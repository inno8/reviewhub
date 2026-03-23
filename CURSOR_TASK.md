# ReviewHub — Phase 5: UI Polish (Pixel-Perfect Match to Stitch Design)

## Overview

Polish the UI to match the Stitch design exactly. The current implementation works but doesn't match the designer's vision. This phase is about visual refinement.

**Stitch Design URL:** https://stitch.withgoogle.com/projects/1695881319703761493

## Design System Reference

### Colors (OpenClaw Dark)
```css
/* Primary palette */
--primary: #58A6FF;        /* Cyan/blue - main accent */
--primary-hover: #6CAEFF;  /* T70 */
--primary-light: #A2C9FF;  /* T80 */

/* Secondary palette */
--secondary: #5F799C;      /* Muted blue-gray */
--secondary-light: #7992B7; /* T60 */

/* Tertiary palette */
--tertiary: #DA9600;       /* Gold/orange - warnings, highlights */
--tertiary-light: #FFBA42; /* T80 */

/* Neutral palette (backgrounds) */
--bg-darkest: #0D1117;     /* Main background */
--bg-dark: #181C22;        /* T10 - cards, sidebar */
--bg-card: #161B22;        /* Card backgrounds */
--bg-elevated: #2D3137;    /* T20 - elevated surfaces, inputs */
--border: #30363D;         /* Borders */

/* Text colors */
--text-primary: #FFFFFF;   /* White - headings */
--text-secondary: #8B949E; /* Gray - body text */
--text-muted: #6E7681;     /* Muted text */

/* Status colors */
--success: #3FB950;        /* Green */
--error: #F85149;          /* Red */
--warning: #D29922;        /* Yellow/orange */
```

### Typography
- **Font Family:** Inter, system-ui, -apple-system, sans-serif
- **Monospace:** JetBrains Mono, Consolas, monospace
- **Headings:** Semi-bold (600), tracking slightly wider
- **Body:** Regular (400)
- **Labels/Badges:** Medium (500), uppercase for some labels

### Spacing & Sizing
- **Border radius:** 8px for cards, 6px for buttons, 4px for badges
- **Padding:** 16px for cards, 12px for smaller elements
- **Gap:** 16px between cards, 8px within groups

## Screen-by-Screen Polish Requirements

### 1. Login Page

**Current issues:**
- Logo design doesn't match (needs ReviewHub wordmark with code brackets icon)
- Input fields styling
- Button styling
- Footer links missing

**Design requirements:**
- Left side: Logo + tagline "THE MONOLITH & THE LENS"
- Center card with:
  - "Welcome back" heading
  - "Access your editorial code space" subtitle
  - Username field with person icon
  - Password field with lock icon + "Forgot?" link
  - Blue "Sign In" button with arrow icon
  - "New to the hub? Request Access" text
- Bottom: GitHub and SSO login buttons
- Footer: © 2024 ReviewHub | Documentation | System Status | Privacy

**CSS changes needed:**
```css
/* Login card */
.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 32px;
  max-width: 400px;
}

/* Input fields */
.input-field {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  padding-left: 44px; /* For icon */
}

/* Sign In button */
.btn-primary {
  background: var(--primary);
  color: white;
  border-radius: 8px;
  padding: 12px 24px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}
```

### 2. Dashboard

**Current issues:**
- Sidebar layout doesn't match
- Calendar widget styling
- Finding cards layout
- Header styling
- Filter dropdowns

**Design requirements from Stitch:**

**Header:**
- Logo on left (ReviewHub wordmark)
- "Dashboard" text (active nav item)
- Project selector dropdown (center)
- User avatar on right

**Sidebar (left, ~280px):**
- "Activity" section header with calendar icon
- Month calendar (March 2026)
  - Days with findings highlighted in blue
  - Grid layout with day names
- Navigation items below:
  - Dashboard (active - with blue indicator)
  - Insights
  - Team Management
  - Settings (bottom)
  - Support (bottom)

**Main content:**
- Date header: "Monday, March 23, 2026"
- Stats line: "14 pending reviews across 3 active projects"
- Filter bar: Category | Difficulty | Author dropdowns
- Finding cards grid (2-3 columns):
  - Card structure:
    - File path with folder icon
    - Branch badge (gray pill)
    - Category badge (colored: Security=red, Performance=orange, etc.)
    - Difficulty badge (Beginner=green, Intermediate=yellow, Advanced=red)
    - Author section (avatar + name)
    - 2-line description preview
    - "View Details" button (text link style)

