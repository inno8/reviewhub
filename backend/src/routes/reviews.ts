import { Router, Request, Response } from 'express';
import { PrismaClient, Category, Difficulty } from '@prisma/client';
import { Octokit } from '@octokit/rest';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';

const router = Router();
const prisma = new PrismaClient();

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
});

router.use(authMiddleware);

router.get('/', async (req: Request, res: Response): Promise<void> => {
  const { projectId } = req.query;

  const reviews = await prisma.review.findMany({
    where: projectId ? { projectId: parseInt(projectId as string) } : undefined,
    include: {
      project: { select: { name: true, displayName: true } },
      _count: { select: { findings: true } },
    },
    orderBy: { reviewDate: 'desc' },
  });

  res.json({ reviews });
});

router.get('/calendar', async (req: Request, res: Response): Promise<void> => {
  const { projectId, month } = req.query;
  const parsedProjectId = Number(projectId);

  if (!parsedProjectId || !month || !/^\d{4}-\d{2}$/.test(month as string)) {
    res.status(400).json({ error: 'projectId and month (YYYY-MM) are required' });
    return;
  }

  const [year, monthNumber] = (month as string).split('-').map(Number);
  const start = new Date(year, monthNumber - 1, 1);
  const end = new Date(year, monthNumber, 1);

  const findings = await prisma.finding.findMany({
    where: {
      review: {
        projectId: parsedProjectId,
        reviewDate: {
          gte: start,
          lt: end,
        },
      },
    },
    select: {
      review: {
        select: {
          reviewDate: true,
        },
      },
    },
  });

  const dates = Array.from(
    new Set(findings.map((finding) => finding.review.reviewDate.toISOString().slice(0, 10))),
  );

  res.json({ dates });
});

router.get('/:id', async (req: Request, res: Response): Promise<void> => {
  const review = await prisma.review.findUnique({
    where: { id: parseInt(req.params.id) },
    include: {
      project: true,
      findings: {
        include: {
          userFindings: {
            where: { userId: req.user!.userId },
          },
        },
      },
    },
  });

  if (!review) {
    res.status(404).json({ error: 'Review not found' });
    return;
  }

  res.json({ review });
});

// Trigger a new code review
router.post('/trigger', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { projectId, branches } = req.body;

  if (!projectId) {
    res.status(400).json({ error: 'projectId is required' });
    return;
  }

  const project = await prisma.project.findUnique({
    where: { id: projectId },
  });

  if (!project) {
    res.status(404).json({ error: 'Project not found' });
    return;
  }

  // Get branches to review (all if not specified)
  let branchesToReview = branches || [];
  if (branchesToReview.length === 0) {
    try {
      const { data: repoBranches } = await octokit.repos.listBranches({
        owner: project.githubOwner,
        repo: project.githubRepo,
        per_page: 100,
      });
      branchesToReview = repoBranches.map(b => b.name);
    } catch (error) {
      console.error('[GitHub] Failed to fetch branches:', error);
      res.status(500).json({ error: 'Failed to fetch branches from GitHub' });
      return;
    }
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const results: { branch: string; findingsCount: number }[] = [];

  for (const branch of branchesToReview) {
    try {
      // Get recent commits on this branch
      const { data: commits } = await octokit.repos.listCommits({
        owner: project.githubOwner,
        repo: project.githubRepo,
        sha: branch,
        since: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // Last 24h
        per_page: 20,
      });

      if (commits.length === 0) continue;

      // Check if we already have a review for this branch today
      let review = await prisma.review.findUnique({
        where: {
          projectId_branch_reviewDate: {
            projectId: project.id,
            branch,
            reviewDate: today,
          },
        },
      });

      if (!review) {
        review = await prisma.review.create({
          data: {
            projectId: project.id,
            branch,
            reviewDate: today,
            rawMarkdown: `# Code Review - ${branch}\n\nTriggered on ${new Date().toISOString()}`,
          },
        });
      }

      // Analyze commits and create findings (simplified - in real implementation would use AI)
      let findingsCount = 0;
      for (const commit of commits.slice(0, 5)) {
        // Get commit details
        const { data: commitDetail } = await octokit.repos.getCommit({
          owner: project.githubOwner,
          repo: project.githubRepo,
          ref: commit.sha,
        });

        // Check files for common patterns (simplified analysis)
        for (const file of commitDetail.files || []) {
          if (!file.filename || file.status === 'removed') continue;
          
          // Skip non-code files
          const ext = file.filename.split('.').pop()?.toLowerCase();
          if (!['js', 'ts', 'py', 'html', 'vue', 'jsx', 'tsx', 'css', 'scss'].includes(ext || '')) continue;

          // Check for patterns (very simplified - real implementation would use AI)
          const issues = analyzeFilePatterns(file.patch || '', file.filename);
          
          for (const issue of issues) {
            // Check if finding already exists
            const existingFinding = await prisma.finding.findFirst({
              where: {
                reviewId: review.id,
                filePath: file.filename,
                commitSha: commit.sha.slice(0, 7),
              },
            });

            if (!existingFinding) {
              await prisma.finding.create({
                data: {
                  reviewId: review.id,
                  commitSha: commit.sha.slice(0, 7),
                  commitAuthor: commit.commit.author?.name || 'Unknown',
                  filePath: file.filename,
                  lineStart: issue.lineStart,
                  lineEnd: issue.lineEnd,
                  originalCode: issue.originalCode,
                  optimizedCode: issue.optimizedCode,
                  explanation: issue.explanation,
                  references: JSON.stringify(issue.references),
                  category: issue.category,
                  difficulty: issue.difficulty,
                },
              });
              findingsCount++;
            }
          }
        }
      }

      if (findingsCount > 0) {
        results.push({ branch, findingsCount });
      }
    } catch (error) {
      console.error(`[Review] Failed to analyze branch ${branch}:`, error);
    }
  }

  const totalFindings = results.reduce((sum, r) => sum + r.findingsCount, 0);

  res.json({
    success: true,
    message: totalFindings > 0 
      ? `Review complete! Found ${totalFindings} issues across ${results.length} branches.`
      : 'Review complete. No new issues found.',
    results,
    totalFindings,
  });
});

