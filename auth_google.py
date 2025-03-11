import os
import json
import logging  # Aggiunto import mancante
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Configurazione logging
logging.basicConfig(level=logging.INFO)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_credentials():
    """Ottieni o crea le credenziali OAuth 2.0."""
    creds = None
    token_path = get_token_path()
    client_secrets_path = get_credentials_path()  # Rinominato per chiarezza

    # 1. Tentativo di caricamento token esistente
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            logging.info("Token caricato correttamente")
        except Exception as e:
            logging.warning(f"Errore nel caricamento del token: {str(e)}")

    # 2. Aggiornamento token scaduto
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Salva il token aggiornato
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
            logging.info("Token aggiornato e salvato")
        except Exception as e:
            logging.error(f"Errore nell'aggiornamento: {str(e)}")
            creds = None

    # 3. Flusso OAuth solo se necessario e in ambiente di sviluppo
    if not creds:
        if os.getenv('ENV') == 'prod':
            raise Exception("Token mancante in produzione")
        
        if not os.path.exists(client_secrets_path):
            raise FileNotFoundError("File client_secrets.json mancante")
        
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Salva il nuovo token
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        logging.info("Nuovo token generato e salvato")

    return creds