-- Script pentru crearea tabelelor pentru inventory-service

CREATE TABLE IF NOT EXISTS medications (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    description VARCHAR(500),
    unit_price FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_medications_id ON medications(id);
CREATE INDEX IF NOT EXISTS idx_medications_name ON medications(name);

CREATE TABLE IF NOT EXISTS pharmacy_stocks (
    id SERIAL PRIMARY KEY,
    pharmacy_id INTEGER NOT NULL,
    medication_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    min_threshold INTEGER NOT NULL DEFAULT 10,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_quantity_non_negative CHECK (quantity >= 0)
);

CREATE INDEX IF NOT EXISTS idx_pharmacy_stocks_pharmacy_id ON pharmacy_stocks(pharmacy_id);
CREATE INDEX IF NOT EXISTS idx_pharmacy_stocks_medication_id ON pharmacy_stocks(medication_id);

-- Adaugă foreign key dacă nu există
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pharmacy_stocks_medication_id_fkey') THEN
        ALTER TABLE pharmacy_stocks ADD CONSTRAINT pharmacy_stocks_medication_id_fkey 
        FOREIGN KEY (medication_id) REFERENCES medications(id);
    END IF;
END $$;
