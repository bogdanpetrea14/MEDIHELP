from flask import Flask, jsonify, request
import os
import requests
from flask_cors import CORS
import jwt
import time

app = Flask(__name__)

CORS(
    app,
    resources={r"/api/*": {
        "origins": ["http://localhost:8082"],
        "allow_headers": ["Authorization", "Content-Type"],
        "methods": ["GET", "POST", "OPTIONS"]
    }},
)

USER_PROFILE_BASE_URL = os.environ.get(
    "USER_PROFILE_BASE_URL",
    "http://user-profile-service:5000",
)
PRESCRIPTION_BASE_URL = os.environ.get(
    "PRESCRIPTION_BASE_URL",
    "http://prescription-service:5000",
)
INVENTORY_BASE_URL = os.environ.get(
    "INVENTORY_BASE_URL",
    "http://inventory-service:5000",
)
PHARMACY_BASE_URL = os.environ.get(
    "PHARMACY_BASE_URL",
    "http://pharmacy-service:5000",
)

KEYCLOAK_BASE_URL = os.environ.get(
    "KEYCLOAK_BASE_URL",
    "http://keycloak-service:8080",
)
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "medihelp")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "medihelp-frontend")


def parse_token_no_verify(access_token: str):
    """
    Decodăm JWT-ul fără să verificăm semnătura (demo only).
    Verificăm doar exp-ul, ca să nu fie expirat.
    """
    try:
        payload = jwt.decode(
            access_token,
            options={"verify_signature": False, "verify_aud": False},
            algorithms=["RS256", "HS256"],
        )
    except Exception as e:
        app.logger.error(f"Failed to decode token: {e}")
        return None, "decode_failed"

    exp = payload.get("exp")
    now = int(time.time())
    if exp is not None and exp < now:
        return None, "expired"

    return payload, None


