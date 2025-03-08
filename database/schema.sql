CREATE TABLE IF NOT EXISTS clienti (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    codice_fiscale CHAR(16) UNIQUE NOT NULL,
    situazione_iva TEXT,
    ultima_fattura NUMERIC(10,2),
    data_ultima_fattura DATE,
    data_scadenza DATE,
    saldo_contabile NUMERIC(10,2)
);