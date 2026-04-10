# Project Brief — ReviewHub

## Overview

**Name:** ReviewHub  
**Type:** Web Application (Internal Tool)  
**Status:** Planning  
**Created:** 2026-03-23  

**Mission:** Transform daily automated code reviews into a structured teaching platform for interns, with performance tracking and one-click fix application.

---

## Problem

Interns working on projects receive code review feedback, but:
- Reviews are scattered in markdown files
- No structured way to learn from mistakes
- No tracking of individual progress
- No visibility into strengths/weaknesses over time
- Manual process to apply suggested fixes

---

## Solution

A dashboard that:
1. **Aggregates** daily @code-review findings across all projects
2. **Structures** them by date, category, and difficulty
3. **Teaches** with side-by-side code comparison and explanations
4. **Tracks** individual developer performance over time
5. **Automates** fix application via PR creation

---

## Users & Permissions

| Role | Access |
|------|--------|
| **Admin (inno8)** | Full access: all projects, all users, commit/merge, performance insights, user management |
| **Intern** | Limited: only their commits, only assigned projects, can mark items, request explanation calls |

- No self-registration — admin adds users manually
- Auth: session-based with role system

---

## Core Features

### 1. Project Selector
- Dropdown showing all projects with @code-review enabled
- Filters all views to selected project
- Remembers last selection

### 2. Calendar Navigation
- Browse reviews by Day → Week → Month
- Weekdays only (no weekend data)
- Visual indicators for days with findings
- Quick jump to specific date

### 3. Review Cards (Per Finding)
Each finding displays:

| Element | Description |
|---------|-------------|
| **File path** | Where the issue was found |
| **Branch** | Which branch |
| **Original code** | Full file with problematic snippet **highlighted** |
| **Optimized code** | The improved version |
| **Explanation** | WHY this is better (teaching focus) |
| **Category** | Security, Performance, Code Style, Testing, Architecture, etc. |
| **Difficulty** | Beginner, Intermediate, Advanced |
| **Author** | Who wrote the original code (commit author) |

### 4. Intern Actions
- ✅ **Mark as understood** — visual checkbox (no backend action, just visual state)
- 📞 **Request explanation call** — flags for live walkthrough, **notifies admin via Telegram**

### 5. Admin Actions (Commit & Merge)
*Only visible to admin*

| Step | Action |
|------|--------|
| 1 | Click "Apply Fix" on a finding |
| 2 | System applies optimized code to **source branch** |
| 3 | Creates **PR to main** |
| 4 | Shows PR link |

### 6. Performance Insights (Admin Only)
*Separate page, admin access only*

| Metric | Description |
|--------|-------------|
| **Developer selector** | Pick a team member to analyze |
| **Time period** | Daily, weekly, monthly views |
| **Commit stats** | Number of commits, files changed, lines added/removed |
| **Review stats** | Findings count, categories breakdown, fix rate |
| **Strengths** | Categories where they excel (few/no issues) |
| **Growth areas** | Categories with repeated issues |
| **Trend chart** | Improvement over time |
| **Recommendations** | Books, tutorials, exercises — curated by @code-review based on weaknesses |

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Vue.js 3 + Vite | Modern, reactive, fast dev experience |
| **Styling** | Tailwind CSS | Utility-first, matches team stack |
| **Backend** | Node.js + Express + TypeScript | Good GitHub API support, type safety |
| **Database** | PostgreSQL | Structured data, analytics-friendly |
| **ORM** | Prisma | Type-safe queries, easy migrations |
| **Auth** | Express sessions + bcrypt | Simple, secure |
| **Git Integration** | Octokit (GitHub API) | PR creation, branch operations, commit data |
| **Notifications** | Telegram Bot API | Explanation call alerts |
| **Hosting** | DigitalOcean Droplet | Team standard |
| **CI/CD** | GitHub Actions | Automated deployment |

---

## Database Schema

