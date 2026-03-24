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
  if (patch.includes('console.log') && !filename.includes('test')) {
    const match = patch.match(/\+.*console\.log\([^)]+\)/);
    if (match) {
      issues.push({
        lineStart: 1,
        lineEnd: 1,
        originalCode: match[0].replace(/^\+\s*/, ''),
        optimizedCode: '// Remove console.log in production\n// Or use a proper logging library',
        explanation: 'Console.log statements should be removed from production code. Use a proper logging library like winston or pino that can be configured per environment.',
        references: [{ type: 'docs', title: 'Winston Logger', url: 'https://github.com/winstonjs/winston' }],
        category: Category.CODE_STYLE,
        difficulty: Difficulty.BEGINNER,
      });
    }
  }

  // Check for TODO comments
  if (patch.includes('TODO') || patch.includes('FIXME')) {
    issues.push({
      lineStart: 1,
      lineEnd: 1,
      originalCode: '// TODO: ...',
      optimizedCode: '// Create a GitHub issue to track this task',
      explanation: 'TODO comments tend to be forgotten. Consider creating a GitHub issue to properly track this work item.',
      references: [],
      category: Category.CODE_STYLE,
      difficulty: Difficulty.BEGINNER,
    });
  }

  // Check for hardcoded URLs/secrets
  if (patch.match(/https?:\/\/[^\s"']+\.(com|io|org|net)/)) {
    issues.push({
      lineStart: 1,
      lineEnd: 1,
      originalCode: 'const url = "https://api.example.com"',
      optimizedCode: 'const url = process.env.API_URL',
      explanation: 'Hardcoded URLs should be moved to environment variables for flexibility across different environments.',
      references: [{ type: 'docs', title: 'Twelve-Factor App - Config', url: 'https://12factor.net/config' }],
      category: Category.SECURITY,
      difficulty: Difficulty.BEGINNER,
    });
  }

  return issues;
}

export default router;