def get_user_from_token():
    """Extrage user info din token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None, None

    token = auth_header.split(" ", 1)[1]
    payload, err = parse_token_no_verify(token)
    if not payload:
        return None, None, None

    username = payload.get("preferred_username") or payload.get("sub")
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    
    return payload, username, roles


def require_role(allowed_roles):
    """Decorator pentru a verifica rolul."""
    def decorator(f):
        def wrapper(*args, **kwargs):
            payload, username, roles = get_user_from_token()
            if not username:
                return jsonify({"error": "authentication required"}), 401
            
            if not any(role in allowed_roles for role in roles):
                return jsonify({"error": "insufficient permissions"}), 403
            
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "gateway-service"}), 200



@app.route("/api/profiles", methods=["GET"])
def api_get_profiles():
    try:
        resp = requests.get(f"{USER_PROFILE_BASE_URL}/profiles", timeout=3)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "user-profile-service unreachable",
                    "details": str(e),
                }
            ),
            502,
        )


@app.route("/api/profiles", methods=["POST"])
def api_create_profile():
    try:
        resp = requests.post(
            f"{USER_PROFILE_BASE_URL}/profiles",
            json=request.get_json(),
            timeout=3,
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "user-profile-service unreachable",
                    "details": str(e),
                }
            ),
            502,
        )


@app.route("/api/profiles/<int:user_id>", methods=["GET"])
def api_get_profile(user_id: int):
    try:
        resp = requests.get(
            f"{USER_PROFILE_BASE_URL}/profiles/{user_id}",
            timeout=3,
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "user-profile-service unreachable",
                    "details": str(e),
                }
            ),
            502,
        )



@app.route("/api/user/me", methods=["GET", "OPTIONS"])
def api_user_me():
    """
    Endpoint protejat: cere Authorization: Bearer <access_token>.

    1. Decodăm JWT-ul fără verificare de semnătură (dar verificăm exp).
    2. Extragem username + roluri (realm_access.roles).
    3. Apelează user-profile-service /me, trimițând username + roluri în headere.
    4. user-profile-service creează automat profilul dacă nu există.
    """

    if request.method == "OPTIONS":
        return "", 200

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return (
            jsonify({"error": "missing or invalid Authorization header"}),
            401,
        )

    token = auth_header.split(" ", 1)[1]

    payload, err = parse_token_no_verify(token)
    if not payload:
        return jsonify({"error": "invalid or expired token", "reason": err}), 401

    username = payload.get("preferred_username") or payload.get("sub")
    if not username:
        return jsonify({"error": "username not found in token"}), 400

    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    roles_str = ",".join(roles)

    headers = {
        "X-Username": username,
        "X-Roles": roles_str,
    }

    try:
        resp = requests.get(
            f"{USER_PROFILE_BASE_URL}/me",
            headers=headers,
            timeout=5,
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return (
            jsonify(
                {
                    "error": "user-profile-service unreachable",
                    "details": str(e),
                }
            ),
            502,
        )


# Prescription routes
@app.route("/api/prescriptions", methods=["GET", "OPTIONS"])
def api_get_prescriptions():
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        params = dict(request.args)
        resp = requests.get(f"{PRESCRIPTION_BASE_URL}/prescriptions", params=params, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "prescription-service unreachable", "details": str(e)}), 502


@app.route("/api/prescriptions", methods=["POST"])
def api_create_prescription():
    payload, username, roles = get_user_from_token()
    if not username or "DOCTOR" not in roles:
        return jsonify({"error": "DOCTOR role required"}), 403
    
    try:
        body = request.get_json() or {}
        resp = requests.post(f"{PRESCRIPTION_BASE_URL}/prescriptions", json=body, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "prescription-service unreachable", "details": str(e)}), 502


@app.route("/api/prescriptions/<int:prescription_id>", methods=["GET"])
def api_get_prescription(prescription_id: int):
    try:
        resp = requests.get(f"{PRESCRIPTION_BASE_URL}/prescriptions/{prescription_id}", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "prescription-service unreachable", "details": str(e)}), 502


@app.route("/api/prescriptions/<int:prescription_id>/fulfill", methods=["POST"])
def api_fulfill_prescription(prescription_id: int):
    payload, username, roles = get_user_from_token()
    if not username or "PHARMACIST" not in roles:
        return jsonify({"error": "PHARMACIST role required"}), 403
    
    try:
        body = request.get_json() or {}
        resp = requests.post(f"{PRESCRIPTION_BASE_URL}/prescriptions/{prescription_id}/fulfill", json=body, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "prescription-service unreachable", "details": str(e)}), 502


# Inventory routes
@app.route("/api/medications", methods=["GET", "OPTIONS"])
def api_get_medications():
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        resp = requests.get(f"{INVENTORY_BASE_URL}/medications", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


@app.route("/api/medications", methods=["POST"])
def api_create_medication():
    payload, username, roles = get_user_from_token()
    if not username or "ADMIN" not in roles:
        return jsonify({"error": "ADMIN role required"}), 403
    
    try:
        body = request.get_json() or {}
        resp = requests.post(f"{INVENTORY_BASE_URL}/medications", json=body, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


@app.route("/api/medications/<int:medication_id>", methods=["GET"])
def api_get_medication(medication_id: int):
    try:
        resp = requests.get(f"{INVENTORY_BASE_URL}/medications/{medication_id}", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacies/<int:pharmacy_id>/stock", methods=["GET", "OPTIONS"])
def api_get_pharmacy_stock(pharmacy_id: int):
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        resp = requests.get(f"{INVENTORY_BASE_URL}/pharmacies/{pharmacy_id}/stock", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacies/<int:pharmacy_id>/stock", methods=["POST"])
def api_add_pharmacy_stock(pharmacy_id: int):
    payload, username, roles = get_user_from_token()
    if not username or "PHARMACIST" not in roles:
        return jsonify({"error": "PHARMACIST role required"}), 403
    
    try:
        body = request.get_json() or {}
        resp = requests.post(f"{INVENTORY_BASE_URL}/pharmacies/{pharmacy_id}/stock", json=body, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacies/<int:pharmacy_id>/stock/low", methods=["GET"])
def api_get_low_stock(pharmacy_id: int):
    try:
        resp = requests.get(f"{INVENTORY_BASE_URL}/pharmacies/{pharmacy_id}/stock/low", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


# Pharmacy routes
@app.route("/api/pharmacies", methods=["GET", "OPTIONS"])
def api_get_pharmacies():
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        params = dict(request.args)
        resp = requests.get(f"{PHARMACY_BASE_URL}/pharmacies", params=params, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "pharmacy-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacies", methods=["POST"])
def api_create_pharmacy():
    payload, username, roles = get_user_from_token()
    if not username or "ADMIN" not in roles:
        return jsonify({"error": "ADMIN role required"}), 403
    
    try:
        body = request.get_json() or {}
        resp = requests.post(f"{PHARMACY_BASE_URL}/pharmacies", json=body, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "pharmacy-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacies/<int:pharmacy_id>", methods=["GET"])
def api_get_pharmacy(pharmacy_id: int):
    try:
        resp = requests.get(f"{PHARMACY_BASE_URL}/pharmacies/{pharmacy_id}", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "pharmacy-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacies/<int:pharmacy_id>/pharmacists", methods=["GET"])
def api_get_pharmacy_pharmacists(pharmacy_id: int):
    try:
        resp = requests.get(f"{PHARMACY_BASE_URL}/pharmacies/{pharmacy_id}/pharmacists", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "pharmacy-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacists", methods=["GET", "OPTIONS"])
def api_get_pharmacists():
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        params = dict(request.args)
        resp = requests.get(f"{PHARMACY_BASE_URL}/pharmacists", params=params, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "pharmacy-service unreachable", "details": str(e)}), 502


@app.route("/api/pharmacists", methods=["POST"])
def api_create_pharmacist():
    payload, username, roles = get_user_from_token()
    if not username or "ADMIN" not in roles:
        return jsonify({"error": "ADMIN role required"}), 403
    
    try:
        body = request.get_json() or {}
        resp = requests.post(f"{PHARMACY_BASE_URL}/pharmacists", json=body, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "pharmacy-service unreachable", "details": str(e)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
