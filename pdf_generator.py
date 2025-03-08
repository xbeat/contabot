from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import logging
import os

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_pdf(clienti: list, filename: str, filtro: str = None):
    """
    Genera un PDF con i dati dei clienti.
    
    :param clienti: Lista di dizionari con i dati dei clienti.
    :param filename: Nome del file PDF da generare.
    :param filtro: Filtro applicato. Se None, mostra tutti i campi.
    :return: Il percorso del file PDF generato.
    """
    try:
        # Crea il documento PDF
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []

        # Stili
        styles = getSampleStyleSheet()
        elements.append(Paragraph("<b>Scheda Contabile</b>", styles["Title"]))

        # Se è un singolo cliente
        if len(clienti) == 1:
            cliente = clienti[0]
            nome_cliente = cliente.get('nome', 'Cliente senza nome')
            elements.append(Paragraph(f"Cliente: {nome_cliente}", styles["Normal"]))

            # Tabella dati
            data = []
            for key, value in cliente.items():
                if key != "nome":  # Escludi il nome, già mostrato sopra
                    # Converti il valore in stringa e gestisci il caso in cui è None
                    value_str = str(value) if value is not None else "N/A"
                    data.append([key.replace("_", " ").title(), value_str])

        # Se sono più clienti
        else:
            # Estrai le colonne dalla query - dobbiamo determinare quali colonne mostrare
            # Prendi tutte le chiavi del primo cliente (assumendo che tutti i clienti abbiano le stesse chiavi)
            if clienti and len(clienti) > 0:
                colonne = list(clienti[0].keys())
                # Rimuovi 'nome' perché lo mostreremo sempre come prima colonna
                if 'nome' in colonne:
                    colonne.remove('nome')
                
                # Crea l'intestazione della tabella
                header = ["Nome"] + [col.replace("_", " ").title() for col in colonne]
                data = [header]
                
                # Aggiungi i dati di ogni cliente
                for cliente in clienti:
                    row = [cliente.get('nome', 'Cliente senza nome')]
                    for col in colonne:
                        value = cliente.get(col)
                        value_str = str(value) if value is not None else "N/A"
                        row.append(value_str)
                    data.append(row)
            else:
                # Gestisci il caso in cui non ci sono clienti
                data = [["Nessun cliente trovato"]]

        # Calcola larghezze colonne dinamicamente
        num_colonne = len(data[0]) if data else 1
        col_width = 500 / num_colonne  # A4 è circa 595 x 842 punti
        
        # Crea la tabella
        table = Table(data, colWidths=[col_width] * num_colonne)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Intestazione grigia
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Testo intestazione bianco
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Allinea tutto al centro
            ('BOX', (0, 0), (-1, -1), 1, colors.black),  # Bordo nero
            ('FONTSIZE', (0, 0), (-1, -1), 9)  # Testo più piccolo per contenere più colonne
        ]))

        # Aggiungi la tabella al PDF
        elements.append(table)
        doc.build(elements)
        logger.info(f"PDF generato con successo: {filename}")

        return filename  # Restituisci il percorso del file PDF generato

    except Exception as e:
        logger.error(f"Errore generazione PDF: {str(e)}")
        raise