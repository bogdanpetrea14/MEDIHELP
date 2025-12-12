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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
