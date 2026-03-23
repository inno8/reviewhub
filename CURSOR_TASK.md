# ReviewHub — Phase 2: Core Dashboard

## Overview

Wire up the frontend to the backend API. Replace all mock/placeholder data with real API calls. Make the dashboard fully functional with working filters, calendar navigation, and code display.

## Current State

- ✅ Backend running on port 3000
- ✅ Frontend running on port 5174
- ✅ SQLite database with seed data (3 findings, 3 users, 1 project)
- ✅ Auth endpoints working
- ✅ UI components scaffolded

## Phase 2 Tasks

### 1. API Integration Setup

**Update `frontend/src/composables/useApi.ts`:**
- Configure axios with base URL (`http://localhost:3000/api`)
- Add JWT token interceptor (read from localStorage)
- Add response interceptor for 401 → redirect to login
- Export typed API methods

```typescript
// Example structure
export const api = {
  auth: {
    login: (email: string, password: string) => axios.post('/auth/login', { email, password }),
    me: () => axios.get('/auth/me'),
    logout: () => axios.post('/auth/logout'),
  },
  projects: {
    list: () => axios.get('/projects'),
    get: (id: number) => axios.get(`/projects/${id}`),
  },
  reviews: {
    list: (params: ReviewFilters) => axios.get('/reviews', { params }),
    calendar: (projectId: number, month: string) => axios.get('/reviews/calendar', { params: { projectId, month } }),
  },
  findings: {
    list: (params: FindingFilters) => axios.get('/findings', { params }),
    get: (id: number) => axios.get(`/findings/${id}`),
    markUnderstood: (id: number) => axios.patch(`/findings/${id}/understood`),
    requestExplanation: (id: number) => axios.post(`/findings/${id}/request-explanation`),
  },
  users: {
    list: () => axios.get('/users'),
    create: (data: CreateUser) => axios.post('/users', data),
    update: (id: number, data: UpdateUser) => axios.patch(`/users/${id}`, data),
    delete: (id: number) => axios.delete(`/users/${id}`),
  },
  performance: {
    get: (userId: number, params: PerformanceParams) => axios.get(`/performance/${userId}`, { params }),
  },
};
```

### 2. Auth Store (`frontend/src/stores/auth.ts`)

- Implement login/logout with API calls
- Store JWT in localStorage
- Load user on app init (check if token exists)
- Expose `isAdmin` computed property

### 3. Projects Store (`frontend/src/stores/projects.ts`)

- Fetch projects from API on init
- Store selected project ID
- Persist selection in localStorage

### 4. Findings Store (`frontend/src/stores/findings.ts`)

- Fetch findings with filters (project, date, category, difficulty, author)
- Implement pagination
- Cache finding details

### 5. Login View (`frontend/src/views/LoginView.vue`)

- Wire up form to auth store
- Handle errors (show message)
- Redirect to dashboard on success
- Show loading state during login

### 6. Dashboard View (`frontend/src/views/DashboardView.vue`)

- Fetch findings on mount and when filters change
- Working project selector (dropdown)
- Working date picker (calendar component)
- Working filters (category, difficulty, author)
- Show loading skeleton while fetching
- Show "No findings" message when empty

### 7. Calendar Widget (`frontend/src/components/calendar/CalendarWidget.vue`)

- Fetch calendar data from API (dates with reviews)
- Highlight dates that have findings
- Emit selected date to parent
- Navigate months (prev/next buttons)

### 8. Finding Card (`frontend/src/components/findings/FindingCard.vue`)

- Display real data from API
- Show author avatar (or initials fallback)
- Click navigates to finding detail

### 9. Finding Detail View (`frontend/src/views/FindingDetailView.vue`)

- Fetch finding by ID from route params
- Display full original and optimized code with syntax highlighting
- Parse and display references (links to docs/articles)
- "Mark as understood" checkbox → API call
- "Request Explanation" button → API call + success toast
- "Apply Fix & Create PR" button (admin only) → placeholder for Phase 3

### 10. Code Comparison Component (`frontend/src/components/findings/CodeComparison.vue`)

- Use highlight.js for syntax highlighting
- Detect language from file extension
- Show line numbers
- Highlight changed lines (red for original problems, green for fixes)
- Full file view with scroll

### 11. Backend Fixes (if needed)

**Check and fix these endpoints:**

`GET /api/reviews/calendar`
- Input: `projectId`, `month` (YYYY-MM)
- Output: `{ dates: ['2026-03-23', '2026-03-22', ...] }` (dates with findings)

`GET /api/findings`
- Input: `projectId`, `date`, `category`, `difficulty`, `author`, `page`, `limit`
- Output: `{ findings: [...], total: number, page: number, totalPages: number }`

`GET /api/findings/:id`
- Include full code (originalCode, optimizedCode)
- Include parsed references
- Include review info (branch, date)

`PATCH /api/findings/:id/understood`
- Toggle `markedUnderstood` for current user
- Return updated state

`POST /api/findings/:id/request-explanation`
- Set `explanationRequested: true` for current user
- Send Telegram notification (skip if no bot token configured)
- Return success

### 12. Environment

**Frontend `.env`:**
```
VITE_API_URL=http://localhost:3000/api
```

## Testing Checklist

- [ ] Login with admin@reviewhub.dev / admin123
- [ ] See dashboard with project selector
- [ ] Calendar shows March 23 highlighted (has findings)
- [ ] Click date → findings list updates
- [ ] Filter by category → list filters
- [ ] Click finding card → detail view opens
- [ ] See code comparison with syntax highlighting
- [ ] Click "Mark as understood" → checkbox saves
- [ ] Click "Request Explanation" → toast shows success
- [ ] Logout → redirects to login

## DO NOT

- Do not change the database schema
- Do not add new dependencies without need
- Do not skip TypeScript types
- Do not hardcode API URLs (use env variable)
