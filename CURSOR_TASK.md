# ReviewHub — Development Task

## Project Overview

Build a code review teaching dashboard that transforms daily automated code reviews into structured learning for interns.

**Repository:** https://github.com/inno8/reviewhub
**Design:** https://stitch.withgoogle.com/projects/1695881319703761493

## Tech Stack (Required)

- **Frontend:** Vue.js 3 + Tailwind CSS + Vite
- **Backend:** Node.js + Express + TypeScript
- **Database:** PostgreSQL + Prisma ORM
- **Git Integration:** GitHub API via Octokit
- **Notifications:** Telegram Bot API

## Phase 1: Foundation (Current Task)

### 1. Project Setup

**Frontend (`/frontend`):**
```bash
npm create vite@latest . -- --template vue-ts
npm install tailwindcss postcss autoprefixer
npm install pinia vue-router axios
npm install @vueuse/core
npm install highlight.js  # for code syntax highlighting
```

**Backend (`/backend`):**
```bash
npm init -y
npm install express typescript ts-node-dev
npm install @types/express @types/node
npm install prisma @prisma/client
npm install bcryptjs jsonwebtoken
npm install @octokit/rest
npm install node-telegram-bot-api
npm install cors helmet
npm install zod  # validation
```

### 2. Database Schema

Create `backend/prisma/schema.prisma`:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id            Int             @id @default(autoincrement())
  username      String          @unique
  email         String          @unique
  passwordHash  String
  role          Role            @default(INTERN)
  telegramChatId String?
  createdAt     DateTime        @default(now())
  updatedAt     DateTime        @updatedAt
  
  projects      UserProject[]
  findings      UserFinding[]
  performance   PerformanceMetric[]
}

enum Role {
  ADMIN
  INTERN
}

model Project {
  id                  Int       @id @default(autoincrement())
  name                String    @unique
  displayName         String
  githubOwner         String
  githubRepo          String
  codeReviewEnabled   Boolean   @default(true)
  createdAt           DateTime  @default(now())
  
  users               UserProject[]
  reviews             Review[]
  performance         PerformanceMetric[]
}

model UserProject {
  userId    Int
  projectId Int
  user      User    @relation(fields: [userId], references: [id], onDelete: Cascade)
  project   Project @relation(fields: [projectId], references: [id], onDelete: Cascade)
  
  @@id([userId, projectId])
}

model Review {
  id          Int       @id @default(autoincrement())
  projectId   Int
  branch      String
  reviewDate  DateTime  @db.Date
  rawMarkdown String?   @db.Text
  createdAt   DateTime  @default(now())
  
  project     Project   @relation(fields: [projectId], references: [id])
  findings    Finding[]
  
  @@unique([projectId, branch, reviewDate])
}

model Finding {
  id              Int       @id @default(autoincrement())
  reviewId        Int
  commitSha       String?
  commitAuthor    String?
  filePath        String
  lineStart       Int?
  lineEnd         Int?
  originalCode    String    @db.Text
  optimizedCode   String    @db.Text
  explanation     String    @db.Text
  references      Json?     // Array of {type: "docs"|"article"|"tutorial", title: string, url: string}
  category        Category
  difficulty      Difficulty
  prCreated       Boolean   @default(false)
  prUrl           String?
  createdAt       DateTime  @default(now())
  
  review          Review    @relation(fields: [reviewId], references: [id], onDelete: Cascade)
  userFindings    UserFinding[]
}

enum Category {
  SECURITY
  PERFORMANCE
  CODE_STYLE
  TESTING
  ARCHITECTURE
  DOCUMENTATION
}

enum Difficulty {
  BEGINNER
  INTERMEDIATE
  ADVANCED
}

model UserFinding {
  userId                  Int
  findingId               Int
  markedUnderstood        Boolean   @default(false)
  explanationRequested    Boolean   @default(false)
  explanationRequestedAt  DateTime?
  
  user    User    @relation(fields: [userId], references: [id], onDelete: Cascade)
  finding Finding @relation(fields: [findingId], references: [id], onDelete: Cascade)
  
  @@id([userId, findingId])
}

model PerformanceMetric {
  id                  Int       @id @default(autoincrement())
  userId              Int
  projectId           Int
  periodType          PeriodType
  periodStart         DateTime  @db.Date
  periodEnd           DateTime  @db.Date
  commitCount         Int       @default(0)
  findingCount        Int       @default(0)
  findingsByCategory  Json?     // {"SECURITY": 2, "PERFORMANCE": 5}
  findingsByDifficulty Json?    // {"BEGINNER": 3, "ADVANCED": 1}
  strengths           Json?     // ["API Design", "Testing"]
  growthAreas         Json?     // ["Security", "Database"]
  recommendations     Json?     // [{type: "book", title: "...", url: "..."}]
  calculatedAt        DateTime  @default(now())
  
  user    User    @relation(fields: [userId], references: [id])
  project Project @relation(fields: [projectId], references: [id])
  
  @@unique([userId, projectId, periodType, periodStart])
}

