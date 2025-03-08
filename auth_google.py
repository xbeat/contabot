import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Configurazione
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',  # Permessi per Gmail
]

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

def get_credentials():
    """Ottieni o crea le credenziali OAuth 2.0."""
    creds = None
    creds_path = get_credentials_path()
    token_path = get_token_path()

    # Se esiste già un token, caricalo
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Se non ci sono credenziali valide, chiedi all'utente di autenticarsi
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Salva le credenziali per il prossimo avvio
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds

if __name__ == "__main__":
    creds = get_credentials()
    print("Credenziali configurate con successo!")