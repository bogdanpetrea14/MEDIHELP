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

# Database configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "medihelp_db")
DB_USER = os.environ.get("DB_USER", "admin123")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "admin123")

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


def track_medication_usage(medication_name: str):
    """Incrementează contorul de utilizare pentru un medicament (pentru tracking medicamente uzuale)."""
    if not redis_available:
        return
    try:
        # Folosim un sorted set pentru a ține top medicamente
        key = "medications:popularity"
        redis_client.zincrby(key, 1, medication_name)
        # Setăm TTL pentru sorted set la 30 zile
        redis_client.expire(key, 2592000)
    except:
        pass


def get_popular_medications_from_redis(limit: int = 10):
    """Obține medicamentele cele mai uzuale din cache."""
    if not redis_available:
        return []
    try:
        key = "medications:popularity"
        # Obține top N medicamente (cu score descrescător)
        popular = redis_client.zrevrange(key, 0, limit - 1, withscores=True)
        return [{"name": name, "usage_count": int(score)} for name, score in popular]
    except:
        return []


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "inventory-service",
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


@app.route("/medications", methods=["GET"])
def get_medications():
    """Obține toate medicamentele. Cache-uiește medicamentele uzuale cu prioritate."""
    cache_key = get_cache_key("medications", "all")
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200

    session = SessionLocal()
    try:
        medications = session.query(Medication).all()
        
        # Obține medicamentele populare pentru a le marca
        popular_names = {m["name"] for m in get_popular_medications_from_redis(20)}
        
        result = [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "unit_price": m.unit_price,
                "is_popular": m.name in popular_names,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in medications
        ]
        
        # Cache mai lung pentru lista completă (se schimbă rar)
        set_cache(cache_key, result, ttl=600)  # 10 minute
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


@app.route("/medications/popular", methods=["GET"])
def get_popular_medications():
    """Obține medicamentele cele mai uzuale (bazat pe prescripții)."""
    limit = request.args.get("limit", type=int, default=10)
    cache_key = get_cache_key("medications", "popular", limit)
    
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200
    
    # Obține medicamentele populare din Redis
    popular_names = get_popular_medications_from_redis(limit)
    
    if not popular_names:
        # Dacă nu avem date în Redis, returnăm medicamentele generale
        session = SessionLocal()
        try:
            medications = session.query(Medication).limit(limit).all()
            result = [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "unit_price": m.unit_price,
                    "is_popular": False,
                    "usage_count": 0
                }
                for m in medications
            ]
        finally:
            session.close()
    else:
        # Găsește medicamentele din baza de date pentru medicamentele populare
        session = SessionLocal()
        try:
            popular_dict = {p["name"]: p["usage_count"] for p in popular_names}
            medication_names = list(popular_dict.keys())
            
            medications = session.query(Medication).filter(
                Medication.name.in_(medication_names)
            ).all()
            
            medication_map = {m.name: m for m in medications}
            result = []
            for name, count in popular_dict.items():
                if name in medication_map:
                    m = medication_map[name]
                    result.append({
                        "id": m.id,
                        "name": m.name,
                        "description": m.description,
                        "unit_price": m.unit_price,
                        "is_popular": True,
                        "usage_count": count
                    })
            
            # Cache pentru 1 oră (medicamentele populare se schimbă rar)
            set_cache(cache_key, result, ttl=3600)
        finally:
            session.close()
    
    return jsonify(result), 200


@app.route("/medications/track-usage", methods=["POST"])
def track_medication_usage_endpoint():
    """Endpoint pentru tracking utilizare medicamente (apelat de prescription-service)."""
    body = request.get_json() or {}
    medication_name = body.get("medication_name")
    
    if not medication_name:
        return jsonify({"error": "medication_name is required"}), 400
    
    track_medication_usage(medication_name)
    return jsonify({"message": "usage tracked"}), 200


@app.route("/medications/<int:medication_id>/stock", methods=["GET"])
def get_medication_stock_all_pharmacies(medication_id: int):
    """Obține stocul unui medicament în toate farmaciile (optimizat cu cache pentru medicamente uzuale)."""
    cache_key = get_cache_key("medication_stock", medication_id, "all_pharmacies")
    
    cached = get_from_cache(cache_key)
    if cached:
        return jsonify(cached), 200
    
    session = SessionLocal()
    try:
        # Obține medicamentul
        medication = session.get(Medication, medication_id)
        if not medication:
            return jsonify({"error": "medication not found"}), 404
        
        # Obține stocul pentru acest medicament în toate farmaciile
        stocks = session.query(PharmacyStock).filter_by(medication_id=medication_id).all()
        
        result = [
            {
                "pharmacy_id": s.pharmacy_id,
                "medication_id": s.medication_id,
                "medication_name": medication.name,
                "quantity": s.quantity,
                "min_threshold": s.min_threshold,
                "low_stock": s.quantity <= s.min_threshold,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
            }
            for s in stocks
        ]
        
        # Cache mai lung pentru medicamente uzuale (verificăm dacă e popular)
        is_popular = medication.name in [m["name"] for m in get_popular_medications_from_redis(20)]
        ttl = 300 if is_popular else 60  # 5 minute pentru populare, 1 minut pentru rest
        
        set_cache(cache_key, result, ttl=ttl)
        return jsonify(result), 200
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

        # Invalidate cache pentru stoc farmacie și stoc medicament în toate farmaciile
        invalidate_cache(f"pharmacy_stock:{pharmacy_id}")
        invalidate_cache(f"medication_stock:{medication_id}:*")

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

        # Invalidate cache pentru stoc farmacie și stoc medicament în toate farmaciile
        invalidate_cache(f"pharmacy_stock:{pharmacy_id}")
        invalidate_cache(f"medication_stock:{medication_id}:*")

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
