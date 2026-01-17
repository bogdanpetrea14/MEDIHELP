#!/usr/bin/env python3
"""
Script pentru a inițializa manual tabelele pentru pharmacy-service
Rulează: python init_db_pharmacy.py
"""

import sys
import os

# Adaugă directorul pharmacy_service la path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pharmacy_service'))

from pharmacy_service.app import init_db, engine, Base, Pharmacy, Pharmacist

if __name__ == "__main__":
    print("Initializing pharmacy-service database tables...")
    result = init_db()
    if result:
        print("✓ Database tables created successfully!")
        print("Tables created:")
        print("  - pharmacies")
        print("  - pharmacists")
    else:
        print("✗ Failed to create database tables")
        sys.exit(1)
