# ReviewHub: Import Markdown Reviews into Database

## Context

@code-review writes detailed reviews to markdown files at:
`C:\Users\yanic\.openclaw\workspace\projects\amanks-market\reviews\YYYY-MM-DD.md`

But ReviewHub reads from its SQLite database. Currently they're disconnected.

## Task: Create Markdown Import System

### 1. Create Import Service

**File:** `backend/src/services/markdownImport.ts`

Parse markdown review files and extract findings:

```typescript
import * as fs from 'fs';
import * as path from 'path';
import { PrismaClient, Category, Difficulty } from '@prisma/client';

const REVIEWS_DIR = 'C:/Users/yanic/.openclaw/workspace/projects/amanks-market/reviews';

interface ParsedFinding {
  filePath: string;
  lineStart: number;
  lineEnd: number;
  originalCode: string;
  explanation: string;
  category: Category;
  difficulty: Difficulty;
  branch: string;
  commitAuthor: string;
}

export async function importMarkdownReview(date: string, projectId: number): Promise<number> {
  const filePath = path.join(REVIEWS_DIR, `${date}.md`);
  
  if (!fs.existsSync(filePath)) {
    throw new Error(`Review file not found: ${filePath}`);
  }
  
  const content = fs.readFileSync(filePath, 'utf-8');
  const findings = parseMarkdownReview(content);
  
  // Import to database...
  return findings.length;
}

function parseMarkdownReview(content: string): ParsedFinding[] {
  const findings: ParsedFinding[] = [];
  
  // Parse the markdown structure:
  // - Find branch headers (### 1. `branch-name`)
  // - Find "#### ⚠️ Issues Found" sections
  // - Extract numbered issues with code blocks
  // - Map to categories based on keywords
  
  // Example pattern to match:
  // ##### 1. **Duplicate Meta Description** (home.html)
  // ```html
  // <meta name="description" content="...">
  // ```
  // **Why this matters:** ...
  // **Fix:** ...
  
  const branchRegex = /### \d+\. `([^`]+)`\s*\n\*\*Author:\*\* ([^\n]+)/g;
  const issueRegex = /##### \d+\. \*\*([^*]+)\*\* \(([^)]+)\)\s*\n```(\w+)?\n([\s\S]*?)```\s*\n\*\*Why this matters:\*\* ([^\n]+)/g;
  
  let currentBranch = '';
  let currentAuthor = '';
  
  // First pass: extract branches
  let branchMatch;
  const branches: Array<{branch: string, author: string, startIndex: number}> = [];
  while ((branchMatch = branchRegex.exec(content)) !== null) {
    branches.push({
      branch: branchMatch[1],
      author: branchMatch[2].split('(')[0].trim(),
      startIndex: branchMatch.index
    });
  }
  
  // Second pass: extract issues and assign to branches
  let issueMatch;
  while ((issueMatch = issueRegex.exec(content)) !== null) {
    // Find which branch this issue belongs to
    const issueIndex = issueMatch.index;
    for (let i = branches.length - 1; i >= 0; i--) {
      if (branches[i].startIndex < issueIndex) {
        currentBranch = branches[i].branch;
        currentAuthor = branches[i].author;
        break;
      }
    }
    
    const [_, title, fileName, lang, code, explanation] = issueMatch;
    
    findings.push({
      filePath: fileName,
      lineStart: 1,
      lineEnd: 1,
      originalCode: code.trim(),
      explanation: `**${title}**: ${explanation}`,
      category: categorizeIssue(title),
      difficulty: Difficulty.BEGINNER,
      branch: currentBranch,
      commitAuthor: currentAuthor
    });
  }
  
  return findings;
}

function categorizeIssue(title: string): Category {
  const lower = title.toLowerCase();
  if (lower.includes('security') || lower.includes('csrf') || lower.includes('hardcoded')) {
    return Category.SECURITY;
  }
  if (lower.includes('performance') || lower.includes('slow') || lower.includes('loading')) {
    return Category.PERFORMANCE;
  }
  if (lower.includes('test') || lower.includes('coverage')) {
    return Category.TESTING;
  }
  if (lower.includes('architecture') || lower.includes('structure') || lower.includes('import')) {
    return Category.ARCHITECTURE;
  }
  return Category.CODE_STYLE;
}
```

### 2. Add Import Endpoint

**File:** `backend/src/routes/reviews.ts`

Add a new endpoint that imports from markdown:

```typescript
import { importMarkdownReview, syncAllMarkdownReviews } from '../services/markdownImport';

