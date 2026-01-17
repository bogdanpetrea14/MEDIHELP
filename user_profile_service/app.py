import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import (
    create_engine,
    text,
    Column,
    Integer,
    String,
)
from sqlalchemy.orm import sessionmaker, declarative_base
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

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(String(50), nullable=False)


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
        "service": "user-profile-service"
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


@app.route("/profiles", methods=["GET"])
def get_profiles():
    session = SessionLocal()
    try:
        users = session.query(UserProfile).all()
        return jsonify([
            {"id": u.id, "username": u.username, "role": u.role}
            for u in users
        ]), 200
    finally:
        session.close()


@app.route("/profiles", methods=["POST"])
def create_profile():
    body = request.get_json() or {}
    username = body.get("username")
    role = body.get("role")

    if not username or not role:
        return jsonify({"error": "username and role required"}), 400

    session = SessionLocal()
    try:
        user = UserProfile(username=username, role=role)
        session.add(user)
        session.commit()
        session.refresh(user)
        return jsonify(
            {"id": user.id, "username": user.username, "role": user.role}
        ), 201
    finally:
        session.close()


@app.route("/profiles/<int:user_id>", methods=["GET"])
def get_profile(user_id: int):
    session = SessionLocal()
    try:
        user = session.get(UserProfile, user_id)
        if not user:
            return jsonify({"error": "not found"}), 404
        return jsonify(
            {"id": user.id, "username": user.username, "role": user.role}
        ), 200
    finally:
        session.close()



@app.route("/me", methods=["GET"])
def me():
    """
    Endpoint intern, apelat DOAR de gateway.

    Gateway trimite:
      - X-Username: username-ul din token
      - X-Roles: lista de roluri (separate prin virgulă)

    user-profile-service:
      - caută profilul după username
      - dacă nu există, îl creează automat, luând primul rol din listă
      - întoarce profilul
    """
    username = request.headers.get("X-Username")
    roles_str = request.headers.get("X-Roles", "")

    if not username:
        return jsonify({"error": "X-Username header required"}), 400

    roles = [r.strip() for r in roles_str.split(",") if r.strip()]
    
    # Log received roles for debugging (both logger and print for visibility)
    log_msg = f"User {username} - Received roles: {roles}"
    app.logger.info(log_msg)
    print(log_msg, flush=True)  # Print to stdout for Docker logs
    
    # Filter out default Keycloak roles
    excluded_roles = {"default-roles-medihelp", "offline_access", "uma_authorization"}
    app_roles = [r for r in roles if r not in excluded_roles]
    
    log_msg2 = f"User {username} - Filtered app roles: {app_roles}"
    app.logger.info(log_msg2)
    print(log_msg2, flush=True)  # Print to stdout for Docker logs
    
    # Priority order for roles (highest to lowest)
    role_priority = ["ADMIN", "DOCTOR", "PHARMACIST", "PATIENT"]
    
    # Find the highest priority role - check in ALL roles first
    main_role = None
    for priority_role in role_priority:
        if priority_role in roles:  # Check in all roles, not just app_roles
            main_role = priority_role
            app.logger.info(f"User {username} - Found priority role: {main_role}")
            break
    
    # If no priority role found, use the first app role (after filtering)
    if main_role is None and app_roles:
        main_role = app_roles[0]
        app.logger.info(f"User {username} - Using first app role: {main_role}")
    elif main_role is None:
        main_role = "USER"
        app.logger.warning(f"User {username} - No valid role found, defaulting to USER. All roles: {roles}")

    session = SessionLocal()
    try:
        user = session.query(UserProfile).filter_by(username=username).first()
        if not user:
            user = UserProfile(username=username, role=main_role)
            session.add(user)
            session.commit()
            session.refresh(user)
        else:
            # Always update role if:
            # 1. Current role is excluded (like "default-roles-medihelp")
            # 2. Current role is not in the priority list (invalid role)
            # 3. We found a valid role and it's different from current
            current_role_excluded = user.role in excluded_roles
            current_role_invalid = user.role not in role_priority
            has_valid_role = main_role in role_priority
            should_update = current_role_excluded or current_role_invalid or (has_valid_role and user.role != main_role)
            
            if should_update:
                old_role = user.role
                user.role = main_role
                session.commit()
                session.refresh(user)
                app.logger.info(f"Updated user {username} role from {old_role} to {main_role} (roles from token: {roles})")

        return jsonify(
            {"id": user.id, "username": user.username, "role": user.role}
        ), 200
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
