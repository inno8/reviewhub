import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reviewhub.settings')
django.setup()

from users.models import User

print("=" * 60)
print("USERS IN DATABASE")
print("=" * 60)

users = User.objects.all()
if users:
    for user in users:
        print(f"ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Username: {user.username}")
        print(f"  Active: {user.is_active}")
        print(f"  Role: {user.role}")
        print()
else:
    print("No users found!")
    print("\nCreating test user...")
    
    user = User.objects.create_user(
        email="test@example.com",
        username="testuser",
        password="testpass123",
        role="ADMIN"
    )
    print(f"Created user: {user.email}")