// Import a specific day's review from markdown
router.post('/import/:date', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { date } = req.params;
  const { projectId } = req.body;
  
  if (!projectId || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    res.status(400).json({ error: 'Valid projectId and date (YYYY-MM-DD) required' });
    return;
  }
  
  try {
    const count = await importMarkdownReview(date, projectId);
    res.json({ success: true, imported: count, date });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});

// Sync all markdown reviews (scan directory, import missing)
router.post('/sync-markdown', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { projectId } = req.body;
  
  if (!projectId) {
    res.status(400).json({ error: 'projectId required' });
    return;
  }
  
  try {
    const result = await syncAllMarkdownReviews(projectId);
    res.json({ success: true, ...result });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
});
```

### 3. Update Refresh Button

**File:** `backend/src/routes/reviews.ts`

Modify the existing `/trigger` endpoint to also check for new markdown files:

```typescript
router.post('/trigger', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { projectId } = req.body;
  
  // First, sync any new markdown reviews from @code-review
  const markdownResult = await syncAllMarkdownReviews(projectId);
  
  // Then do the GitHub-based analysis (optional, could remove)
  // ... existing code ...
  
  res.json({
    success: true,
    markdownImported: markdownResult.imported,
    // ... other results
  });
});
```

### 4. Add Sync Function

**File:** `backend/src/services/markdownImport.ts`

```typescript
export async function syncAllMarkdownReviews(projectId: number): Promise<{imported: number, skipped: number, files: string[]}> {
  const prisma = new PrismaClient();
  const files = fs.readdirSync(REVIEWS_DIR).filter(f => f.match(/^\d{4}-\d{2}-\d{2}\.md$/));
  
  let imported = 0;
  let skipped = 0;
  const importedFiles: string[] = [];
  
  for (const file of files) {
    const date = file.replace('.md', '');
    const reviewDate = new Date(date);
    reviewDate.setHours(0, 0, 0, 0);
    
    // Check if we already imported this date
    const existing = await prisma.review.findFirst({
      where: {
        projectId,
        reviewDate,
        rawMarkdown: { not: null }  // Indicates it was imported from markdown
      }
    });
    
    if (existing) {
      skipped++;
      continue;
    }
    
    try {
      const count = await importMarkdownReview(date, projectId);
      imported += count;
      importedFiles.push(date);
    } catch (e) {
      console.error(`Failed to import ${file}:`, e);
    }
  }
  
  await prisma.$disconnect();
  return { imported, skipped, files: importedFiles };
}
```

### 5. Frontend: Update API Client

**File:** `frontend/src/composables/useApi.ts`

Add the new endpoints:

```typescript
reviews: {
  // ... existing
  importMarkdown: (projectId: number, date: string) =>
    client.post(`/reviews/import/${date}`, { projectId }),
  syncMarkdown: (projectId: number) =>
    client.post('/reviews/sync-markdown', { projectId }),
},
```

## Testing

1. Run sync: `POST /api/reviews/sync-markdown` with `{ projectId: 1 }`
2. Should import the 2026-03-25.md review
3. Calendar should now show March 25 as active
4. Clicking March 25 should show the real issues (duplicate meta, broken HTML, etc.)

## Files to Create/Modify

- **CREATE:** `backend/src/services/markdownImport.ts`
- **MODIFY:** `backend/src/routes/reviews.ts`
- **MODIFY:** `frontend/src/composables/useApi.ts`

## Important Notes

- The markdown parser needs to handle the specific format of @code-review output
- Store `rawMarkdown` in the Review model to track that it came from markdown import
- De-duplicate: don't re-import if the date already has findings
- The Refresh button should call sync-markdown first, then optionally do GitHub analysis

---

Ready for implementation!
