# ReviewHub — Phase 4: Performance Insights

## Overview

Build the Performance Insights dashboard for admins. This page shows individual developer metrics, strengths, growth areas, code progression tracking, and personalized learning recommendations.

## Current State

- ✅ Phase 1-3 complete
- ✅ GitHub and Telegram tokens configured
- Backend running on port 3000
- Frontend running on port 5174

## Phase 4 Tasks

### 1. Performance Metrics Calculation Service

**Backend: `backend/src/services/performance.ts`**

Implement the performance calculation logic:

```typescript
export interface PerformanceData {
  userId: number;
  projectId: number;
  periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  periodStart: Date;
  periodEnd: Date;
  commitCount: number;
  findingCount: number;
  findingsByCategory: Record<string, number>;
  findingsByDifficulty: Record<string, number>;
  strengths: string[];
  growthAreas: string[];
  recommendations: Recommendation[];
}

interface Recommendation {
  type: 'book' | 'article' | 'tutorial' | 'video';
  title: string;
  url: string;
  category: string;
  reason: string;
}

export async function calculatePerformance(
  userId: number,
  projectId: number,
  periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY'
): Promise<PerformanceData>
```

**Logic:**
1. Get all findings for the user (by commitAuthor) in the period
2. Count by category and difficulty
3. Determine strengths: categories with 0-1 findings (they're doing well)
4. Determine growth areas: categories with 3+ findings (needs improvement)
5. Generate recommendations based on growth areas

**Recommendations mapping (hardcoded for now):**
```typescript
const RECOMMENDATIONS: Record<string, Recommendation[]> = {
  SECURITY: [
    { type: 'book', title: 'Web Security for Developers', url: 'https://www.amazon.com/dp/1593279949', category: 'SECURITY', reason: 'Covers common vulnerabilities and prevention' },
    { type: 'article', title: 'OWASP Top 10', url: 'https://owasp.org/Top10/', category: 'SECURITY', reason: 'Essential security knowledge' },
  ],
  PERFORMANCE: [
    { type: 'book', title: 'High Performance JavaScript', url: 'https://www.amazon.com/dp/059680279X', category: 'PERFORMANCE', reason: 'Deep dive into JS performance' },
    { type: 'article', title: 'Web.dev Performance Guide', url: 'https://web.dev/performance/', category: 'PERFORMANCE', reason: 'Modern performance best practices' },
  ],
  CODE_STYLE: [
    { type: 'book', title: 'Clean Code', url: 'https://www.amazon.com/dp/0132350882', category: 'CODE_STYLE', reason: 'Industry standard for code quality' },
    { type: 'article', title: 'Google Style Guides', url: 'https://google.github.io/styleguide/', category: 'CODE_STYLE', reason: 'Professional style guidelines' },
  ],
  TESTING: [
    { type: 'book', title: 'Testing JavaScript Applications', url: 'https://www.amazon.com/dp/1617297917', category: 'TESTING', reason: 'Comprehensive testing guide' },
    { type: 'tutorial', title: 'Jest Documentation', url: 'https://jestjs.io/docs/getting-started', category: 'TESTING', reason: 'Learn the most popular testing framework' },
  ],
  ARCHITECTURE: [
    { type: 'book', title: 'Clean Architecture', url: 'https://www.amazon.com/dp/0134494164', category: 'ARCHITECTURE', reason: 'Fundamental architecture principles' },
    { type: 'article', title: 'Patterns.dev', url: 'https://www.patterns.dev/', category: 'ARCHITECTURE', reason: 'Modern design patterns' },
  ],
  DOCUMENTATION: [
    { type: 'article', title: 'Write the Docs Guide', url: 'https://www.writethedocs.org/guide/', category: 'DOCUMENTATION', reason: 'Documentation best practices' },
  ],
};
```

### 2. Code Progression Tracking

**Add to performance service:**

```typescript
export async function getCodeProgression(
  userId: number,
  projectId: number
): Promise<CodeProgression[]>

interface CodeProgression {
  weekStart: Date;
  weekEnd: Date;
  findingCount: number;
  categories: Record<string, number>;
  trend: 'improving' | 'stable' | 'declining';
}
```

Compare findings week-over-week to show if the developer is improving.

### 3. Performance API Endpoints

**Backend: `backend/src/routes/performance.ts`**

```typescript
// GET /api/performance/:userId
// Query: projectId, periodType (DAILY|WEEKLY|MONTHLY)
// Returns: PerformanceData

// GET /api/performance/:userId/trends
// Query: projectId, weeks (default 8)
// Returns: CodeProgression[]

// GET /api/performance/:userId/recommendations
// Query: projectId
// Returns: Recommendation[]

// GET /api/performance/leaderboard
// Query: projectId, periodType
// Returns: Array of { userId, username, findingCount, improvementRate }
```

### 4. Performance Insights UI

**Frontend: `frontend/src/views/PerformanceView.vue`**

Complete implementation:

**Header Section:**
- Developer selector dropdown (fetch users)
- Time period tabs: Daily | Weekly | Monthly
- Project filter (if multiple projects)

**Stats Cards Row:**
- Total Commits (from findings count)
- Total Findings
- Fix Rate % (findings with prCreated / total)
- Trend indicator (arrow up/down with color)

**Two-Column Section:**
- Left: **Strengths** — green badges with checkmarks
- Right: **Growth Areas** — orange badges with arrow icons

**Chart Section:**
- Line chart showing findings over time (by week)
- Use a simple chart library or CSS-based visualization
- X-axis: weeks, Y-axis: finding count
- Show trend line

**Recommendations Section:**
- Cards for each recommendation:
  - Icon based on type (book, video, article, tutorial)
  - Title (clickable link)
  - Category badge
  - Reason text
- Group by growth area

**Code Progression Section (New!):**
- "Your Progress" header
- Week-by-week comparison
- Show "Week 1 vs Week 4" examples when available
- Highlight categories where findings decreased

### 5. Simple Chart Component

**Frontend: `frontend/src/components/charts/TrendChart.vue`**

Create a simple SVG-based line chart (no external dependencies):

```vue
<template>
  <svg :viewBox="`0 0 ${width} ${height}`" class="w-full h-48">
    <!-- Grid lines -->
    <!-- Data points -->
    <!-- Line connecting points -->
    <!-- Labels -->
  </svg>
</template>
```

Or use a lightweight library like Chart.js if preferred.

### 6. Frontend API Updates

**Frontend: `frontend/src/composables/useApi.ts`**

Add:
```typescript
performance: {
  get: (userId: number, params: { projectId: number; periodType: string }) => 
    axios.get(`/performance/${userId}`, { params }),
  trends: (userId: number, params: { projectId: number; weeks?: number }) =>
    axios.get(`/performance/${userId}/trends`, { params }),
  recommendations: (userId: number, params: { projectId: number }) =>
    axios.get(`/performance/${userId}/recommendations`, { params }),
}
```

## Testing Checklist

- [ ] Login as admin
- [ ] Navigate to Performance Insights
- [ ] Select a developer (alice or bob)
- [ ] See stats cards with real data
- [ ] See strengths (green) and growth areas (orange)
- [ ] See trend chart with weekly data
- [ ] See recommendations based on growth areas
- [ ] Switch time period (Daily/Weekly/Monthly) and see data update
- [ ] Switch developer and see different stats

## Files to Modify/Create

**Backend:**
- `backend/src/services/performance.ts` — Full implementation
- `backend/src/routes/performance.ts` — Complete endpoints

**Frontend:**
- `frontend/src/views/PerformanceView.vue` — Full implementation
- `frontend/src/components/charts/TrendChart.vue` — Chart component
- `frontend/src/composables/useApi.ts` — Add performance endpoints

## DO NOT

- Do not add heavy chart libraries (keep it simple)
- Do not change database schema
- Do not skip TypeScript types
- Keep the UI consistent with existing dark theme
