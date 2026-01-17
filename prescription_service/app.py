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
import requests
import redis
import json
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
CORS(app)

# Prometheus metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "medihelp_db")
DB_USER = os.environ.get("DB_USER", "admin123")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin123")

INVENTORY_BASE_URL = os.environ.get(
    "INVENTORY_BASE_URL",
    "http://inventory-service:5000"
)


def track_medication_usage_in_redis(medication_name: str):
    """Trimite tracking pentru utilizare medicament către inventory-service."""
    if not redis_available:
        return
    try:
        # Trimite direct către inventory-service prin Redis pub/sub sau direct
        # Pentru simplitate, vom face un request async (fire-and-forget)
        # În producție, ar fi mai bine să folosești un queue (Celery, etc.)
        import threading
        def track_async():
            try:
                requests.post(
                    f"{INVENTORY_BASE_URL}/medications/track-usage",
                    json={"medication_name": medication_name},
                    timeout=1
                )
            except:
                pass  # Nu blocăm dacă tracking eșuează
        threading.Thread(target=track_async, daemon=True).start()
    except:
        pass

# Redis configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=2
    )
    redis_client.ping()
    redis_available = True
except:
    redis_available = False
    app.logger.warning("Redis not available, caching disabled")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL, 
    echo=False, 
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verifică conexiunea înainte de utilizare
    pool_recycle=3600    # Recyclează conexiunile după 1 oră
)
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


def get_cache_key(prefix: str, *args) -> str:
    """Generează o cheie de cache."""
    return f"{prefix}:{':'.join(str(a) for a in args)}"


def get_from_cache(key: str):
    """Obține date din cache."""
    if not redis_available:
        return None
    try:
        data = redis_client.get(key)
        return json.loads(data) if data else None
    except:
        return None


def set_cache(key: str, value, ttl: int = 300):
    """Salvează date în cache."""
    if not redis_available:
        return
    try:
        redis_client.setex(key, ttl, json.dumps(value))
    except:
        pass


def invalidate_cache(pattern: str):
    """Șterge chei din cache care se potrivesc cu pattern-ul."""
    if not redis_available:
        return
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except:
        pass


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
        "service": "prescription-service",
        "redis": "available" if redis_available else "unavailable"
    }), 200


@app.route("/metrics", methods=["GET"])
def metrics():
    """Endpoint Prometheus pentru metrici."""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.before_request
def before_request():
    """Middleware pentru tracking metrici Prometheus."""
    request.start_time = time.time()


@app.after_request
def after_request(response):
    """Middleware pentru tracking metrici Prometheus după request."""
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        endpoint = request.endpoint or 'unknown'
        method = request.method
        
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        http_requests_total.labels(method=method, endpoint=endpoint, status=response.status_code).inc()
    
    return response


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


@app.route("/prescriptions", methods=["GET"])
def get_prescriptions():
    """Obține toate prescripțiile, cu filtrare opțională."""
    # Build cache key from query parameters
    doctor_id = request.args.get("doctor_id", type=int)
    patient_id = request.args.get("patient_id", type=int)
    pharmacy_id = request.args.get("pharmacy_id", type=int)
    status = request.args.get("status")
    
    cache_key = get_cache_key("prescriptions", 
                               doctor_id or "all",
                               patient_id or "all",
                               pharmacy_id or "all",
                               status or "all")
    
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200
    
    session = SessionLocal()
    try:
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

        result = [
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
        ]
        
        set_cache(cache_key, result, ttl=60)  # Cache mai scurt pentru prescripții
        return jsonify(result), 200
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

        # Track medication usage for popular medications
        track_medication_usage_in_redis(medication_name)

        # Invalidate prescriptions cache
        invalidate_cache("prescriptions:*")

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
    """Onorează o prescripție (doar farmaciștii pot face asta) și scade automat stocul."""
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

        # Găsește medication_id din medication_name
        medication_id = None
        try:
            medications_resp = requests.get(f"{INVENTORY_BASE_URL}/medications", timeout=5)
            if medications_resp.status_code == 200:
                medications = medications_resp.json()
                for med in medications:
                    if med.get("name") == prescription.medication_name:
                        medication_id = med.get("id")
                        break
        except Exception as e:
            app.logger.warning(f"Could not fetch medications to find ID: {e}")

        # Scade stocul automat dacă am găsit medication_id
        if medication_id:
            try:
                deduct_resp = requests.post(
                    f"{INVENTORY_BASE_URL}/pharmacies/{pharmacy_id}/stock/{medication_id}/deduct",
                    json={"quantity": prescription.quantity},
                    timeout=5
                )
                if deduct_resp.status_code != 200:
                    app.logger.warning(f"Could not deduct stock: {deduct_resp.text}")
                    # Nu returnăm eroare, doar logăm - prescripția se onorează oricum
            except Exception as e:
                app.logger.warning(f"Error deducting stock: {e}")
                # Nu returnăm eroare, doar logăm - prescripția se onorează oricum

        prescription.status = PrescriptionStatus.FULFILLED.value
        prescription.pharmacy_id = pharmacy_id
        prescription.pharmacist_id = pharmacist_id
        prescription.fulfilled_at = datetime.utcnow()

        session.commit()
        session.refresh(prescription)

        # Invalidate prescriptions cache
        invalidate_cache("prescriptions:*")

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
        
        # Invalidate prescriptions cache
        invalidate_cache("prescriptions:*")

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
