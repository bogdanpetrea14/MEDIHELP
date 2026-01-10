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
    Float,
    Boolean,
    Enum as SQLEnum,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime
import enum

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


class PrescriptionStatus(enum.Enum):
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    medication_name = Column(String(200), nullable=False)
    dosage = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    instructions = Column(String(500))
    status = Column(String(20), default=PrescriptionStatus.PENDING.value, nullable=False)
    pharmacy_id = Column(Integer, nullable=True, index=True)
    pharmacist_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    fulfilled_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


def init_db():
    """Creează tabelele, dacă nu există."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        app.logger.error(f"Failed to init DB: {e}")


init_db()


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "prescription-service"
    }), 200


@app.route("/db-health", methods=["GET"])
def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"db": "ok"}), 200
    except Exception as e:
        return jsonify({"db": "error", "error": str(e)}), 500


@app.route("/prescriptions", methods=["GET"])
def get_prescriptions():
    """Obține toate prescripțiile, cu filtrare opțională."""
    session = SessionLocal()
    try:
        doctor_id = request.args.get("doctor_id", type=int)
        patient_id = request.args.get("patient_id", type=int)
        pharmacy_id = request.args.get("pharmacy_id", type=int)
        status = request.args.get("status")

        query = session.query(Prescription)

        if doctor_id:
            query = query.filter(Prescription.doctor_id == doctor_id)
        if patient_id:
            query = query.filter(Prescription.patient_id == patient_id)
        if pharmacy_id:
            query = query.filter(Prescription.pharmacy_id == pharmacy_id)
        if status:
            query = query.filter(Prescription.status == status)

        prescriptions = query.order_by(Prescription.created_at.desc()).all()

        return jsonify([
            {
                "id": p.id,
                "doctor_id": p.doctor_id,
                "patient_id": p.patient_id,
                "medication_name": p.medication_name,
                "dosage": p.dosage,
                "quantity": p.quantity,
                "instructions": p.instructions,
                "status": p.status,
                "pharmacy_id": p.pharmacy_id,
                "pharmacist_id": p.pharmacist_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "fulfilled_at": p.fulfilled_at.isoformat() if p.fulfilled_at else None,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            }
            for p in prescriptions
        ]), 200
    finally:
        session.close()


@app.route("/prescriptions", methods=["POST"])
def create_prescription():
    """Creează o nouă prescripție (doar doctorii pot face asta)."""
    body = request.get_json() or {}
    doctor_id = body.get("doctor_id")
    patient_id = body.get("patient_id")
    medication_name = body.get("medication_name")
    dosage = body.get("dosage")
    quantity = body.get("quantity")
    instructions = body.get("instructions", "")
    expires_at_str = body.get("expires_at")

    if not all([doctor_id, patient_id, medication_name, dosage, quantity]):
        return jsonify({"error": "doctor_id, patient_id, medication_name, dosage, and quantity are required"}), 400

    session = SessionLocal()
    try:
        expires_at = None
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            except:
                pass

        prescription = Prescription(
            doctor_id=doctor_id,
            patient_id=patient_id,
            medication_name=medication_name,
            dosage=dosage,
            quantity=quantity,
            instructions=instructions,
            status=PrescriptionStatus.PENDING.value,
            expires_at=expires_at
        )
        session.add(prescription)
        session.commit()
        session.refresh(prescription)

        return jsonify({
            "id": prescription.id,
            "doctor_id": prescription.doctor_id,
            "patient_id": prescription.patient_id,
            "medication_name": prescription.medication_name,
            "dosage": prescription.dosage,
            "quantity": prescription.quantity,
            "instructions": prescription.instructions,
            "status": prescription.status,
            "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
            "expires_at": prescription.expires_at.isoformat() if prescription.expires_at else None,
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/prescriptions/<int:prescription_id>", methods=["GET"])
def get_prescription(prescription_id: int):
    """Obține o prescripție specifică."""
    session = SessionLocal()
    try:
        prescription = session.get(Prescription, prescription_id)
        if not prescription:
            return jsonify({"error": "not found"}), 404

        return jsonify({
            "id": prescription.id,
            "doctor_id": prescription.doctor_id,
            "patient_id": prescription.patient_id,
            "medication_name": prescription.medication_name,
            "dosage": prescription.dosage,
            "quantity": prescription.quantity,
            "instructions": prescription.instructions,
            "status": prescription.status,
            "pharmacy_id": prescription.pharmacy_id,
            "pharmacist_id": prescription.pharmacist_id,
            "created_at": prescription.created_at.isoformat() if prescription.created_at else None,
            "fulfilled_at": prescription.fulfilled_at.isoformat() if prescription.fulfilled_at else None,
            "expires_at": prescription.expires_at.isoformat() if prescription.expires_at else None,
        }), 200
    finally:
        session.close()


@app.route("/prescriptions/<int:prescription_id>/fulfill", methods=["POST"])
def fulfill_prescription(prescription_id: int):
    """Onorează o prescripție (doar farmaciștii pot face asta)."""
    body = request.get_json() or {}
    pharmacy_id = body.get("pharmacy_id")
    pharmacist_id = body.get("pharmacist_id")

    if not pharmacy_id or not pharmacist_id:
        return jsonify({"error": "pharmacy_id and pharmacist_id are required"}), 400

    session = SessionLocal()
    try:
        prescription = session.get(Prescription, prescription_id)
        if not prescription:
            return jsonify({"error": "not found"}), 404

        if prescription.status != PrescriptionStatus.PENDING.value:
            return jsonify({"error": f"prescription is already {prescription.status}"}), 400

        prescription.status = PrescriptionStatus.FULFILLED.value
        prescription.pharmacy_id = pharmacy_id
        prescription.pharmacist_id = pharmacist_id
        prescription.fulfilled_at = datetime.utcnow()

        session.commit()
        session.refresh(prescription)

        return jsonify({
            "id": prescription.id,
            "status": prescription.status,
            "pharmacy_id": prescription.pharmacy_id,
            "pharmacist_id": prescription.pharmacist_id,
            "fulfilled_at": prescription.fulfilled_at.isoformat() if prescription.fulfilled_at else None,
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/prescriptions/<int:prescription_id>/cancel", methods=["POST"])
def cancel_prescription(prescription_id: int):
    """Anulează o prescripție."""
    session = SessionLocal()
    try:
        prescription = session.get(Prescription, prescription_id)
        if not prescription:
            return jsonify({"error": "not found"}), 404

        if prescription.status == PrescriptionStatus.FULFILLED.value:
            return jsonify({"error": "cannot cancel fulfilled prescription"}), 400

        prescription.status = PrescriptionStatus.CANCELLED.value
        session.commit()

        return jsonify({
            "id": prescription.id,
            "status": prescription.status,
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