**Card CSS:**
```css
.finding-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}

.finding-card:hover {
  border-color: var(--primary);
}

/* Category badges */
.badge-security { background: rgba(248, 81, 73, 0.15); color: #F85149; }
.badge-performance { background: rgba(210, 153, 34, 0.15); color: #D29922; }
.badge-code-style { background: rgba(88, 166, 255, 0.15); color: #58A6FF; }
.badge-testing { background: rgba(63, 185, 80, 0.15); color: #3FB950; }

/* Difficulty badges */
.badge-beginner { background: rgba(63, 185, 80, 0.15); color: #3FB950; }
.badge-intermediate { background: rgba(210, 153, 34, 0.15); color: #D29922; }
.badge-advanced { background: rgba(248, 81, 73, 0.15); color: #F85149; }
```

### 3. Finding Detail

**Current issues:**
- Code comparison layout
- Syntax highlighting colors
- Line numbers styling
- Action buttons placement

**Design requirements from Stitch:**

**Header:**
- Breadcrumb: File path → Branch name
- Badges: Category + Difficulty + Finding ID

**Code comparison (side-by-side):**
- Two panels: "Original" and "Optimized"
- Dark background for code blocks
- Line numbers on left of each panel
- Red highlight for problematic lines (left)
- Green highlight for improved lines (right)
- Proper syntax highlighting

**Below code:**
- "Why This Is Better" section header
- Explanation text
- Checkmark list of benefits
- Reference links

**Actions row:**
- Checkbox: "Mark as understood"
- Button: "Request Explanation" (outlined)
- Button: "Apply Fix & Create PR" (primary blue)

**Code block CSS:**
```css
.code-panel {
  background: #0D1117;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.line-number {
  color: var(--text-muted);
  padding-right: 16px;
  user-select: none;
  text-align: right;
  width: 40px;
}

.line-deleted {
  background: rgba(248, 81, 73, 0.15);
}

.line-added {
  background: rgba(63, 185, 80, 0.15);
}
```

### 4. Performance Insights

**Design requirements:**

**Header:**
- "Performance Insights" title
- Developer selector dropdown
- Period tabs: Daily | Weekly | Monthly

**Stats cards row:**
- 4 cards: Total Commits | Total Findings | Fix Rate | Trend
- Each with icon, value, and label

**Two-column layout:**
- Left: "Strengths" with green checkmark badges
- Right: "Growth Areas" with orange arrow-up badges

**Chart:**
- Line chart showing findings over time
- X-axis: weeks
- Y-axis: count
- Blue line with area fill

**Recommendations:**
- Cards with resource icon, title, link, and relevance tag

### 5. User Management

**Design requirements:**

**Header:**
- "Team Management" title
- "Add User" button (primary)

**Table:**
- Columns: Avatar | Username | Email | Role | Projects | Actions
- Alternating row colors
- Hover state
- Role badges (Admin=blue, Intern=gray)
- Project tags
- Action icons (edit, delete)

**Add/Edit Modal:**
- Form fields: Username, Email, Password, Role dropdown
- Projects checklist
- Save/Cancel buttons

## Components to Create/Update

### Global Components
- [ ] `Badge.vue` - Unified badge styling with variants
- [ ] `Button.vue` - Primary, secondary, outlined, danger variants
- [ ] `Card.vue` - Consistent card styling
- [ ] `Input.vue` - With icon support
- [ ] `Dropdown.vue` - Styled select component

### Layout Components
- [ ] `Sidebar.vue` - Match design exactly
- [ ] `Header.vue` - Logo, nav, user menu

### Page-Specific
- [ ] `LoginView.vue` - Complete redesign
- [ ] `DashboardView.vue` - Layout fixes, card grid
- [ ] `FindingDetailView.vue` - Code panels, explanation section
- [ ] `PerformanceView.vue` - Charts, stats cards
- [ ] `UserManagementView.vue` - Table styling, modal

## CSS Files to Update

**`frontend/src/assets/styles/main.css`:**
- Add all CSS custom properties
- Add component base styles
- Add utility classes

**`frontend/tailwind.config.js`:**
- Extend colors with design system
- Add custom fonts

## Testing Checklist

For each screen, verify:
- [ ] Colors match exactly
- [ ] Spacing/padding matches
- [ ] Border radius matches
- [ ] Typography matches
- [ ] Icons are consistent
- [ ] Hover/active states work
- [ ] Responsive behavior (if applicable)

## Logo Asset

Create `frontend/src/assets/logo.svg` with the horizontal wordmark:
- Code brackets icon (`</>`) with lightbulb symbol
- "ReviewHub" text in Inter font
- Primary blue color (#58A6FF)

## DO NOT

- Do not change functionality (only visual)
- Do not break existing API connections
- Do not change database schema
- Do not remove existing features
- Keep all TypeScript types intact
