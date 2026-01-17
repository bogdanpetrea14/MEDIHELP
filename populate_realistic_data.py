#!/usr/bin/env python3
"""
Script pentru popularea bazei de date cu date realiste și relevante.
Șterge toate datele existente și populează cu minim 15 intrări pentru fiecare tabelă.
"""

import os
import sys
from datetime import datetime, timedelta
import random

# Configurare bază de date
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "medihelp_db")
DB_USER = os.environ.get("DB_USER", "admin123")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin123")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Creează engine
engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def clear_all_data(session):
    """Șterge toate datele existente din toate tabelele."""
    print("🗑️  Șterg datele existente...")
    
    # Ordine importantă pentru foreign keys
    session.execute(text("TRUNCATE TABLE prescriptions CASCADE"))
    session.execute(text("TRUNCATE TABLE pharmacy_stocks CASCADE"))
    session.execute(text("TRUNCATE TABLE pharmacists CASCADE"))
    session.execute(text("TRUNCATE TABLE medications CASCADE"))
    session.execute(text("TRUNCATE TABLE pharmacies CASCADE"))
    session.execute(text("TRUNCATE TABLE user_profiles CASCADE"))
    
    # Resetează secvențele
    session.execute(text("ALTER SEQUENCE user_profiles_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE pharmacies_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE pharmacists_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE medications_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE pharmacy_stocks_id_seq RESTART WITH 1"))
    session.execute(text("ALTER SEQUENCE prescriptions_id_seq RESTART WITH 1"))
    
    session.commit()
    print("✅ Datele au fost șterse.")


def populate_user_profiles(session):
    """Populează user_profiles cu utilizatori realiști."""
    print("\n👥 Populez user_profiles...")
    
    users = [
        # Doctori (15)
        ("dr.ionescu.maria", "DOCTOR"),
        ("dr.popescu.andrei", "DOCTOR"),
        ("dr.radu.alexandra", "DOCTOR"),
        ("dr.stan.george", "DOCTOR"),
        ("dr.munteanu.elena", "DOCTOR"),
        ("dr.constantinescu.radu", "DOCTOR"),
        ("dr.dumitru.cristina", "DOCTOR"),
        ("dr.vasile.mihai", "DOCTOR"),
        ("dr.nicolae.ana", "DOCTOR"),
        ("dr.barbu.daniel", "DOCTOR"),
        ("dr.ciobanu.andreea", "DOCTOR"),
        ("dr.dobre.ionut", "DOCTOR"),
        ("dr.matei.alina", "DOCTOR"),
        ("dr.moldovan.florin", "DOCTOR"),
        ("dr.serban.simona", "DOCTOR"),
        
        # Farmaciști (15)
        ("farmacist.mihaela.popescu", "PHARMACIST"),
        ("farmacist.cristian.radu", "PHARMACIST"),
        ("farmacist.adriana.stan", "PHARMACIST"),
        ("farmacist.bogdan.munteanu", "PHARMACIST"),
        ("farmacist.roxana.constantinescu", "PHARMACIST"),
        ("farmacist.alexandru.dumitru", "PHARMACIST"),
        ("farmacist.andreea.vasile", "PHARMACIST"),
        ("farmacist.sorin.nicolae", "PHARMACIST"),
        ("farmacist.diana.barbu", "PHARMACIST"),
        ("farmacist.marius.ciobanu", "PHARMACIST"),
        ("farmacist.ancuta.dobre", "PHARMACIST"),
        ("farmacist.laurentiu.matei", "PHARMACIST"),
        ("farmacist.corina.moldovan", "PHARMACIST"),
        ("farmacist.florin.serban", "PHARMACIST"),
        ("farmacist.alina.tomescu", "PHARMACIST"),
        
        # Administratori (3)
        ("admin.principal", "ADMIN"),
        ("admin.secundar", "ADMIN"),
        ("admin.sistem", "ADMIN"),
    ]
    
    for username, role in users:
        session.execute(
            text("INSERT INTO user_profiles (username, role) VALUES (:username, :role)"),
            {"username": username, "role": role}
        )
    
    session.commit()
    print(f"✅ Am adăugat {len(users)} utilizatori.")


