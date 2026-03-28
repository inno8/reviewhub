# Task: Create Onboard Page (First-Time User Password Setup)

## Overview
Create an onboarding flow for users logging in for the first time. The flow:
1. User enters email
2. System searches for user in DB
3. If found, welcome user by name and send 5-digit OTP to their email
4. Show OTP input fields
5. On correct OTP, prompt user to set password
6. Update user record in DB and redirect to login

## Tech Stack
- **Backend:** Django + Django REST Framework (in `django_backend/`)
- **Frontend:** Vue 3 + TypeScript + Tailwind (in `frontend/`)
- **Auth:** JWT via djangorestframework-simplejwt

## Backend Changes (Django)

### 1. New Model: `OnboardCode` in `django_backend/users/models.py`

```python
class OnboardCode(models.Model):
    """Temporary OTP codes for first-time user onboarding."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='onboard_codes')
    code = models.CharField(max_length=5)  # 5-digit code
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'onboard_codes'
        indexes = [
            models.Index(fields=['user', 'code']),
        ]
```

Also add to User model:
```python
onboard_completed = models.BooleanField(default=False)
```

Run migrations after schema changes.

### 2. New Views in `django_backend/users/views.py`

Create three endpoints:

#### `POST /api/onboard/check-email/`
- Input: `{ "email": "..." }`
- Find user by email
- If not found: return `{ "found": false }`
- If found and `onboard_completed=True`: return `{ "found": true, "already_onboarded": true }`
- If found and not onboarded:
  - Generate 5-digit code (random, numeric)
  - Save to `OnboardCode` with 15-minute expiry
  - Log code to console (for now): `print(f"[ONBOARD] Code for {email}: {code}")`
  - Return `{ "found": true, "username": user.username, "code_sent": true }`

#### `POST /api/onboard/verify-code/`
- Input: `{ "email": "...", "code": "..." }`
- Find user by email
- Find valid (not used, not expired) OnboardCode for user
- If code matches:
  - Mark code as used
  - Generate short-lived JWT token for password reset (5 min expiry)
  - Return `{ "valid": true, "reset_token": "..." }`
- If invalid: return `{ "valid": false, "error": "Invalid or expired code" }`

#### `POST /api/onboard/set-password/`
- Input: `{ "token": "...", "password": "..." }`
- Verify reset token
- Hash password with Django's `make_password()`
- Update user: `password`, `onboard_completed=True`
- Return `{ "success": true }`

### 3. Register URLs in `django_backend/users/urls.py`
```python
path('onboard/check-email/', OnboardCheckEmailView.as_view()),
path('onboard/verify-code/', OnboardVerifyCodeView.as_view()),
path('onboard/set-password/', OnboardSetPasswordView.as_view()),
```

## Frontend Changes

### 1. New View: `frontend/src/views/OnboardView.vue`

Multi-step form matching existing design (see LoginView.vue for styling):

**Step 1: Email Entry**
- Same card styling as LoginView
- Email input field
- "Continue" button
- Link: "Already have password? Sign in"

**Step 2: OTP Verification** (shown after email found)
- Welcome message: "Welcome, {username}!"
- Subtitle: "We sent a 5-digit code to {email}"
- 5 separate input boxes for OTP (auto-focus next on input)
- "Verify Code" button
- "Resend code" link (rate-limited, 60 second cooldown)

**Step 3: Set Password** (shown after OTP verified)
- Password input
- Confirm password input
- Password requirements hint (8+ chars)
- "Set Password" button

**Step 4: Success**
- Success message with checkmark icon
- Auto-redirect to /login after 3 seconds
- Manual "Go to Login" button

### 2. Add Route in `frontend/src/router/index.ts`
```typescript
import OnboardView from '@/views/OnboardView.vue';
// ...
{ path: '/onboard', name: 'onboard', component: OnboardView, meta: { public: true } },
```

### 3. API calls
Add to appropriate API service or inline in component.

## Design Notes
- Match the existing dark theme from LoginView.vue
- Use same color tokens: `primary`, `surface-container-*`, `on-surface`, etc.
- Use Material Symbols icons
- Add subtle animations for step transitions
- OTP boxes should be large, centered, with auto-advance

## Validation
- Email: valid email format
- OTP: exactly 5 digits
- Password: min 8 chars, must match confirmation

## Testing
After implementation:
1. Start Django backend + Vue frontend
2. Create a test user without password (Django shell or admin)
3. Navigate to /onboard
4. Enter test user email
5. Check console for OTP code
6. Enter OTP
7. Set password
8. Try logging in with new password

## Files to Create/Modify
- `django_backend/users/models.py` (add OnboardCode model, update User)
- `django_backend/users/views.py` (add 3 views)
- `django_backend/users/urls.py` (add 3 routes)
- Run: `python manage.py makemigrations && python manage.py migrate`
- `frontend/src/views/OnboardView.vue` (new)
- `frontend/src/router/index.ts` (add route)

## Commit Message
After implementation: `feat: add onboard page for first-time user password setup`
