# ReviewHub

Code review teaching dashboard — transforms daily automated code reviews into structured learning for interns with performance tracking.

## Overview

ReviewHub aggregates code review findings from the `@code-review` agent and presents them in an educational dashboard where:
- Interns learn from real code examples with side-by-side comparisons
- Explanations teach the *why* behind optimizations
- Admins can apply fixes with one click (creates PR)
- Performance tracking shows individual growth over time

## Features

### For Interns
- 📅 Browse reviews by day, week, or month
- 🔍 Side-by-side code comparison (original vs optimized)
- 💡 Detailed explanations with learning resources
- ✅ Mark items as "understood"
- 📞 Request explanation calls (notifies admin via Telegram)

### For Admins
- 🚀 One-click "Apply Fix & Create PR"
- 👥 User management (add interns, assign projects)
- 📊 Performance Insights dashboard
  - Strengths & growth areas per developer
  - Code progression tracking (old vs new)
  - Personalized learning recommendations

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vue.js 3, Tailwind CSS, Vite |
| **Backend** | Node.js, Express, TypeScript |
| **Database** | PostgreSQL, Prisma ORM |
| **Git Integration** | GitHub API (Octokit) |
| **Notifications** | Telegram Bot API |
| **Hosting** | DigitalOcean |

## Design

Designed in Stitch with OpenClaw Dark theme.

**Screens:**
1. Login
2. Dashboard (calendar, findings list)
3. Finding Detail (split code view, explanations)
4. Performance Insights (admin only)
5. User Management (admin only)

**Logo:** Horizontal wordmark (code brackets + lightbulb icon)

## Project Structure

```
reviewhub/
├── frontend/          # Vue.js frontend
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   └── assets/
│   └── package.json
├── backend/           # Express API
│   ├── src/
│   │   ├── routes/
│   │   ├── controllers/
│   │   ├── services/
│   │   └── middleware/
│   ├── prisma/
│   └── package.json
├── docs/              # Documentation
│   ├── API.md
│   ├── DESIGN.md
│   └── DATABASE.md
└── README.md
```

## Getting Started

### Prerequisites
- Node.js 18+
- PostgreSQL 14+
- GitHub Personal Access Token
- Telegram Bot Token

### Installation

```bash
# Clone the repository
git clone https://github.com/inno8/reviewhub.git
cd reviewhub

# Install dependencies
cd frontend && npm install
cd ../backend && npm install

# Setup environment
cp backend/.env.example backend/.env
# Edit .env with your credentials

# Setup database
cd backend && npx prisma migrate dev

# Start development
npm run dev  # in both frontend/ and backend/
```

## License

Proprietary — itec

## Links

- [Stitch Design](https://stitch.withgoogle.com/projects/1695881319703761493)
- [Project Brief](docs/PROJECT_BRIEF.md)
