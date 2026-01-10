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

    roles = [r for r in roles_str.split(",") if r]
    main_role = roles[0] if roles else "USER"

    session = SessionLocal()
    try:
        user = session.query(UserProfile).filter_by(username=username).first()
        if not user:
            user = UserProfile(username=username, role=main_role)
            session.add(user)
            session.commit()
            session.refresh(user)

        return jsonify(
            {"id": user.id, "username": user.username, "role": user.role}
        ), 200
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
