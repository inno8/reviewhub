# ReviewHub — Project Brief

## Mission

Transform daily automated code reviews into a structured teaching platform for interns, with performance tracking and one-click fix application.

## Users & Permissions

| Role | Access |
|------|--------|
| **Admin (inno8)** | Full: all projects, all users, commit/merge, performance insights, user management |
| **Intern** | Limited: only their commits, only assigned projects, can mark items, request explanation calls |

## Core Features

### 1. Review Dashboard
- Project selector (multi-project support)
- Calendar navigation (day/week/month, weekdays only)
- Finding cards with badges (category, difficulty)
- Filters by category, difficulty, author

### 2. Finding Detail View
- Full file with highlighted problematic lines
- Side-by-side comparison (original vs optimized)
- "Why This Is Better" explanation
- **Learning references** (links to official docs, tutorials)
- Mark as understood (visual only)
- Request explanation call → Telegram notification

### 3. Apply Fix & Create PR (Admin)
- Applies optimized code to source branch
- Creates PR to main
- Shows PR link

### 4. Performance Insights (Admin Only)
- Per-developer stats (commits, findings, fix rate)
- Strengths & growth areas
- **Code progression tracking** (compare old vs new code)
- Personalized learning recommendations

### 5. User Management (Admin Only)
- Add/remove interns (no self-registration)
- Assign projects to users
- Role management

## Tech Stack

- **Frontend:** Vue.js 3 + Tailwind CSS + Vite
- **Backend:** Node.js + Express + TypeScript
- **Database:** PostgreSQL + Prisma
- **Git:** GitHub API (Octokit)
- **Notifications:** Telegram Bot API
- **Hosting:** DigitalOcean

## Database Schema

See `backend/prisma/schema.prisma` for full schema.

Key tables:
- `users` — with roles (admin/intern)
- `projects` — linked to GitHub repos
- `user_projects` — access control
- `reviews` — daily review per branch
- `findings` — individual code issues
- `user_findings` — mark as understood, explanation requested
- `performance_metrics` — cached performance data

## Design

**Stitch Project:** https://stitch.withgoogle.com/projects/1695881319703761493

**Style:** OpenClaw Dark
- Primary: #58A6FF
- Background: #0D1117
- Font: Inter

**Logo:** Horizontal wordmark (2nd variation)
- Icon: code brackets + lightbulb
- Text: "ReviewHub." in Inter

## Development Notes

1. **Learning References in Explanations**
   - Include links to official language docs
   - Link relevant tutorials/articles
   - Help interns learn from authoritative sources

2. **Code Progression Tracking**
   - Compare new code vs old code by same user
   - Track improvement over time
   - Show concrete examples of growth

## API Endpoints

### Auth
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Reviews
- `GET /api/reviews` — list (filters: project, date, branch)
- `GET /api/reviews/calendar` — dates with findings

### Findings
- `GET /api/findings` — list
- `GET /api/findings/:id` — detail with full code
- `PATCH /api/findings/:id/understood` — mark understood
- `POST /api/findings/:id/explanation-request` — request call
- `POST /api/findings/:id/apply-fix` — create PR (admin)

### Users (Admin)
- `GET /api/users`
- `POST /api/users`
- `PATCH /api/users/:id`
- `DELETE /api/users/:id`

### Performance (Admin)
- `GET /api/performance/:userId`
- `GET /api/performance/:userId/recommendations`

## Milestones

1. **Foundation** (Week 1-2): Project setup, auth, basic UI
2. **Core Dashboard** (Week 3-4): Calendar, findings, code view
3. **Intern Features** (Week 5-6): Mark understood, request explanation
4. **Admin Features** (Week 7-8): Apply fix, user management
5. **Performance Insights** (Week 9-10): Analytics, recommendations
6. **Polish & Deploy** (Week 11-12): Testing, CI/CD, production
