import requests

API_URL = "http://localhost:8000/api"

# Try to login with test user
print("Logging in...")
response = requests.post(
    f"{API_URL}/auth/token/",
    json={
        "email": "demo@reviewhub.dev",
        "password": "demo123"
    }
)

if response.status_code == 200:
    data = response.json()
    token = data['access']
    print("Login successful!")
    print(f"Token: {token}")
    
    # Save token
    with open("test_token.txt", "w") as f:
        f.write(token)
    print("Token saved to test_token.txt")
else:
    print(f"Login failed: {response.status_code}")
    print(response.json())
