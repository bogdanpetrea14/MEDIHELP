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
    Float,
    ForeignKey,
    CheckConstraint,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import redis
import json

app = Flask(__name__)
CORS(app)

# Database configuration
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


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(String(500))
    unit_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PharmacyStock(Base):
    __tablename__ = "pharmacy_stocks"

    id = Column(Integer, primary_key=True, index=True)
    pharmacy_id = Column(Integer, nullable=False, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    min_threshold = Column(Integer, default=10, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint('quantity >= 0', name='check_quantity_non_negative'),
    )


def init_db():
    """Creează tabelele, dacă nu există."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        app.logger.error(f"Failed to init DB: {e}")


init_db()


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


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "inventory-service",
        "redis": "available" if redis_available else "unavailable"
    }), 200


@app.route("/db-health", methods=["GET"])
def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"db": "ok"}), 200
    except Exception as e:
        return jsonify({"db": "error", "error": str(e)}), 500


@app.route("/medications", methods=["GET"])
def get_medications():
    """Obține toate medicamentele."""
    cache_key = get_cache_key("medications", "all")
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200

    session = SessionLocal()
    try:
        medications = session.query(Medication).all()
        result = [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "unit_price": m.unit_price,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in medications
        ]
        set_cache(cache_key, result)
        return jsonify(result), 200
    finally:
        session.close()


@app.route("/medications", methods=["POST"])
def create_medication():
    """Creează un nou medicament."""
    body = request.get_json() or {}
    name = body.get("name")
    description = body.get("description", "")
    unit_price = body.get("unit_price")

    if not name or unit_price is None:
        return jsonify({"error": "name and unit_price are required"}), 400

    session = SessionLocal()
    try:
        medication = Medication(
            name=name,
            description=description,
            unit_price=float(unit_price)
        )
        session.add(medication)
        session.commit()
        session.refresh(medication)

        invalidate_cache("medications:*")

        return jsonify({
            "id": medication.id,
            "name": medication.name,
            "description": medication.description,
            "unit_price": medication.unit_price,
            "created_at": medication.created_at.isoformat() if medication.created_at else None,
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/medications/<int:medication_id>", methods=["GET"])
def get_medication(medication_id: int):
    """Obține un medicament specific."""
    cache_key = get_cache_key("medication", medication_id)
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200

    session = SessionLocal()
    try:
        medication = session.get(Medication, medication_id)
        if not medication:
            return jsonify({"error": "not found"}), 404

        result = {
            "id": medication.id,
            "name": medication.name,
            "description": medication.description,
            "unit_price": medication.unit_price,
            "created_at": medication.created_at.isoformat() if medication.created_at else None,
        }
        set_cache(cache_key, result)
        return jsonify(result), 200
    finally:
        session.close()


@app.route("/pharmacies/<int:pharmacy_id>/stock", methods=["GET"])
def get_pharmacy_stock(pharmacy_id: int):
    """Obține stocul unei farmacii."""
    cache_key = get_cache_key("pharmacy_stock", pharmacy_id)
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200

    session = SessionLocal()
    try:
        stocks = session.query(PharmacyStock).filter_by(pharmacy_id=pharmacy_id).all()
        medications = {m.id: m for m in session.query(Medication).all()}

        result = [
            {
                "id": s.id,
                "pharmacy_id": s.pharmacy_id,
                "medication_id": s.medication_id,
                "medication_name": medications.get(s.medication_id).name if s.medication_id in medications else None,
                "quantity": s.quantity,
                "min_threshold": s.min_threshold,
                "low_stock": s.quantity <= s.min_threshold,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
            }
            for s in stocks
        ]
        set_cache(cache_key, result, ttl=60)  # Cache mai scurt pentru stoc
        return jsonify(result), 200
    finally:
        session.close()


@app.route("/pharmacies/<int:pharmacy_id>/stock", methods=["POST"])
def add_pharmacy_stock(pharmacy_id: int):
    """Adaugă sau actualizează stocul unei farmacii."""
    body = request.get_json() or {}
    medication_id = body.get("medication_id")
    quantity = body.get("quantity")
    min_threshold = body.get("min_threshold", 10)

    if medication_id is None or quantity is None:
        return jsonify({"error": "medication_id and quantity are required"}), 400

    session = SessionLocal()
    try:
        stock = session.query(PharmacyStock).filter_by(
            pharmacy_id=pharmacy_id,
            medication_id=medication_id
        ).first()

        if stock:
            stock.quantity += int(quantity)
            stock.min_threshold = int(min_threshold)
            stock.last_updated = datetime.utcnow()
        else:
            stock = PharmacyStock(
                pharmacy_id=pharmacy_id,
                medication_id=medication_id,
                quantity=int(quantity),
                min_threshold=int(min_threshold)
            )
            session.add(stock)

        session.commit()
        session.refresh(stock)

        invalidate_cache(f"pharmacy_stock:{pharmacy_id}")

        return jsonify({
            "id": stock.id,
            "pharmacy_id": stock.pharmacy_id,
            "medication_id": stock.medication_id,
            "quantity": stock.quantity,
            "min_threshold": stock.min_threshold,
            "last_updated": stock.last_updated.isoformat() if stock.last_updated else None,
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/pharmacies/<int:pharmacy_id>/stock/<int:medication_id>/deduct", methods=["POST"])
def deduct_stock(pharmacy_id: int, medication_id: int):
    """Scade cantitatea din stoc (când se onorează o prescripție)."""
    body = request.get_json() or {}
    quantity = body.get("quantity", 1)

    session = SessionLocal()
    try:
        stock = session.query(PharmacyStock).filter_by(
            pharmacy_id=pharmacy_id,
            medication_id=medication_id
        ).first()

        if not stock:
            return jsonify({"error": "stock not found"}), 404

        if stock.quantity < quantity:
            return jsonify({"error": "insufficient stock"}), 400

        stock.quantity -= int(quantity)
        stock.last_updated = datetime.utcnow()
        session.commit()
        session.refresh(stock)

        invalidate_cache(f"pharmacy_stock:{pharmacy_id}")

        return jsonify({
            "id": stock.id,
            "pharmacy_id": stock.pharmacy_id,
            "medication_id": stock.medication_id,
            "quantity": stock.quantity,
            "min_threshold": stock.min_threshold,
            "last_updated": stock.last_updated.isoformat() if stock.last_updated else None,
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/pharmacies/<int:pharmacy_id>/stock/low", methods=["GET"])
def get_low_stock(pharmacy_id: int):
    """Obține medicamentele cu stoc scăzut."""
    session = SessionLocal()
    try:
        stocks = session.query(PharmacyStock).filter_by(pharmacy_id=pharmacy_id).all()
        medications = {m.id: m for m in session.query(Medication).all()}

        low_stocks = [
            {
                "id": s.id,
                "pharmacy_id": s.pharmacy_id,
                "medication_id": s.medication_id,
                "medication_name": medications.get(s.medication_id).name if s.medication_id in medications else None,
                "quantity": s.quantity,
                "min_threshold": s.min_threshold,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
            }
            for s in stocks if s.quantity <= s.min_threshold
        ]

        return jsonify(low_stocks), 200
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
