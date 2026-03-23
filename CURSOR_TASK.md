# ReviewHub — Phase 3: GitHub PR Creation & Telegram Notifications

## Overview

Implement the "Apply Fix & Create PR" functionality and Telegram notifications for explanation requests. This phase makes the admin actions work end-to-end.

## Current State

- ✅ Phase 1: Foundation complete
- ✅ Phase 2: Core Dashboard complete (API wired, login, filters, code comparison)
- Backend running on port 3000
- Frontend running on port 5174
- SQLite database with seed data

## Phase 3 Tasks

### 1. GitHub Integration — Apply Fix & Create PR

**Backend: `backend/src/services/github.ts`**

Implement the full GitHub flow:

```typescript
export async function applyFixAndCreatePR(finding: Finding, review: Review, project: Project): Promise<string> {
  // 1. Get the file content from the source branch
  // 2. Create a new branch: fix/finding-{id}-{timestamp}
  // 3. Update the file with optimizedCode
  // 4. Commit the change
  // 5. Create PR to main
  // 6. Return PR URL
}
```

**Steps:**
1. Use Octokit to authenticate with GitHub token from env
2. Get current file content from the branch where issue was found
3. Create new branch from that branch
4. Replace the code between lineStart and lineEnd with optimizedCode
5. Commit with message: `fix: Apply code review suggestion for ${filePath}`
6. Create PR with:
   - Title: `Fix: ${category} issue in ${filePath}`
   - Body: Include explanation and link to finding
   - Base: main
   - Head: fix branch

**Backend: `backend/src/routes/findings.ts`**

Add endpoint:
```typescript
// POST /api/findings/:id/apply-fix
// Admin only
// Returns: { prUrl: string }
```

**Frontend: `frontend/src/views/FindingDetailView.vue`**

Wire up the "Apply Fix & Create PR" button:
- Show loading state while creating PR
- On success: show PR URL as clickable link
- On error: show error message
- Update finding.prCreated and finding.prUrl in state

### 2. Telegram Notifications

**Backend: `backend/src/services/telegram.ts`**

Implement actual Telegram sending:

```typescript
import TelegramBot from 'node-telegram-bot-api';

const bot = process.env.TELEGRAM_BOT_TOKEN 
  ? new TelegramBot(process.env.TELEGRAM_BOT_TOKEN)
  : null;

export async function notifyExplanationRequested(
  intern: User,
  finding: Finding,
  project: Project
): Promise<void> {
  if (!bot || !process.env.TELEGRAM_ADMIN_CHAT_ID) {
    console.log('[Telegram] Bot not configured, skipping notification');
    return;
  }

  const message = `📞 *Explanation Requested*

*Intern:* ${intern.username}
*Project:* ${project.displayName}
*File:* \`${finding.filePath}\`
*Category:* ${finding.category}
*Difficulty:* ${finding.difficulty}

The intern would like a live explanation of this code review finding.`;

  await bot.sendMessage(process.env.TELEGRAM_ADMIN_CHAT_ID, message, {
    parse_mode: 'Markdown',
  });
}
```

**Backend: `backend/src/routes/findings.ts`**

Update the request-explanation endpoint to actually send Telegram notification:
- Get the current user (intern)
- Get the finding with project info
- Call notifyExplanationRequested()
- Handle errors gracefully (don't fail if Telegram fails)

### 3. User Management (Admin)

**Backend: `backend/src/routes/users.ts`**

Ensure these endpoints work properly:

```typescript
// GET /api/users - List all users (admin only)
// POST /api/users - Create user (admin only)
//   Body: { username, email, password, role, projectIds }
// PATCH /api/users/:id - Update user (admin only)
//   Body: { username?, email?, password?, role?, projectIds? }
// DELETE /api/users/:id - Delete user (admin only)
// GET /api/users/:id/projects - Get user's assigned projects
// POST /api/users/:id/projects - Assign projects to user
//   Body: { projectIds: number[] }
```

**Frontend: `frontend/src/views/UserManagementView.vue`**

Wire up the user management UI:
- Fetch and display users list
- "Add User" button opens modal
- Add User modal:
  - Username, email, password fields
  - Role dropdown (Admin/Intern)
  - Project multi-select checkboxes
  - Save creates user and assigns projects
- Edit user (click row or edit icon)
- Delete user (with confirmation)
- Show assigned projects as badges

### 4. Environment Setup

**Backend `.env` additions needed for full functionality:**
```
# GitHub - Personal Access Token with repo scope
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_ADMIN_CHAT_ID=123456789
```

### 5. Error Handling

- GitHub API errors: Return meaningful error messages
- Telegram errors: Log but don't fail the request
- User management: Validate unique username/email

## Testing Checklist

### GitHub PR Flow
- [ ] Configure GITHUB_TOKEN in .env
- [ ] Click "Apply Fix & Create PR" on a finding
- [ ] Verify new branch created in GitHub
- [ ] Verify PR created with correct title/body
- [ ] Verify finding.prUrl updated in database
- [ ] Verify button shows PR link after creation

### Telegram Notifications
- [ ] Configure TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID
- [ ] Login as intern (alice/intern123)
- [ ] Click "Request Explanation" on a finding
- [ ] Verify Telegram message received by admin

### User Management
- [ ] Login as admin
- [ ] Navigate to User Management
- [ ] See list of users with their roles and projects
- [ ] Add new intern user
- [ ] Assign projects to user
- [ ] Edit user role
- [ ] Delete user (with confirmation)

## Files to Modify

**Backend:**
- `backend/src/services/github.ts` — Full implementation
- `backend/src/services/telegram.ts` — Full implementation
- `backend/src/routes/findings.ts` — Add apply-fix endpoint
- `backend/src/routes/users.ts` — Complete CRUD + project assignment

**Frontend:**
- `frontend/src/views/FindingDetailView.vue` — Wire up Apply Fix button
- `frontend/src/views/UserManagementView.vue` — Full implementation
- `frontend/src/composables/useApi.ts` — Add missing endpoints if needed

## DO NOT

- Do not change the database schema
- Do not commit real tokens to git
- Do not skip error handling
- Do not make GitHub calls without checking for token
