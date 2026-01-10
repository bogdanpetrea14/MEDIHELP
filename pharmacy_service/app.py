import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import (
    create_engine,
    text,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "medihelp_db")
DB_USER = os.environ.get("DB_USER", "admin123")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin123")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    address = Column(String(500), nullable=False)
    phone = Column(String(50))
    email = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Pharmacist(Base):
    __tablename__ = "pharmacists"

    id = Column(Integer, primary_key=True, index=True)
    pharmacy_id = Column(Integer, ForeignKey("pharmacies.id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # Referință la user_profile
    license_number = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    """Creează tabelele, dacă nu există."""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to initialize database (attempt {attempt + 1}/{max_retries})...")
            print(f"Database URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")
            
            # Test connection first
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Create tables
            Base.metadata.create_all(bind=engine)
            print("Database tables created successfully!")
            return True
        except Exception as e:
            print(f"Failed to init DB (attempt {attempt + 1}/{max_retries}): {e}")
            app.logger.error(f"Failed to init DB: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Tables may not be created.")
                return False
    return False


# Initialize database on startup
import time
time.sleep(2)  # Wait a bit for DB to be ready
init_db()


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "pharmacy-service"
    }), 200


@app.route("/db-health", methods=["GET"])
def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"db": "ok"}), 200
    except Exception as e:
        return jsonify({"db": "error", "error": str(e)}), 500


@app.route("/init-db", methods=["POST"])
def init_db_endpoint():
    """Endpoint pentru a inițializa manual baza de date."""
    try:
        result = init_db()
        if result:
            return jsonify({"message": "Database initialized successfully"}), 200
        else:
            return jsonify({"error": "Failed to initialize database after retries"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/pharmacies", methods=["GET"])
def get_pharmacies():
    """Obține toate farmaciile."""
    session = SessionLocal()
    try:
        active_only = request.args.get("active_only", "false").lower() == "true"
        query = session.query(Pharmacy)
        if active_only:
            query = query.filter(Pharmacy.is_active == True)
        
        pharmacies = query.all()
        return jsonify([
            {
                "id": p.id,
                "name": p.name,
                "address": p.address,
                "phone": p.phone,
                "email": p.email,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in pharmacies
        ]), 200
    finally:
        session.close()


@app.route("/pharmacies", methods=["POST"])
def create_pharmacy():
    """Creează o nouă farmacie."""
    body = request.get_json() or {}
    name = body.get("name")
    address = body.get("address")
    phone = body.get("phone", "")
    email = body.get("email", "")

    if not name or not address:
        return jsonify({"error": "name and address are required"}), 400

    session = SessionLocal()
    try:
        pharmacy = Pharmacy(
            name=name,
            address=address,
            phone=phone,
            email=email
        )
        session.add(pharmacy)
        session.commit()
        session.refresh(pharmacy)

        return jsonify({
            "id": pharmacy.id,
            "name": pharmacy.name,
            "address": pharmacy.address,
            "phone": pharmacy.phone,
            "email": pharmacy.email,
            "is_active": pharmacy.is_active,
            "created_at": pharmacy.created_at.isoformat() if pharmacy.created_at else None,
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/pharmacies/<int:pharmacy_id>", methods=["GET"])
def get_pharmacy(pharmacy_id: int):
    """Obține o farmacie specifică."""
    session = SessionLocal()
    try:
        pharmacy = session.get(Pharmacy, pharmacy_id)
        if not pharmacy:
            return jsonify({"error": "not found"}), 404

        return jsonify({
            "id": pharmacy.id,
            "name": pharmacy.name,
            "address": pharmacy.address,
            "phone": pharmacy.phone,
            "email": pharmacy.email,
            "is_active": pharmacy.is_active,
            "created_at": pharmacy.created_at.isoformat() if pharmacy.created_at else None,
        }), 200
    finally:
        session.close()


@app.route("/pharmacies/<int:pharmacy_id>/pharmacists", methods=["GET"])
def get_pharmacy_pharmacists(pharmacy_id: int):
    """Obține farmaciștii unei farmacii."""
    session = SessionLocal()
    try:
        pharmacists = session.query(Pharmacist).filter_by(
            pharmacy_id=pharmacy_id,
            is_active=True
        ).all()

        return jsonify([
            {
                "id": p.id,
                "pharmacy_id": p.pharmacy_id,
                "user_id": p.user_id,
                "license_number": p.license_number,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in pharmacists
        ]), 200
    finally:
        session.close()


@app.route("/pharmacists", methods=["GET"])
def get_pharmacists():
    """Obține toți farmaciștii."""
    session = SessionLocal()
    try:
        pharmacy_id = request.args.get("pharmacy_id", type=int)
        user_id = request.args.get("user_id", type=int)

        query = session.query(Pharmacist)
        if pharmacy_id:
            query = query.filter(Pharmacist.pharmacy_id == pharmacy_id)
        if user_id:
            query = query.filter(Pharmacist.user_id == user_id)

        pharmacists = query.all()
        return jsonify([
            {
                "id": p.id,
                "pharmacy_id": p.pharmacy_id,
                "user_id": p.user_id,
                "license_number": p.license_number,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in pharmacists
        ]), 200
    finally:
        session.close()


@app.route("/pharmacists", methods=["POST"])
def create_pharmacist():
    """Creează un nou farmacist."""
    body = request.get_json() or {}
    pharmacy_id = body.get("pharmacy_id")
    user_id = body.get("user_id")
    license_number = body.get("license_number")

    if not all([pharmacy_id, user_id, license_number]):
        return jsonify({"error": "pharmacy_id, user_id, and license_number are required"}), 400

    session = SessionLocal()
    try:
        pharmacist = Pharmacist(
            pharmacy_id=pharmacy_id,
            user_id=user_id,
            license_number=license_number
        )
        session.add(pharmacist)
        session.commit()
        session.refresh(pharmacist)

        return jsonify({
            "id": pharmacist.id,
            "pharmacy_id": pharmacist.pharmacy_id,
            "user_id": pharmacist.user_id,
            "license_number": pharmacist.license_number,
            "is_active": pharmacist.is_active,
            "created_at": pharmacist.created_at.isoformat() if pharmacist.created_at else None,
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/pharmacists/<int:pharmacist_id>", methods=["GET"])
def get_pharmacist(pharmacist_id: int):
    """Obține un farmacist specific."""
    session = SessionLocal()
    try:
        pharmacist = session.get(Pharmacist, pharmacist_id)
        if not pharmacist:
            return jsonify({"error": "not found"}), 404

        return jsonify({
            "id": pharmacist.id,
            "pharmacy_id": pharmacist.pharmacy_id,
            "user_id": pharmacist.user_id,
            "license_number": pharmacist.license_number,
            "is_active": pharmacist.is_active,
            "created_at": pharmacist.created_at.isoformat() if pharmacist.created_at else None,
        }), 200
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

