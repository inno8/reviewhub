import requests

API_URL = "http://localhost:8000/api"

# Read token from file
with open("test_token.txt", "r") as f:
    token = f.read().strip()

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Test notifications endpoints
print("Testing Notifications API...")
print("=" * 50)

# 1. List notifications
print("\n1. GET /api/notifications/")
response = requests.get(f"{API_URL}/notifications/", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# 2. Get unread count
print("\n2. GET /api/notifications/unread-count/")
response = requests.get(f"{API_URL}/notifications/unread-count/", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# 3. Test recommendations
print("\n3. GET /api/skills/recommendations/")
response = requests.get(f"{API_URL}/skills/recommendations/", headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

print("\n" + "=" * 50)
print("All tests completed!")
