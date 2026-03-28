import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()

from users.models import User

# Delete old test user if exists
User.objects.filter(email="demo@reviewhub.dev").delete()

# Create new test user
user = User.objects.create_user(
    email="demo@reviewhub.dev",
    username="demo",
    password="demo123",
    role="developer"
)

print(f"Created user: {user.email}")
print(f"Password: demo123")
print(f"ID: {user.id}")
