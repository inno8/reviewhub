# Django Migration Status - Frontend

## ✅ Completed Backend
- Django backend on port 8000
- FastAPI AI engine on port 8001
- JWT authentication configured
- All models and APIs ready

## 🔧 Frontend Changes Needed

### 1. Environment
- ✅ Updated `.env`: `VITE_API_URL=http://localhost:8000/api`

### 2. API Endpoints Mapping

#### Authentication
- OLD: `POST /auth/login` → NEW: `POST /auth/token/`
- Request: `{ email, password }` → `{ username, password }` (Django uses username field)
- Response: `{ token }` → `{ access, refresh }`
- OLD: `GET /auth/me` → NEW: `GET /users/me/`

#### Projects
- ✅ `GET /projects/` - Same
- ✅ `GET /projects/:id/` - Same
- ❌ `GET /projects/:id/branches` - Not implemented yet
- ❌ `POST /projects/from-url` - Not implemented yet

#### Reviews → Evaluations
- OLD: `GET /reviews` → NEW: `GET /evaluations/`
- OLD: `POST /reviews/trigger` → NEW: N/A (webhook-driven)
- ❌ `GET /reviews/calendar` - Not implemented
- ❌ `POST /reviews/import` - Not implemented
- ❌ `POST /reviews/sync-markdown` - Not implemented

#### Findings
- OLD: `GET /findings` → NEW: `GET /evaluations/findings/`
- OLD: `GET /findings/:id` → NEW: `GET /evaluations/findings/:id/`
- ❌ `GET /findings/:id/file-content` - Not implemented
- ❌ `PATCH /findings/:id/understood` - Not implemented
- ❌ `POST /findings/:id/request-explanation` - Not implemented
- ❌ `POST /findings/:id/apply-fix` - Not implemented
- OLD: `PATCH /findings/:id/fixed` → NEW: `POST /evaluations/findings/:id/fix/`

#### Users
- ✅ `GET /users/` - Same
- ✅ `GET /users/me/` - Same
- ✅ `POST /users/register/` - Django has this
- ❌ User project assignment endpoints - Not implemented

#### Performance
- ❌ All performance endpoints - Not implemented yet

#### Skills
- ✅ `GET /skills/categories/` - Works
- ✅ `GET /skills/user/:id/` - Works
- ❌ Breakdown endpoints - Not implemented

### 3. Authentication Flow Changes

**Django JWT requires:**
```javascript
// Login
POST /api/auth/token/
Body: { username: "email@example.com", password: "..." }
Response: { access: "jwt-token", refresh: "refresh-token" }

// Store token
localStorage.setItem('reviewhub_token', response.data.access)

// Use in headers
Authorization: Bearer <access-token>

// Refresh (when access expires)
POST /api/auth/token/refresh/
Body: { refresh: "refresh-token" }
Response: { access: "new-access-token" }
```

### 4. Data Structure Changes

**Review → Evaluation:**
```typescript
// OLD
interface Review {
  id: number
  projectId: number
  commitSha: string
  authorName: string
  // ...
}

// NEW (Django)
interface Evaluation {
  id: number
  project: number  // Just the ID
  commit_sha: string  // Snake case
  author_name: string  // Snake case
  // ...
}
```

**Finding Changes:**
```typescript
// NEW fields
interface Finding {
  // ... existing
  skills: Skill[]  // Array of skill objects
  finding_skills: FindingSkill[]  // Array of {skill, impact_score}
}
```

## 📋 Priority Implementation Tasks

### Phase 1 (Critical - do now)
1. ✅ Update `.env` to port 8000
2. Update `useApi.ts`:
   - Fix auth login endpoint
   - Update evaluations/findings endpoints
   - Handle snake_case ↔ camelCase conversion
3. Test login flow
4. Test evaluations list
5. Test findings list

### Phase 2 (Can defer)
- Calendar view (requires new Django endpoint)
- Manual review triggers (webhook-driven now)
- File content viewer
- Performance tracking
- Skill breakdown

## 🎯 Minimal Working Frontend

To get a basic working version:
1. Fix auth (login, token storage, /users/me/)
2. Show evaluations list (basic table)
3. Show evaluation detail (commit, score, findings)
4. Show findings with skills

Advanced features can be added later.