enum PeriodType {
  DAILY
  WEEKLY
  MONTHLY
}
```

### 3. Backend Structure

```
backend/
├── src/
│   ├── index.ts              # Entry point
│   ├── app.ts                # Express app setup
│   ├── config/
│   │   └── index.ts          # Environment config
│   ├── middleware/
│   │   ├── auth.ts           # JWT middleware
│   │   ├── admin.ts          # Admin-only middleware
│   │   └── errorHandler.ts
│   ├── routes/
│   │   ├── auth.ts
│   │   ├── projects.ts
│   │   ├── reviews.ts
│   │   ├── findings.ts
│   │   ├── users.ts
│   │   └── performance.ts
│   ├── services/
│   │   ├── github.ts         # GitHub API integration
│   │   ├── telegram.ts       # Telegram notifications
│   │   └── performance.ts    # Calculate metrics
│   └── utils/
│       └── jwt.ts
├── prisma/
│   └── schema.prisma
├── .env.example
├── tsconfig.json
└── package.json
```

### 4. Frontend Structure

```
frontend/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── projects.ts
│   │   └── findings.ts
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── DashboardView.vue
│   │   ├── FindingDetailView.vue
│   │   ├── PerformanceView.vue
│   │   └── UserManagementView.vue
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.vue
│   │   │   ├── Badge.vue
│   │   │   ├── Card.vue
│   │   │   └── Modal.vue
│   │   ├── layout/
│   │   │   ├── Sidebar.vue
│   │   │   └── Header.vue
│   │   ├── calendar/
│   │   │   └── CalendarWidget.vue
│   │   ├── findings/
│   │   │   ├── FindingCard.vue
│   │   │   ├── CodeComparison.vue
│   │   │   └── ExplanationSection.vue
│   │   └── charts/
│   │       └── TrendChart.vue
│   ├── composables/
│   │   └── useApi.ts
│   └── assets/
│       ├── logo-horizontal.svg
│       └── styles/
│           └── main.css
├── index.html
├── tailwind.config.js
├── vite.config.ts
└── package.json
```

### 5. Design System (from Stitch)

**Colors:**
```css
:root {
  --primary: #58A6FF;
  --secondary: #5F799C;
  --tertiary: #DA9600;
  --bg-dark: #0D1117;
  --bg-card: #161B22;
  --text-primary: #FFFFFF;
  --text-secondary: #8B949E;
  --success: #3FB950;
  --error: #F85149;
  --warning: #D29922;
}
```

**Tailwind Config:**
```js
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#58A6FF',
        secondary: '#5F799C',
        tertiary: '#DA9600',
        dark: {
          bg: '#0D1117',
          card: '#161B22',
          border: '#30363D',
        },
        success: '#3FB950',
        error: '#F85149',
        warning: '#D29922',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

## Key Implementation Notes

### Code Comparison Component
- Use Monaco Editor or highlight.js for syntax highlighting
- Show line numbers on both sides
- Highlight changed lines (red for original, green for optimized)
- Full file context with problematic section highlighted

### Learning References (Important!)
When displaying explanations, include links to:
- Official language documentation
- Relevant tutorials/articles
- Best practice guides

Store in `Finding.references` as JSON array.

### Performance Tracking (Important!)
Track code progression:
- Compare findings over time for same user
- Show improvement trends
- Identify patterns in growth areas

### Telegram Integration
When intern clicks "Request Explanation":
1. Create entry in user_findings with explanationRequested=true
2. Send Telegram message to admin: "📞 Explanation requested by {intern} for {finding} in {project}"

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/reviewhub

# JWT
JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=7d

# GitHub
GITHUB_TOKEN=ghp_xxxxx

# Telegram
TELEGRAM_BOT_TOKEN=xxxxx
TELEGRAM_ADMIN_CHAT_ID=xxxxx

# App
PORT=3000
NODE_ENV=development
FRONTEND_URL=http://localhost:5173
```

## Deliverables for Phase 1

1. ✅ Working Vue.js frontend with Tailwind (dark theme)
2. ✅ Working Express backend with TypeScript
3. ✅ PostgreSQL database with Prisma schema
4. ✅ Authentication (login/logout, JWT)
5. ✅ Basic dashboard layout with sidebar and calendar
6. ✅ Finding card component
7. ✅ API endpoints for auth and listings

## Testing

- Use actual PostgreSQL database
- Create seed data for development
- Test with real GitHub API calls
- Test Telegram notification flow

## DO NOT

- Do not use SQLite (must be PostgreSQL)
- Do not skip TypeScript types
- Do not use inline styles (use Tailwind classes)
- Do not hardcode credentials