// Calculate the actual line number from a diff patch at a given character position
function calculateLineNumber(patch: string, position: number): number {
  const textBefore = patch.slice(0, position);
  // Find the last @@ header before this position
  const headers = [...textBefore.matchAll(/@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/g)];
  if (headers.length === 0) return 1;

  const lastHeader = headers[headers.length - 1];
  const startLine = parseInt(lastHeader[1], 10);
  const afterHeader = textBefore.slice(lastHeader.index! + lastHeader[0].length);

  // Count added/context lines (lines starting with + or space, not -)
  const lines = afterHeader.split('\n');
  let lineOffset = 0;
  for (const line of lines) {
    if (line.startsWith('+') || line.startsWith(' ')) {
      lineOffset++;
    }
  }

  return startLine + Math.max(0, lineOffset - 1);
}

// Simple pattern analysis (would be replaced by AI in production)
function analyzeFilePatterns(patch: string, filename: string): Array<{
  lineStart: number;
  lineEnd: number;
  originalCode: string;
  optimizedCode: string;
  explanation: string;
  references: Array<{ type: string; title: string; url: string }>;
  category: Category;
  difficulty: Difficulty;
}> {
  const issues: any[] = [];

  // Check for console.log in production code
  if (!filename.includes('test')) {
    const consoleMatches = patch.matchAll(/\+(.*(console\.log\([^)]*\)).*)/g);
    for (const match of consoleMatches) {
      const actualLine = match[1].trim();
      const lineNum = calculateLineNumber(patch, match.index!);
      issues.push({
        lineStart: lineNum,
        lineEnd: lineNum,
        originalCode: actualLine,
        optimizedCode: '// Remove console.log in production\n// Or use a proper logging library',
        explanation: 'Console.log statements should be removed from production code. Use a proper logging library like winston or pino that can be configured per environment.',
        references: [{ type: 'docs', title: 'Winston Logger', url: 'https://github.com/winstonjs/winston' }],
        category: Category.CODE_STYLE,
        difficulty: Difficulty.BEGINNER,
      });
    }
  }

  // Check for TODO/FIXME comments - extract actual line
  const todoMatches = patch.matchAll(/\+(.*(?:TODO|FIXME)[^\n]*)/g);
  for (const match of todoMatches) {
    const actualLine = match[1].trim();
    const lineNum = calculateLineNumber(patch, match.index!);
    issues.push({
      lineStart: lineNum,
      lineEnd: lineNum,
      originalCode: actualLine,
      optimizedCode: '// Create a GitHub issue to track this task',
      explanation: `TODO/FIXME comment found: "${actualLine}". These tend to be forgotten. Consider creating a GitHub issue to properly track this work item.`,
      references: [],
      category: Category.CODE_STYLE,
      difficulty: Difficulty.BEGINNER,
    });
  }

  // Check for hardcoded URLs - extract actual code and URL
  const urlMatches = patch.matchAll(/\+(.*(https?:\/\/[^\s"'`]+\.(com|io|org|net)[^\s"'`]*).*)/g);
  for (const match of urlMatches) {
    const actualLine = match[1].trim();
    const actualUrl = match[2];
    const lineNum = calculateLineNumber(patch, match.index!);
    issues.push({
      lineStart: lineNum,
      lineEnd: lineNum,
      originalCode: actualLine,
      optimizedCode: actualLine.replace(actualUrl, 'process.env.API_URL'),
      explanation: `Hardcoded URL "${actualUrl}" should be moved to environment variables for flexibility across different environments.`,
      references: [{ type: 'docs', title: 'Twelve-Factor App - Config', url: 'https://12factor.net/config' }],
      category: Category.SECURITY,
      difficulty: Difficulty.BEGINNER,
    });
  }

  return issues;
}

export default router;