def populate_pharmacies(session):
    """Populează pharmacies cu farmacii realiste din România."""
    print("\n🏥 Populez pharmacies...")
    
    pharmacies = [
        ("Farmacia Help Farma", "Str. Victoriei 45, București", "021-123-4567", "contact@helpfarma.ro"),
        ("Farmacia Central", "Bd. Unirii 12, București", "021-234-5678", "info@farmaciacentral.ro"),
        ("Farmacia Sanitas", "Calea Floreasca 78, București", "021-345-6789", "office@sanitas.ro"),
        ("Farmacia Vita", "Str. Dorobanți 23, București", "021-456-7890", "contact@farmaciavita.ro"),
        ("Farmacia MediCare", "Bd. Magheru 56, București", "021-567-8901", "hello@medicare.ro"),
        ("Farmacia Plus", "Str. Calea Griviței 89, București", "021-678-9012", "info@farmaciaplus.ro"),
        ("Farmacia Cristal", "Bd. Aviatorilor 34, București", "021-789-0123", "contact@farmaciacristal.ro"),
        ("Farmacia Farmexpert", "Str. Kogălniceanu 67, București", "021-890-1234", "office@farmexpert.ro"),
        ("Farmacia Dr. Max", "Calea Vitan 45, București", "021-901-2345", "contact@drmax.ro"),
        ("Farmacia Catena", "Bd. Iuliu Maniu 123, București", "021-012-3456", "bucuresti@catena.ro"),
        ("Farmacia Sensiblu", "Str. Amzei 78, București", "021-123-4567", "bucuresti@sensiblu.ro"),
        ("Farmacia Dona", "Bd. Basarabia 90, București", "021-234-5678", "contact@dona.ro"),
        ("Farmacia Phoenix", "Str. Mihai Eminescu 12, Cluj-Napoca", "0264-123-456", "cluj@phoenix.ro"),
        ("Farmacia MedLife", "Bd. Eroilor 45, Cluj-Napoca", "0264-234-567", "cluj@medlife.ro"),
        ("Farmacia Regina Maria", "Str. Memorandumului 67, Cluj-Napoca", "0264-345-678", "cluj@reginamaria.ro"),
    ]
    
    for name, address, phone, email in pharmacies:
        session.execute(
            text("""
                INSERT INTO pharmacies (name, address, phone, email, is_active, created_at)
                VALUES (:name, :address, :phone, :email, TRUE, :created_at)
            """),
            {
                "name": name,
                "address": address,
                "phone": phone,
                "email": email,
                "created_at": datetime.utcnow() - timedelta(days=random.randint(30, 365))
            }
        )
    
    session.commit()
    print(f"✅ Am adăugat {len(pharmacies)} farmacii.")


def populate_medications(session):
    """Populează medications cu medicamente realiste."""
    print("\n💊 Populez medications...")
    
    medications = [
        ("Paracetamol 500mg", "Analgezic și antipiretic pentru durere și febră", 8.50),
        ("Ibuprofen 400mg", "Antiinflamator nesteroidian pentru durere și inflamație", 12.00),
        ("Amoxicilină 500mg", "Antibiotic pentru infecții bacteriene", 25.50),
        ("Aspirină 100mg", "Anticoagulant și analgezic", 6.75),
        ("Omeprazol 20mg", "Inhibitor de pompă de protoni pentru arsură", 18.90),
        ("Loratadină 10mg", "Antihistaminic pentru alergie", 15.50),
        ("Metformină 500mg", "Antidiabetic oral", 22.00),
        ("Atorvastatină 20mg", "Statină pentru colesterol", 45.00),
        ("Amlodipină 5mg", "Blocator de canale de calciu pentru tensiune", 28.50),
        ("Metoclopramidă 10mg", "Antiemetic și prokinetic", 9.25),
        ("Salbutamol inhalator", "Bronhodilatator pentru astm", 35.00),
        ("Cetirizină 10mg", "Antihistaminic pentru alergie", 13.50),
        ("Diclofenac 50mg", "Antiinflamator nesteroidian", 16.75),
        ("Ranitidină 150mg", "Antihistaminic H2 pentru arsură", 11.00),
        ("Levotiroxină 50mcg", "Hormon tiroidian pentru hipotiroidism", 19.50),
        ("Vitamina D3 2000UI", "Supliment pentru deficiență de vitamina D", 24.00),
        ("Magnesiu 400mg", "Supliment pentru deficiență de magneziu", 14.50),
        ("Probiotice", "Bacterii benefice pentru flora intestinală", 32.00),
    ]
    
    for name, description, price in medications:
        session.execute(
            text("""
                INSERT INTO medications (name, description, unit_price, created_at)
                VALUES (:name, :description, :price, :created_at)
            """),
            {
                "name": name,
                "description": description,
                "price": price,
                "created_at": datetime.utcnow() - timedelta(days=random.randint(60, 730))
            }
        )
    
    session.commit()
    print(f"✅ Am adăugat {len(medications)} medicamente.")


