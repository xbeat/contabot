import os
import logging
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from database import Database
from pdf_generator import generate_pdf
from gmail_service import GmailService
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from dotenv import load_dotenv
from google.generativeai import configure, GenerativeModel
from google.api_core.exceptions import ResourceExhausted

# Carica le variabili d'ambiente
load_dotenv()

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)

class MaskingFormatter(logging.Formatter):
    """Maschera il token Telegram nei log."""
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.token = os.getenv('TELEGRAM_TOKEN')
        
    def format(self, record):
        formatted = super().format(record)
        if self.token and self.token in formatted:
            return formatted.replace(self.token, "[TOKEN NASCOSTO]")
        return formatted

handler = logging.StreamHandler()
handler.setFormatter(MaskingFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.root.handlers = [handler]

logger = logging.getLogger(__name__)

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Gestisce le richieste di health check."""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

class HealthServer:
    """Avvia un server HTTP per il health check in produzione."""
    def __init__(self, port=10000):
        self.port = port
        self.server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        self.thread = Thread(target=self.server.serve_forever)

    def start(self):
        """Avvia il server di health check."""
        self.thread.start()
        logger.info(f"Health check server avviato su porta {self.port}")

    def stop(self):
        """Ferma il server di health check."""
        self.server.shutdown()
        self.thread.join()
        logger.info("Health check server fermato")

class Contabot:
    def __init__(self):
        """Inizializza il bot e i servizi."""
        self.db = Database()
        self.gmail = GmailService()
        self.health_server = HealthServer() if os.getenv('ENV') == 'prod' else None
        self.llm = self._init_llm()

    def _init_llm(self):
        """Inizializza il modello Gemini."""
        configure(api_key=os.getenv('GOOGLE_API_KEY'))
        return GenerativeModel('gemini-1.5-pro-002')

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce il comando /start."""
        await update.message.reply_text(
            "Ciao! Sono Contabot. Puoi chiedermi informazioni sui clienti. Es: 'Mostrami il saldo di Mario Rossi'."
        )

    def _create_prompt(self, user_input: str):
        """Crea il prompt per l'LLM per generare query SQL."""
        schema = """
            CREATE TABLE clienti (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                codice_fiscale CHAR(16) UNIQUE NOT NULL,
                situazione_iva TEXT,
                ultima_fattura NUMERIC(10,2),
                data_ultima_fattura DATE,
                data_scadenza DATE,
                saldo_contabile NUMERIC(10,2)
            );
        """
        return f"""
            Schema del database:
            {schema}

            Richiesta dell'utente: "{user_input}"

            Istruzioni dettagliate:
            1. Analizza con attenzione la richiesta dell'utente e identifica:
               - Se si riferisce a un cliente specifico (tramite nome) o a più clienti
               - Se richiede specifiche colonne o tutte le informazioni
               - Se include filtri o condizioni (comparazioni con valori)

            2. Genera una query SQL seguendo queste regole precise:
               - Se l'utente chiede dati su un singolo cliente (es. "codice fiscale di Mario Rossi"):
                   * Se richiede colonne specifiche: SELECT solo quelle colonne (nome_colonna FROM clienti WHERE nome ILIKE '%Mario Rossi%')
                   * Se la richiesta è generica: SELECT * FROM clienti WHERE nome ILIKE '%Mario Rossi%'
                   
               - Se l'utente chiede dati filtrati su più clienti:
                   * Se richiede colonne specifiche: SELECT nome, colonne_richieste FROM clienti WHERE condizione
                   * Se la richiesta è generica: SELECT * FROM clienti WHERE condizione

            3. Gestisci correttamente i filtri numerici e date:
               - Numeri: usa operatori appropriati (<, >, =, <=, >=)
               - Date: usa formato 'YYYY-MM-DD' e operatori appropriati
               - Per intervalli di date, usa BETWEEN o combinazioni di AND con >= e <=

            4. Usa i nomi di colonna esattamente come definiti nello schema:
               - data_scadenza (non "scadenza" o "prossima_scadenza")
               - saldo_contabile (non "saldo")
               - ecc.

            5. Restituisci SOLO la query SQL, senza commenti o spiegazioni.

            Esempi di input e query corrette:
            - Input: "Dammi il codice fiscale di Mario Rossi"
              Output: SELECT nome, codice_fiscale FROM clienti WHERE nome ILIKE '%Mario Rossi%'

            - Input: "Mostrami la situazione IVA e il saldo di Luigi Verdi"
              Output: SELECT nome, situazione_iva, saldo_contabile FROM clienti WHERE nome ILIKE '%Luigi Verdi%'

            - Input: "Clienti con scadenza a luglio 2025"
              Output: SELECT * FROM clienti WHERE data_scadenza BETWEEN '2025-07-01' AND '2025-07-31'

            - Input: "Saldo contabile dei clienti con ultima fattura maggiore di 5000"
              Output: SELECT nome, saldo_contabile FROM clienti WHERE ultima_fattura > 5000

            - Input: "Tutti i clienti con saldo negativo"
              Output: SELECT * FROM clienti WHERE saldo_contabile < 0

            Ora genera la query SQL corretta per questa richiesta: "{user_input}"
        """

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gestisce i messaggi dell'utente."""
        user_input = update.message.text
        pdf_path = None  # Inizializza pdf_path all'inizio

        try:
            # Crea il prompt per l'LLM
            prompt = self._create_prompt(user_input)
            
            # Invia il prompt al modello LLM
            try:
                response = self.llm.generate_content(prompt)
                query = response.text.strip()
                logger.info(f"Query generata: {query}")
            except ResourceExhausted:
                await update.message.reply_text("❌ Limite di richieste raggiunto. Riprova più tardi.")
                return
            except Exception as e:
                logger.error(f"Errore generazione query: {str(e)}")
                await update.message.reply_text("❌ Si è verificato un errore. Riprova più tardi.")
                return

            # Esegui la query sul database
            clienti = self.db.execute_query(query)
            if not clienti:
                await update.message.reply_text("❌ Nessun cliente trovato con i criteri specificati.")
                return

            # Log dei dati dei clienti per debug
            logger.info(f"Dati clienti trovati: {clienti}")

            # Determina se è una richiesta per un singolo cliente o per multipli clienti
            is_single_client = len(clienti) == 1 or 'ILIKE' in query
            
            # Determina il nome del file e il filtro
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if is_single_client and len(clienti) == 1:
                nome_cliente = clienti[0].get('nome', 'Cliente')
                pdf_path = f"situazione_{nome_cliente.replace(' ', '_')}_{timestamp}.pdf"
                filtro = None  # Per singolo cliente mostriamo tutti i campi
            else:
                # Estrai le colonne selezionate dalla query
                try:
                    # Estrai le colonne selezionate dalla query
                    select_part = query.split('FROM')[0].strip()
                    if 'SELECT *' in select_part:
                        filtro = None  # Tutte le colonne
                    else:
                        # Rimuovi 'SELECT' e ottieni le colonne
                        cols = select_part.replace('SELECT', '').strip().split(',')
                        # Pulisci i nomi delle colonne
                        cols = [col.strip() for col in cols]
                        filtro = None
                except:
                    filtro = None
                    
                pdf_path = f"clienti_trovati_{timestamp}.pdf"

            # Genera il PDF
            try:
                generate_pdf(clienti, pdf_path, filtro)
            except Exception as e:
                logger.error(f"Errore generazione PDF: {str(e)}")
                await update.message.reply_text("❌ Si è verificato un errore durante la generazione del PDF.")
                return

            # Invia il PDF su Telegram
            try:
                await update.message.reply_document(
                    document=open(pdf_path, 'rb'),
                    caption="Risultati della ricerca"
                )
            except Exception as e:
                logger.error(f"Errore invio PDF su Telegram: {str(e)}")
                await update.message.reply_text("❌ Si è verificato un errore durante l'invio del PDF.")
                return

            # Invia il PDF via email
            try:
                self.gmail.send_email_with_attachment(
                    to="kaolay@gmail.com",
                    subject="Risultati della ricerca",
                    body="In allegato i risultati della ricerca.",
                    attachment_path=pdf_path
                )
            except Exception as e:
                logger.error(f"Errore invio email: {str(e)}")
                await update.message.reply_text("❌ Si è verificato un errore durante l'invio dell'email.")
                return

            logger.info(f"PDF generato e inviato per {len(clienti)} clienti")

        except Exception as e:
            logger.error(f"Errore gestione richiesta: {str(e)}")
            await update.message.reply_text("❌ Si è verificato un errore. Riprova più tardi.")
        finally:
            # Elimina il file PDF dopo l'invio
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.info(f"File PDF eliminato: {pdf_path}")

    def run(self):
        """Avvia il bot."""
        if self.health_server:
            self.health_server.start()

        # Crea l'applicazione Telegram
        app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()

        # Aggiungi i gestori di comandi
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Avvia il bot
        app.run_polling()

if __name__ == "__main__":
    bot = Contabot()
    try:
        bot.run()
    finally:
        if bot.health_server:
            bot.health_server.stop()