import requests
import time
import json
import base64
import sys

# Configuration
BASE_URL = "http://localhost:8080"
HEADERS = {
    "Content-Type": "application/json"
}

def print_separator(title):
    print("\n" + "=" * 60)
    print(f"   {title}")
    print("=" * 60)

def log_request(method, url, data=None, headers=None):
    print(f"\n\033[94m[REQUEST]\033[0m {method} {url}")
    if headers:
        # Filter out long Authorization tokens for display
        display_headers = headers.copy()
        if "Authorization" in display_headers:
            display_headers["Authorization"] = "Bearer <...truncated...>"
        print(f"   Headers: {display_headers}")
    if data:
        print(f"   Payload: {json.dumps(data, indent=2)}")

def log_response(response):
    color = "\033[92m" if 200 <= response.status_code < 300 else "\033[91m"
    print(f"{color}[RESPONSE]\033[0m Status: {response.status_code}")
    try:
        json_resp = response.json()
        print(f"   Body: {json.dumps(json_resp, indent=2)}")
        return json_resp
    except:
        print(f"   Body (text): {response.text}")
        return None

def generate_dummy_token(username="testuser", roles=["USER"]):
    """Generates a dummy unsigned JWT token for testing."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "preferred_username": username,
        "realm_access": {"roles": roles},
        "exp": int(time.time()) + 3600
    }
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{encoded_header}.{encoded_payload}.dummy_signature"

def test_route(method, endpoint, data=None, headers=None, description=""):
    url = f"{BASE_URL}{endpoint}"
    print(f"\n--- {description} ---")
    log_request(method, endpoint, data, headers)
    
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            resp = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == "OPTIONS":
            resp = requests.options(url, headers=headers, timeout=5)
        else:
            print("Method not supported in test script")
            return None
            
        return log_response(resp)
    except Exception as e:
        print(f"\033[91m[ERROR]\033[0m Connection failed: {e}")
        return None

def main():
    print_separator("MEDIHELP API TEST SUITE")
    print(f"Target: {BASE_URL}")

    # 1. Gateway Health
    test_route("GET", "/health", description="Checking Gateway Health")

    # 2. Create Profile
    new_user = {
        "username": f"user_{int(time.time())}",
        "role": "PATIENT"
    }
    resp_data = test_route("POST", "/api/profiles", data=new_user, headers=HEADERS, description="Creating New User Profile")
    
    user_id = None
    if resp_data and "id" in resp_data:
        user_id = resp_data["id"]

    # 3. Get All Profiles
    test_route("GET", "/api/profiles", description="Fetching All Profiles")

    # 4. Get Specific Profile
    if user_id:
        test_route("GET", f"/api/profiles/{user_id}", description=f"Fetching Profile ID: {user_id}")
    else:
        print("\n[SKIP] Skipping Get Profile by ID (Creation failed)")

    # 5. Auth Route (Mocked)
    print_separator("AUTHENTICATION TEST")
    token = generate_dummy_token(username="doctor_house", roles=["DOCTOR", "ADMIN"])
    auth_headers = HEADERS.copy()
    auth_headers["Authorization"] = f"Bearer {token}"
    
    test_route("GET", "/api/user/me", headers=auth_headers, description="Verifying /api/user/me with Bearer Token")

    # 6. Non-existent route
    test_route("GET", "/api/does_not_exist", description="Testing 404 Behavior")

    print_separator("TESTS COMPLETED")

if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("Please install requests: pip install requests")
        sys.exit(1)
    main()
