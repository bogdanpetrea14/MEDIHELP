from flask import Flask, jsonify, request
import os
import requests

app = Flask(__name__)

# Microservicii interne
USER_PROFILE_BASE_URL = os.environ.get(
    "USER_PROFILE_BASE_URL",
    "http://user-profile-service:5000"
)

# Keycloak config (SSO)
KEYCLOAK_BASE_URL = os.environ.get(
    "KEYCLOAK_BASE_URL",
    "http://keycloak-service:8080"
)
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "medihelp")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "medihelp-frontend")


def get_userinfo_from_token(access_token: str):
    """
    Apelează endpoint-ul /userinfo din Keycloak cu token-ul primit de la client.
    Keycloak validează semnătura și expirarea token-ului.
    """
    url = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=5)
    if resp.status_code != 200:
        return None
    return resp.json()


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "gateway-service"
    }), 200


# ------- Forward simplu către user-profile-service (lista profiluri) --------

@app.route("/api/profiles", methods=["GET"])
def api_get_profiles():
    try:
        resp = requests.get(f"{USER_PROFILE_BASE_URL}/profiles", timeout=3)
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({
            "error": "user-profile-service unreachable",
            "details": str(e)
        }), 502


@app.route("/api/profiles", methods=["POST"])
def api_create_profile():
    try:
        resp = requests.post(
            f"{USER_PROFILE_BASE_URL}/profiles",
            json=request.get_json(),
            timeout=3
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({
            "error": "user-profile-service unreachable",
            "details": str(e)
        }), 502


@app.route("/api/profiles/<int:user_id>", methods=["GET"])
def api_get_profile(user_id: int):
    try:
        resp = requests.get(
            f"{USER_PROFILE_BASE_URL}/profiles/{user_id}",
            timeout=3
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({
            "error": "user-profile-service unreachable",
            "details": str(e)
        }), 502


# ---------------- SSO + management de roluri: /api/user/me ------------------

@app.route("/api/user/me", methods=["GET"])
def api_user_me():
    """
    Endpoint protejat: cere Authorization: Bearer <access_token>.

    1. Trimite token-ul la Keycloak (/userinfo) să-l valideze.
    2. Extrage username + roluri.
    3. Apelează user-profile-service /me, trimițând username + roluri în headere.
    4. user-profile-service creează automat profilul dacă nu există.
    """

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "missing or invalid Authorization header"}), 401

    token = auth_header.split(" ", 1)[1]

    # Pas 1: validăm token-ul via Keycloak userinfo
    userinfo = get_userinfo_from_token(token)
    if not userinfo:
        return jsonify({"error": "invalid or expired token"}), 401

    # Exemplu de câmpuri obișnuite în userinfo:
    # sub, preferred_username, email, name, given_name, family_name, etc.
    username = userinfo.get("preferred_username") or userinfo.get("sub")
    if not username:
        return jsonify({"error": "username not found in token"}), 400

    # Rolurile vin de obicei în claim-ul realm_access.roles
    realm_access = userinfo.get("realm_access", {})
    roles = realm_access.get("roles", [])
    roles_str = ",".join(roles)

    # Pas 3: apelăm /me în user-profile-service
    headers = {
        "X-Username": username,
        "X-Roles": roles_str
    }

    try:
        resp = requests.get(
            f"{USER_PROFILE_BASE_URL}/me",
            headers=headers,
            timeout=5
        )
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        return jsonify({
            "error": "user-profile-service unreachable",
            "details": str(e)
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