```sql
-- Users
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) DEFAULT 'intern', -- 'admin' | 'intern'
  telegram_chat_id VARCHAR(50), -- for notifications
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Projects (synced from @code-review config)
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  display_name VARCHAR(200),
  github_owner VARCHAR(100) NOT NULL,
  github_repo VARCHAR(100) NOT NULL,
  code_review_enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW()
);

-- User-Project access
CREATE TABLE user_projects (
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, project_id)
);

-- Daily reviews
CREATE TABLE reviews (
  id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  branch VARCHAR(255) NOT NULL,
  review_date DATE NOT NULL,
  raw_markdown TEXT, -- original @code-review output
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(project_id, branch, review_date)
);

-- Individual findings
CREATE TABLE findings (
  id SERIAL PRIMARY KEY,
  review_id INTEGER REFERENCES reviews(id) ON DELETE CASCADE,
  commit_sha VARCHAR(40),
  commit_author VARCHAR(100), -- Git commit author
  file_path VARCHAR(500) NOT NULL,
  line_start INTEGER,
  line_end INTEGER,
  original_code TEXT NOT NULL,
  optimized_code TEXT NOT NULL,
  explanation TEXT NOT NULL,
  category VARCHAR(50), -- Security, Performance, CodeStyle, Testing, Architecture
  difficulty VARCHAR(20), -- Beginner, Intermediate, Advanced
  pr_created BOOLEAN DEFAULT false,
  pr_url VARCHAR(500),
  created_at TIMESTAMP DEFAULT NOW()
);

-- User interactions with findings
CREATE TABLE user_findings (
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  finding_id INTEGER REFERENCES findings(id) ON DELETE CASCADE,
  marked_understood BOOLEAN DEFAULT false,
  explanation_requested BOOLEAN DEFAULT false,
  explanation_requested_at TIMESTAMP,
  PRIMARY KEY (user_id, finding_id)
);

-- Performance metrics (calculated/cached)
CREATE TABLE performance_metrics (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  project_id INTEGER REFERENCES projects(id),
  period_type VARCHAR(20) NOT NULL, -- 'daily' | 'weekly' | 'monthly'
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  commit_count INTEGER DEFAULT 0,
  finding_count INTEGER DEFAULT 0,
  findings_by_category JSONB, -- {"Security": 2, "Performance": 5}
  findings_by_difficulty JSONB, -- {"Beginner": 3, "Advanced": 1}
  strengths JSONB, -- ["API Design", "Testing"]
  growth_areas JSONB, -- ["Database Architecture", "Security"]
  recommendations JSONB, -- [{"type": "book", "title": "...", "url": "..."}]
  calculated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, project_id, period_type, period_start)
);

-- Indexes for performance
CREATE INDEX idx_findings_commit_author ON findings(commit_author);
CREATE INDEX idx_reviews_date ON reviews(review_date);
CREATE INDEX idx_performance_user ON performance_metrics(user_id);
```

---

## API Endpoints

### Auth
- `POST /api/auth/login` — Login
- `POST /api/auth/logout` — Logout
- `GET /api/auth/me` — Current user

### Projects
- `GET /api/projects` — List accessible projects
- `GET /api/projects/:id` — Project details

### Reviews
- `GET /api/reviews` — List reviews (filter: project, date range, branch)
- `GET /api/reviews/:date` — Reviews for specific date
- `GET /api/reviews/calendar` — Calendar data (dates with findings)

### Findings
- `GET /api/findings` — List findings (filter: project, date, category, difficulty, author)
- `GET /api/findings/:id` — Single finding with full code
- `PATCH /api/findings/:id/understood` — Mark as understood (intern)
- `POST /api/findings/:id/explanation-request` — Request explanation (triggers Telegram notification)
- `POST /api/findings/:id/apply-fix` — Apply fix & create PR (admin only)

### Users (Admin Only)
- `GET /api/users` — List all users
- `POST /api/users` — Create user
- `PATCH /api/users/:id` — Update user
- `DELETE /api/users/:id` — Remove user
- `GET /api/users/:id/projects` — User's assigned projects
- `POST /api/users/:id/projects` — Assign project to user

### Performance (Admin Only)
- `GET /api/performance/:userId` — User performance stats
- `GET /api/performance/:userId/trends` — Performance over time
- `GET /api/performance/:userId/recommendations` — Learning recommendations

---

## User Stories

### Epic 1: Authentication & Access
- As admin, I can log in with my credentials
- As admin, I can add/remove interns
- As admin, I can assign projects to interns
- As intern, I can log in and see only my assigned projects

### Epic 2: Review Dashboard
- As a user, I can select a project from the dropdown
- As a user, I can navigate by day/week/month
- As a user, I can see all findings for a selected date
- As a user, I can view full file with highlighted problem areas
- As a user, I can see the optimized code and explanation
- As a user, I can filter by category and difficulty

