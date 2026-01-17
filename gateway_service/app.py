from flask import Flask, jsonify, request
import os
import requests
from flask_cors import CORS
import jwt
import time
import redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps

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

# Redis configuration for rate limiting
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
    app.logger.warning("Redis not available, rate limiting disabled")

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

rate_limit_hits = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint']
)


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
    
    # Get roles from both realm_access and resource_access (client roles)
    realm_access = payload.get("realm_access", {})
    realm_roles = realm_access.get("roles", [])
    
    # Also check client roles (resource_access)
    resource_access = payload.get("resource_access", {})
    client_roles = []
    client_id = KEYCLOAK_CLIENT_ID
    if client_id in resource_access:
        client_roles = resource_access[client_id].get("roles", [])
    
    # Combine realm roles and client roles
    roles = realm_roles + client_roles
    
    return payload, username, roles


def rate_limit(max_requests=100, window_seconds=60, per_user=False):
    """
    Rate limiting decorator folosind Redis.
    max_requests: numărul maxim de request-uri
    window_seconds: perioada de timp în secunde
    per_user: dacă True, limitează per utilizator (necesită autentificare)
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not redis_available:
                return f(*args, **kwargs)
            
            # Identifică cheia pentru rate limiting
            if per_user:
                payload, username, _ = get_user_from_token()
                if not username:
                    identifier = request.remote_addr
                else:
                    identifier = f"user:{username}"
            else:
                identifier = request.remote_addr
            
            key = f"ratelimit:{f.__name__}:{identifier}"
            
            # Verifică rate limit
            current = redis_client.get(key)
            if current and int(current) >= max_requests:
                rate_limit_hits.labels(endpoint=f.__name__).inc()
                return jsonify({
                    "error": "rate limit exceeded",
                    "message": f"Maximum {max_requests} requests per {window_seconds} seconds"
                }), 429
            
            # Incrementează contorul
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            pipe.execute()
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


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



@app.route("/api/profiles", methods=["GET"])
@rate_limit(max_requests=200, window_seconds=60)
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

    # Get roles from both realm_access and resource_access (client roles)
    realm_access = payload.get("realm_access", {})
    realm_roles = realm_access.get("roles", [])
    
    # Also check client roles (resource_access)
    resource_access = payload.get("resource_access", {})
    client_roles = []
    client_id = KEYCLOAK_CLIENT_ID
    if client_id in resource_access:
        client_roles = resource_access[client_id].get("roles", [])
    
    # Combine realm roles and client roles
    roles = realm_roles + client_roles
    roles_str = ",".join(roles)
    
    # Log for debugging (both logger and print for visibility)
    log_msg = f"User {username} - Realm roles: {realm_roles}, Client roles: {client_roles}, Combined: {roles}"
    app.logger.info(log_msg)
    print(log_msg, flush=True)  # Print to stdout for Docker logs

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
@rate_limit(max_requests=150, window_seconds=60, per_user=True)
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


@app.route("/api/prescriptions/<int:prescription_id>/cancel", methods=["POST", "OPTIONS"])
def api_cancel_prescription(prescription_id: int):
    if request.method == "OPTIONS":
        return "", 200
    
    payload, username, roles = get_user_from_token()
    if not username or "ADMIN" not in roles:
        return jsonify({"error": "ADMIN role required"}), 403
    
    try:
        resp = requests.post(f"{PRESCRIPTION_BASE_URL}/prescriptions/{prescription_id}/cancel", timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "prescription-service unreachable", "details": str(e)}), 502


# Inventory routes
@app.route("/api/medications", methods=["GET", "OPTIONS"])
@rate_limit(max_requests=300, window_seconds=60)  # Cache-ul face acest endpoint foarte rapid
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


@app.route("/api/medications/popular", methods=["GET", "OPTIONS"])
def api_get_popular_medications():
    """Obține medicamentele cele mai uzuale (optimizat cu cache)."""
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        limit = request.args.get("limit", type=int, default=10)
        resp = requests.get(f"{INVENTORY_BASE_URL}/medications/popular", params={"limit": limit}, timeout=5)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({"error": "inventory-service unreachable", "details": str(e)}), 502


@app.route("/api/medications/<int:medication_id>/stock", methods=["GET", "OPTIONS"])
def api_get_medication_stock_all_pharmacies(medication_id: int):
    """Obține stocul unui medicament în toate farmaciile (optimizat cu cache pentru medicamente uzuale)."""
    if request.method == "OPTIONS":
        return "", 200
    
    try:
        resp = requests.get(f"{INVENTORY_BASE_URL}/medications/{medication_id}/stock", timeout=5)
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
