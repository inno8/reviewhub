import * as fs from 'fs';
import * as path from 'path';
import { PrismaClient, Category, Difficulty } from '@prisma/client';

const REVIEWS_DIR = 'C:/Users/yanic/.openclaw/workspace/projects/amanks-market/reviews';

interface ParsedFinding {
  filePath: string;
  lineStart: number;
  lineEnd: number;
  originalCode: string;
  optimizedCode: string;
  explanation: string;
  category: Category;
  difficulty: Difficulty;
  branch: string;
  commitSha: string;
  commitAuthor: string;
}

interface BranchInfo {
  branch: string;
  author: string;
  commitSha: string;
  startIndex: number;
}

export function parseMarkdownReview(content: string): ParsedFinding[] {
  const findings: ParsedFinding[] = [];

  // Extract branches: ### 1. `branch-name`
  const branchRegex = /### \d+\. `([^`]+)`\s*\n\*\*Author:\*\* ([^\n]+)\n\*\*Commit:\*\* ([a-f0-9]+)/g;
  const branches: BranchInfo[] = [];
  let match;
  while ((match = branchRegex.exec(content)) !== null) {
    branches.push({
      branch: match[1],
      author: match[2].split('(')[0].trim(),
      commitSha: match[3],
      startIndex: match.index,
    });
  }

  // Extract issues: ##### N. **Title** (filename) or ##### N. **Title**
  // Issues may or may not have code blocks, and use **Why this matters:** or **Suggestion:**
  const issueRegex = /##### \d+\. \*\*([^*]+)\*\*(?:\s*\(([^)]+)\))?\s*\n([\s\S]*?)(?=##### \d+\.|#### [🧪📚]|---|\n## |\n### \d+\.|$)/g;

  while ((match = issueRegex.exec(content)) !== null) {
    const title = match[1].trim();
    const fileHint = match[2]?.trim() || '';
    const body = match[3];
    const issueIndex = match.index;

    // Find which branch this belongs to
    let branch = '';
    let author = '';
    let commitSha = '';
    for (let i = branches.length - 1; i >= 0; i--) {
      if (branches[i].startIndex < issueIndex) {
        branch = branches[i].branch;
        author = branches[i].author;
        commitSha = branches[i].commitSha;
        break;
      }
    }

    // Extract code block if present
    const codeMatch = body.match(/```(\w+)?\n([\s\S]*?)```/);
    const originalCode = codeMatch ? codeMatch[2].trim() : '';

    // Extract fix/suggestion code block if present (second code block)
    const allCodeBlocks = [...body.matchAll(/```(\w+)?\n([\s\S]*?)```/g)];
    let optimizedCode = allCodeBlocks.length > 1 ? allCodeBlocks[1][2].trim() : '';

    // Extract explanation from **Why this matters:** or text after code block
    const whyMatch = body.match(/\*\*Why this matters:\*\*\s*([^\n]+)/);
    const fixMatch = body.match(/\*\*(?:Fix|Suggestion):\*\*\s*([^\n]+)/);

    // For issues without code blocks, put fix/suggestion text in optimizedCode
    if (!originalCode && fixMatch) {
      optimizedCode = fixMatch[1].trim();
    }

    let explanation = `**${title}**`;
    if (whyMatch) explanation += `: ${whyMatch[1].trim()}`;
    if (fixMatch) explanation += ` **Fix:** ${fixMatch[1].trim()}`;

    // If no **Why this matters**, grab the first non-code line as explanation
    if (!whyMatch) {
      const textLines = body.split('\n')
        .filter(l => !l.startsWith('```') && l.trim().length > 0)
        .map(l => l.trim());
      if (textLines.length > 0) {
        explanation = `**${title}**: ${textLines[0]}`;
      }
    }

    findings.push({
      filePath: fileHint || 'unknown',
      lineStart: 1,
      lineEnd: 1,
      originalCode,
      optimizedCode,
      explanation,
      category: categorizeIssue(title, body),
      difficulty: categorizeDifficulty(title, body),
      branch,
      commitSha,
      commitAuthor: author,
    });
  }

  return findings;
}