### Epic 3: Intern Learning
- As an intern, I can mark findings as "understood"
- As an intern, I can request an explanation call
- As admin, I receive Telegram notification when explanation is requested

### Epic 4: Fix Application (Admin)
- As admin, I can click "Apply Fix" on any finding
- As admin, the system applies the fix to the source branch
- As admin, a PR to main is created automatically
- As admin, I can see the PR link and status

### Epic 5: Performance Insights (Admin)
- As admin, I can view individual developer performance
- As admin, I can see strengths and growth areas
- As admin, I can see learning recommendations
- As admin, I can track improvement trends over time

---

## Design Requirements

### Style Guide
- **Theme:** OpenClaw style
- **Colors:** OpenClaw color scheme (dark mode preferred)
- **Typography:** OpenClaw fonts
- **Icons:** OpenClaw icon set
- **Reference:** GitLab-like split-view for code comparison (see uploaded image)

### Key Screens
1. **Login** — Simple, clean
2. **Dashboard** — Project selector, calendar, findings list
3. **Finding Detail** — Full code view, highlighted snippet, optimized code, explanation
4. **Performance** — Developer stats, charts, recommendations (admin only)
5. **User Management** — Add/edit/remove users, assign projects (admin only)

### Logo
- Create after UI design is approved
- Should match OpenClaw aesthetic
- Simple, recognizable

---

## Team

| Agent | Role |
|-------|------|
| **@code** | Build full application (frontend + backend) |
| **@designer** | UI/UX design in Stitch, then logo |
| **@devops** | Deployment pipeline, DigitalOcean setup, CI/CD |
| **@code-review** | Extended: populate performance insights, generate recommendations |

---

## Integration Points

### @code-review Agent
Must be updated to output structured data:
```json
{
  "branch": "feature/xyz",
  "date": "2026-03-23",
  "findings": [
    {
      "file": "src/utils/auth.js",
      "lineStart": 45,
      "lineEnd": 52,
      "commitSha": "abc123",
      "commitAuthor": "ben",
      "category": "Security",
      "difficulty": "Intermediate",
      "originalCode": "...",
      "optimizedCode": "...",
      "explanation": "..."
    }
  ]
}
```

### Telegram Bot
- Bot token configured in environment
- Sends notification to admin when explanation requested
- Message format: "📞 Explanation requested by {intern} for {finding} in {project}"

### GitHub API
- OAuth app or PAT with repo access
- Permissions: read code, create branches, create PRs

---

## Milestones

### Week 1-2: Foundation
- [ ] Project setup (Vue + Express + PostgreSQL)
- [ ] Database schema & migrations
- [ ] Auth system (login, sessions, roles)
- [ ] Basic UI shell with navigation

### Week 3-4: Core Dashboard
- [ ] Project selector
- [ ] Calendar navigation
- [ ] Review list view
- [ ] Finding detail view with code highlighting

### Week 5-6: Intern Features
- [ ] Mark as understood
- [ ] Request explanation (+ Telegram notification)
- [ ] Filter by category/difficulty

### Week 7-8: Admin Features
- [ ] Apply fix & create PR
- [ ] User management
- [ ] Project assignment

### Week 9-10: Performance Insights
- [ ] Performance metrics calculation
- [ ] Strengths/growth areas analysis
- [ ] Recommendations engine
- [ ] Trend charts

### Week 11-12: Polish & Deploy
- [ ] UI polish
- [ ] Testing
- [ ] CI/CD pipeline
- [ ] Production deployment

---

## Design Feedback (Add During Development)

**1. Learning References in Explanations**
- When showing "Why This Is Better", include links to:
  - Official programming language documentation
  - Relevant articles/tutorials
  - Best practice guides
- Help interns learn from authoritative sources

**2. Performance Insights — Code Progression Tracking**
- Compare new code vs old code written by same user
- Track improvement over time: "Your code in Week 1 vs Week 4"
- Show concrete examples of their growth
- Highlight patterns they've improved on

## Open Questions

*None — all clarified*

---

## Notes

- @code-review output format may need adjustment for structured JSON
- Performance recommendations will be generated by @code-review agent with learning resources
- Start with Amanks Market as pilot project, then expand
