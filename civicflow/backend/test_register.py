"""
Quick test script to verify /auth/register endpoint
Run with: python test_register.py
"""
import requests
import json

API = "http://localhost:8000"

# Test payload matching frontend exactly
payload = {
    "name": "Test User",
    "email": "test@example.com",
    "phone": None,
    "password": "password123",
    "role": "primary",
    "parent_user_id": None
}

print("=" * 60)
print("Testing POST /auth/register")
print("=" * 60)
print("\nPayload:")
print(json.dumps(payload, indent=2))
print("\n" + "=" * 60)

try:
    response = requests.post(
        f"{API}/auth/register",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 422:
        print("\n⚠️  422 VALIDATION ERROR DETECTED")
        data = response.json()
        if "errors" in data:
            print("\nField Errors:")
            for err in data["errors"]:
                print(f"  - {err['loc']}: {err['msg']} (type: {err['type']})")
    elif response.status_code == 200:
        print("\n✅ Registration successful!")
    
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to backend. Is it running on http://localhost:8000?")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