function categorizeIssue(title: string, body: string): Category {
  const text = (title + ' ' + body).toLowerCase();
  if (text.includes('security') || text.includes('csrf') || text.includes('hardcoded') || text.includes('credential')) {
    return Category.SECURITY;
  }
  if (text.includes('performance') || text.includes('slow') || text.includes('loading') || text.includes('external images')) {
    return Category.PERFORMANCE;
  }
  if (text.includes('test') || text.includes('coverage')) {
    return Category.TESTING;
  }
  if (text.includes('architecture') || text.includes('structure') || text.includes('import conflict') || text.includes('centralize')) {
    return Category.ARCHITECTURE;
  }
  if (text.includes('documentation') || text.includes('docstring') || text.includes('readme')) {
    return Category.DOCUMENTATION;
  }
  return Category.CODE_STYLE;
}

function categorizeDifficulty(title: string, body: string): Difficulty {
  const text = (title + ' ' + body).toLowerCase();
  if (text.includes('architecture') || text.includes('import conflict') || text.includes('form functionality')) {
    return Difficulty.INTERMEDIATE;
  }
  if (text.includes('security') || text.includes('csrf')) {
    return Difficulty.ADVANCED;
  }
  return Difficulty.BEGINNER;
}

export async function importMarkdownReview(date: string, projectId: number): Promise<number> {
  const filePath = path.join(REVIEWS_DIR, `${date}.md`);

  if (!fs.existsSync(filePath)) {
    throw new Error(`Review file not found: ${filePath}`);
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const findings = parseMarkdownReview(content);

  if (findings.length === 0) {
    return 0;
  }

  const prisma = new PrismaClient();
  try {
    // Use UTC date to avoid timezone issues
    const reviewDate = new Date(`${date}T00:00:00.000Z`);

    // Group findings by branch
    const byBranch = new Map<string, ParsedFinding[]>();
    for (const f of findings) {
      const key = f.branch || 'unknown';
      if (!byBranch.has(key)) byBranch.set(key, []);
      byBranch.get(key)!.push(f);
    }

    let totalImported = 0;

    for (const [branch, branchFindings] of byBranch) {
      // Upsert the review for this branch+date
      let review = await prisma.review.findUnique({
        where: {
          projectId_branch_reviewDate: {
            projectId,
            branch,
            reviewDate,
          },
        },
      });

      if (!review) {
        review = await prisma.review.create({
          data: {
            projectId,
            branch,
            reviewDate,
            rawMarkdown: content,
          },
        });
      } else if (!review.rawMarkdown) {
        await prisma.review.update({
          where: { id: review.id },
          data: { rawMarkdown: content },
        });
      }

      // Import findings
      for (const f of branchFindings) {
        // Check for duplicate by reviewId + filePath + explanation prefix
        const existing = await prisma.finding.findFirst({
          where: {
            reviewId: review.id,
            filePath: f.filePath,
            explanation: { startsWith: f.explanation.slice(0, 50) },
          },
        });

        if (!existing) {
          await prisma.finding.create({
            data: {
              reviewId: review.id,
              commitSha: f.commitSha,
              commitAuthor: f.commitAuthor,
              filePath: f.filePath,
              lineStart: f.lineStart,
              lineEnd: f.lineEnd,
              originalCode: f.originalCode,
              optimizedCode: f.optimizedCode,
              explanation: f.explanation,
              references: JSON.stringify([]),
              category: f.category,
              difficulty: f.difficulty,
            },
          });
          totalImported++;
        }
      }
    }

    return totalImported;
  } finally {
    await prisma.$disconnect();
  }
}

export async function syncAllMarkdownReviews(projectId: number): Promise<{ imported: number; skipped: number; files: string[] }> {
  if (!fs.existsSync(REVIEWS_DIR)) {
    return { imported: 0, skipped: 0, files: [] };
  }

  const files = fs.readdirSync(REVIEWS_DIR).filter(f => /^\d{4}-\d{2}-\d{2}\.md$/.test(f));
  const prisma = new PrismaClient();

  let imported = 0;
  let skipped = 0;
  const importedFiles: string[] = [];

  try {
    for (const file of files) {
      const date = file.replace('.md', '');
      // Use UTC date to avoid timezone issues
      const reviewDate = new Date(`${date}T00:00:00.000Z`);

      // Check if already imported (has rawMarkdown set)
      const existing = await prisma.review.findFirst({
        where: {
          projectId,
          reviewDate,
          rawMarkdown: { not: null },
        },
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
        console.error(`[MarkdownImport] Failed to import ${file}:`, e);
      }
    }
  } finally {
    await prisma.$disconnect();
  }

  return { imported, skipped, files: importedFiles };
}