def populate_pharmacists(session):
    """Populează pharmacists cu farmaciști realiști."""
    print("\n👨‍⚕️ Populez pharmacists...")
    
    # Obține user_ids pentru PHARMACIST
    pharmacist_users = session.execute(
        text("SELECT id FROM user_profiles WHERE role = 'PHARMACIST' ORDER BY id")
    ).fetchall()
    
    # Obține pharmacy_ids
    pharmacies = session.execute(text("SELECT id FROM pharmacies ORDER BY id")).fetchall()
    
    # Asociază farmaciștii cu farmaciile
    license_counter = 1000
    for i, (user_id,) in enumerate(pharmacist_users):
        pharmacy_id = pharmacies[i % len(pharmacies)][0]  # Distribuie farmaciștii
        license_number = f"FARM-{license_counter + i:04d}"
        
        session.execute(
            text("""
                INSERT INTO pharmacists (pharmacy_id, user_id, license_number, is_active, created_at)
                VALUES (:pharmacy_id, :user_id, :license_number, TRUE, :created_at)
            """),
            {
                "pharmacy_id": pharmacy_id,
                "user_id": user_id,
                "license_number": license_number,
                "created_at": datetime.utcnow() - timedelta(days=random.randint(180, 365))
            }
        )
    
    session.commit()
    print(f"✅ Am adăugat {len(pharmacist_users)} farmaciști.")


