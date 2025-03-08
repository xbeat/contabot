import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """Inizializza la connessione al database."""
        self.conn = self._connect()

    def _connect(self):
        """Stabilisce una connessione al database in base all'ambiente (prod/dev)."""
        try:
            if os.getenv('ENV') == 'prod':
                # Modalità produzione: usa DATABASE_URL da Render
                return psycopg2.connect(
                    os.getenv('DATABASE_URL'),
                    sslmode='require',
                    cursor_factory=RealDictCursor
                )
            else:
                # Modalità sviluppo: usa variabili d'ambiente locali
                return psycopg2.connect(
                    host=os.getenv('DB_HOST'),
                    dbname=os.getenv('DB_NAME'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    cursor_factory=RealDictCursor
                )
        except Exception as e:
            logger.error(f"Errore connessione al database: {str(e)}")
            raise

    def execute_query(self, query: str):
        """
        Esegue una query SQL e restituisce i risultati.
        
        :param query: La query SQL da eseguire.
        :return: Lista di dizionari con i risultati della query.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Errore esecuzione query: {str(e)}")
            self.conn.rollback()
            return []