# ReviewHub Dashboard Fixes

## Priority: HIGH

Three bugs need fixing in the ReviewHub dashboard:

---

## Task 1: Connect Calendar to Backend API

**File:** `frontend/src/components/calendar/CalendarWidget.vue`

**Problem:** Calendar dates are hardcoded:
```javascript
const activeDates = new Set(['2026-03-08', '2026-03-11', '2026-03-16', '2026-03-19']);
```

**Fix Required:**
1. Import and use the API client: `import { api } from '@/composables/useApi';`
2. Accept `projectId` as a prop
3. Fetch active dates on mount and when month changes using `api.reviews.calendar(projectId, month)`
4. The API returns `{ dates: ['2026-03-25', ...] }` — use these for highlighting
5. Emit a `dateSelected` event when user clicks a date

**Backend endpoint already exists:**
```typescript
// GET /api/reviews/calendar?projectId=1&month=2026-03
// Returns: { dates: ['2026-03-25', '2026-03-24', ...] }
```

---

## Task 2: Fix Pattern Analyzer - Capture Actual Code

**File:** `backend/src/routes/reviews.ts`

**Problem:** The `analyzeFilePatterns()` function always shows the same hardcoded example:
```javascript
originalCode: 'const url = "https://api.example.com"',  // Always this!
```

Instead of capturing the actual code from the diff.

**Fix Required:**
1. When matching patterns like hardcoded URLs, extract the actual matching line from the patch
2. Parse the patch to get the real line number
3. Show the real code snippet, not a hardcoded example

**Example fix for URL detection:**
```javascript
// Find actual hardcoded URLs in the diff
const urlMatches = patch.matchAll(/\+(.*(https?:\/\/[^\s"']+\.(com|io|org|net))[^)]*)/g);
for (const match of urlMatches) {
  const actualLine = match[1].trim();
  const actualUrl = match[2];
  issues.push({
    lineStart: calculateLineNumber(patch, match.index),
    lineEnd: calculateLineNumber(patch, match.index),
    originalCode: actualLine,  // Real code!
    optimizedCode: actualLine.replace(actualUrl, 'process.env.API_URL'),
    explanation: `Hardcoded URL "${actualUrl}" should be moved to environment variables.`,
    // ...
  });
}
```

Also add a helper to calculate line numbers from diff:
```javascript
function calculateLineNumber(patch: string, position: number): number {
  // Parse @@ -x,y +a,b @@ header to get starting line
  // Count newlines up to position
  // Return actual line number
}
```

---

## Task 3: Add Date Filtering to Dashboard

**File:** `frontend/src/views/DashboardView.vue`

**Problem:** Clicking a calendar date does nothing. Findings are not filtered by date.

**Fix Required:**
1. Pass `selectedProjectId` to CalendarWidget
2. Listen for `dateSelected` event from calendar
3. When a date is selected, add it to filters: `{ date: '2026-03-25' }`
4. The backend findings endpoint already supports date filtering

**Update DashboardView.vue:**
```vue
<CalendarWidget 
  :projectId="projectsStore.selectedProjectId" 
  @dateSelected="onDateSelected" 
/>

// In script:
const selectedDate = ref<string | null>(null);

function onDateSelected(date: string) {
  selectedDate.value = date;
  findingsStore.fetchFindings({ 
    projectId: projectsStore.selectedProjectId,
    date: date 
  });
}
```

Also add a way to clear the date filter (show all findings).

---

## Testing

After fixes:
1. Calendar should highlight dates that have actual reviews (March 25th should be highlighted)
2. Clicking March 25th should show only findings from that day
3. Findings should show the actual code snippets, not generic examples

## Files to Modify

- `frontend/src/components/calendar/CalendarWidget.vue`
- `frontend/src/views/DashboardView.vue`  
- `backend/src/routes/reviews.ts`

---

Ready for implementation!