def populate_pharmacy_stocks(session):
    """Populează pharmacy_stocks cu stocuri realiste."""
    print("\n📦 Populez pharmacy_stocks...")
    
    # Obține toate farmaciile și medicamentele
    pharmacies = session.execute(text("SELECT id FROM pharmacies ORDER BY id")).fetchall()
    medications = session.execute(text("SELECT id FROM medications ORDER BY id")).fetchall()
    
    stock_count = 0
    for pharmacy_id, in pharmacies:
        for medication_id, in medications:
            # Nu toate farmaciile au toate medicamentele
            if random.random() > 0.15:  # 85% din medicamente sunt disponibile
                quantity = random.randint(10, 200)
                min_threshold = max(5, quantity // 10)
                
                session.execute(
                    text("""
                        INSERT INTO pharmacy_stocks (pharmacy_id, medication_id, quantity, min_threshold, last_updated)
                        VALUES (:pharmacy_id, :medication_id, :quantity, :min_threshold, :last_updated)
                    """),
                    {
                        "pharmacy_id": pharmacy_id,
                        "medication_id": medication_id,
                        "quantity": quantity,
                        "min_threshold": min_threshold,
                        "last_updated": datetime.utcnow() - timedelta(days=random.randint(1, 30))
                    }
                )
                stock_count += 1
    
    session.commit()
    print(f"✅ Am adăugat {stock_count} intrări de stoc.")


def populate_prescriptions(session):
    """Populează prescriptions cu rețete realiste."""
    print("\n📋 Populez prescriptions...")
    
    # Obține doctorii
    doctors = session.execute(
        text("SELECT id FROM user_profiles WHERE role = 'DOCTOR' ORDER BY id")
    ).fetchall()
    
    # Obține medicamentele
    medications = session.execute(
        text("SELECT name FROM medications ORDER BY id")
    ).fetchall()
    
    # Obține farmaciile
    pharmacies = session.execute(text("SELECT id FROM pharmacies ORDER BY id")).fetchall()
    
    # Obține farmaciștii
    pharmacists = session.execute(
        text("SELECT id, pharmacy_id FROM pharmacists ORDER BY id")
    ).fetchall()
    
    statuses = ["PENDING", "FULFILLED", "CANCELLED"]
    dosages = ["1 tabletă de 2 ori pe zi", "1 tabletă dimineața", "2 tablete la 8 ore", 
               "1 capsule pe zi", "1 comprimat la 12 ore", "2 comprimate la masă"]
    
    prescriptions = []
    for i in range(20):  # 20 de rețete
        doctor_id = random.choice(doctors)[0]
        patient_id = random.randint(1000, 9999)  # ID-uri de pacienți fictivi
        medication_name = random.choice(medications)[0]
        dosage = random.choice(dosages)
        quantity = random.randint(10, 60)
        instructions = random.choice([
            "A se lua înainte de masă",
            "A se lua după masă",
            "A se lua cu apă",
            "A se evita alcoolul",
            "A se lua conform prescripției",
        ])
        
        status = random.choice(statuses)
        created_at = datetime.utcnow() - timedelta(days=random.randint(1, 90))
        
        pharmacy_id = None
        pharmacist_id = None
        fulfilled_at = None
        
        if status == "FULFILLED":
            pharmacist_data = random.choice(pharmacists)
            pharmacist_id = pharmacist_data[0]
            pharmacy_id = pharmacist_data[1]
            fulfilled_at = created_at + timedelta(days=random.randint(1, 7))
        elif status == "PENDING" and random.random() > 0.3:
            pharmacy_id = random.choice(pharmacies)[0]
        
        session.execute(
            text("""
                INSERT INTO prescriptions 
                (doctor_id, patient_id, medication_name, dosage, quantity, instructions, 
                 status, pharmacy_id, pharmacist_id, created_at, fulfilled_at)
                VALUES 
                (:doctor_id, :patient_id, :medication_name, :dosage, :quantity, :instructions,
                 :status, :pharmacy_id, :pharmacist_id, :created_at, :fulfilled_at)
            """),
            {
                "doctor_id": doctor_id,
                "patient_id": patient_id,
                "medication_name": medication_name,
                "dosage": dosage,
                "quantity": quantity,
                "instructions": instructions,
                "status": status,
                "pharmacy_id": pharmacy_id,
                "pharmacist_id": pharmacist_id,
                "created_at": created_at,
                "fulfilled_at": fulfilled_at
            }
        )
    
    session.commit()
    print(f"✅ Am adăugat 20 de rețete.")


def main():
    """Funcția principală."""
    print("=" * 60)
    print("🚀 Populare bază de date cu date realiste")
    print("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Șterge toate datele existente
        clear_all_data(session)
        
        # Populează tabelele în ordinea corectă (respectând foreign keys)
        populate_user_profiles(session)
        populate_pharmacies(session)
        populate_medications(session)
        populate_pharmacists(session)
        populate_pharmacy_stocks(session)
        populate_prescriptions(session)
        
        print("\n" + "=" * 60)
        print("✅ Popularea bazei de date a fost finalizată cu succes!")
        print("=" * 60)
        
        # Afișează statistici
        stats = session.execute(text("SELECT role, COUNT(*) FROM user_profiles GROUP BY role")).fetchall()
        print("\n📊 Statistici:")
        print(f"   - Farmacii: {session.execute(text('SELECT COUNT(*) FROM pharmacies')).scalar()}")
        print(f"   - Medicamente: {session.execute(text('SELECT COUNT(*) FROM medications')).scalar()}")
        print(f"   - Farmaciști: {session.execute(text('SELECT COUNT(*) FROM pharmacists')).scalar()}")
        print(f"   - Rețete: {session.execute(text('SELECT COUNT(*) FROM prescriptions')).scalar()}")
        print(f"   - Stocuri: {session.execute(text('SELECT COUNT(*) FROM pharmacy_stocks')).scalar()}")
        print("\n   Utilizatori:")
        for role, count in stats:
            print(f"     - {role}: {count}")
        
    except Exception as e:
        print(f"\n❌ Eroare: {e}")
        session.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
