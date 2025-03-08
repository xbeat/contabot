import os
import logging
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import base64

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_credentials_path():
    """
    Restituisce il percorso corretto per le credenziali in base all'ambiente.
    - In produzione: usa /etc/secrets/credentials.json
    - In sviluppo: usa credentials/credentials.json
    """
    if os.getenv('ENV') == 'prod':
        return '/etc/secrets/credentials.json'
    else:
        return 'credentials/credentials.json'

def get_token_path():
    """
    Restituisce il percorso corretto per il token in base all'ambiente.
    - In produzione: usa /etc/secrets/token.json
    - In sviluppo: usa credentials/token.json
    """
    if os.getenv('ENV') == 'prod':
        return '/etc/secrets/token.json'
    else:
        return 'credentials/token.json'

class GmailService:
    def __init__(self):
        """Inizializza il servizio Gmail."""
        self.service = self._authenticate()

    def _authenticate(self):
        """Autentica l'utente con Google OAuth."""
        creds_path = get_credentials_path()
        token_path = get_token_path()

        try:
            # Se esiste già un token, caricalo
            if os.path.exists(token_path):
                with open(token_path, 'r') as token:
                    creds_info = json.load(token)
                creds = Credentials.from_authorized_user_info(creds_info, scopes=['https://www.googleapis.com/auth/gmail.send'])
                
                if not creds.valid:
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        raise Exception("Credenziali non valide")
                
                return build('gmail', 'v1', credentials=creds)

            # Se non esiste un token, crealo
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes=['https://www.googleapis.com/auth/gmail.send'])
            creds = flow.run_local_server(port=0)
            
            # Salva le credenziali per il prossimo avvio
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            
            return build('gmail', 'v1', credentials=creds)

        except Exception as e:
            logger.error(f"Errore autenticazione Gmail: {str(e)}")
            raise

    def send_email_with_attachment(self, to: str, subject: str, body: str, attachment_path: str):
        """
        Invia un'email con allegato.
        
        :param to: Destinatario dell'email.
        :param subject: Oggetto dell'email.
        :param body: Corpo dell'email.
        :param attachment_path: Percorso del file da allegare.
        """
        try:
            # Crea il messaggio email
            message = MIMEMultipart()
            message['to'] = to
            message['from'] = 'kaolay@gmail.com'
            message['subject'] = subject
            message.attach(MIMEText(body))

            # Allega il PDF
            with open(attachment_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                message.attach(attachment)

            # Codifica il messaggio in base64
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            # Invia l'email
            self.service.users().messages().send(userId='me', body={'raw': raw}).execute()
            logger.info(f"Email inviata con successo a {to}")

        except Exception as e:
            logger.error(f"Errore invio email: {str(e)}")
            raise