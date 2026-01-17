-- Script pentru crearea tabelelor pentru pharmacy-service

CREATE TABLE IF NOT EXISTS pharmacies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    address VARCHAR(500) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pharmacies_id ON pharmacies(id);

CREATE TABLE IF NOT EXISTS pharmacists (
    id SERIAL PRIMARY KEY,
    pharmacy_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    license_number VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pharmacy FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(id)
);

CREATE INDEX IF NOT EXISTS idx_pharmacists_pharmacy_id ON pharmacists(pharmacy_id);
CREATE INDEX IF NOT EXISTS idx_pharmacists_user_id ON pharmacists(user_id);
