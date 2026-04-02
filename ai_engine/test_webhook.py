"""
Test the GitHub webhook flow with a mock commit.
"""
import httpx
import json
from datetime import datetime

# Mock GitHub push webhook payload
webhook_payload = {
    "ref": "refs/heads/feature/v2-ai-mentor",
    "repository": {
        "html_url": "https://github.com/inno8/amanks-market"
    },
    "commits": [
        {
            "id": "abc123def456",
            "message": "Add new product listing feature",
            "timestamp": datetime.now().isoformat(),
            "author": {
                "name": "Yanick",
                "email": "yanick007.dev@gmail.com"
            },
            "added": ["products/new_listing.py"],
            "removed": [],
            "modified": ["products/views.py"]
        }
    ]
}

async def test_webhook():
    """Send a test webhook to the AI engine."""
    async with httpx.AsyncClient() as client:
        # Send webhook
        response = await client.post(
            "http://localhost:8001/api/v1/webhook/github/1",
            headers={
                "X-GitHub-Event": "push",
                "Content-Type": "application/json"
            },
            json=webhook_payload,
            timeout=30.0
        )
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Webhook accepted!")
            print("Check the backend logs for processing status...")
        else:
            print(f"\n❌ Webhook failed: {response.status_code}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_webhook())
