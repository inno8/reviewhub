import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { Octokit } from '@octokit/rest';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';
import { applyFixAndCreatePR } from '../services/github';
import { notifyExplanationRequested } from '../services/telegram';

const router = Router();
const prisma = new PrismaClient();

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
});

router.use(authMiddleware);

function parseReferences(references: string | null) {
  if (!references) return [];
  try {
    const parsed = JSON.parse(references);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

router.get('/', async (req: Request, res: Response): Promise<void> => {
  const { projectId, date, category, difficulty, author, page = '1', limit = '10' } = req.query;
  const parsedPage = Math.max(1, Number(page));
  const parsedLimit = Math.max(1, Number(limit));
  const parsedProjectId = projectId ? Number(projectId) : undefined;

  const where = {
    where: {
      ...(parsedProjectId && { review: { projectId: parsedProjectId } }),
      ...(date && {
        review: {
          ...(parsedProjectId ? { projectId: parsedProjectId } : {}),
          reviewDate: {
            gte: new Date(`${date as string}T00:00:00.000Z`),
            lt: new Date(`${date as string}T23:59:59.999Z`),
          },
        },
      }),
      ...(category && { category: category as any }),
      ...(difficulty && { difficulty: difficulty as any }),
      ...(author && { commitAuthor: { equals: author as string } }),
    },
  };

  const [findings, total] = await Promise.all([
    prisma.finding.findMany({
      ...where,
      include: {
        review: {
          include: { project: { select: { name: true, displayName: true } } },
        },
        userFindings: {
          where: { userId: req.user!.userId },
        },
      },
      orderBy: { createdAt: 'desc' },
      skip: (parsedPage - 1) * parsedLimit,
      take: parsedLimit,
    }),
    prisma.finding.count(where),
  ]);

  res.json({
    findings: findings.map((finding) => ({
      ...finding,
      references: parseReferences(finding.references),
      markedUnderstood: finding.userFindings[0]?.markedUnderstood ?? false,
      explanationRequested: finding.userFindings[0]?.explanationRequested ?? false,
    })),
    total,
    page: parsedPage,
    totalPages: Math.max(1, Math.ceil(total / parsedLimit)),
  });
});

router.get('/:id', async (req: Request, res: Response): Promise<void> => {
  const finding = await prisma.finding.findUnique({
    where: { id: parseInt(req.params.id) },
    include: {
      review: {
        include: { project: { select: { id: true, name: true, displayName: true } } },
      },
      userFindings: {
        where: { userId: req.user!.userId },
      },
    },
  });

  if (!finding) {
    res.status(404).json({ error: 'Finding not found' });
    return;
  }

  res.json({
    finding: {
      ...finding,
      references: parseReferences(finding.references),
      markedUnderstood: finding.userFindings[0]?.markedUnderstood ?? false,
      explanationRequested: finding.userFindings[0]?.explanationRequested ?? false,
      review: {
        ...finding.review,
        reviewDate: finding.review.reviewDate.toISOString().slice(0, 10),
      },
    },
  });
});

router.patch('/:id/understood', async (req: Request, res: Response): Promise<void> => {
  const findingId = parseInt(req.params.id);
  const userId = req.user!.userId;

  const existing = await prisma.userFinding.findUnique({
    where: { userId_findingId: { userId, findingId } },
  });
  const nextState = !(existing?.markedUnderstood ?? false);

  const userFinding = await prisma.userFinding.upsert({
    where: { userId_findingId: { userId, findingId } },
    update: { markedUnderstood: nextState },
    create: { userId, findingId, markedUnderstood: nextState },
  });

  res.json({ markedUnderstood: userFinding.markedUnderstood });
});

router.post('/:id/request-explanation', async (req: Request, res: Response): Promise<void> => {
  const findingId = parseInt(req.params.id);
  const userId = req.user!.userId;

  const userFinding = await prisma.userFinding.upsert({
    where: { userId_findingId: { userId, findingId } },
    update: { explanationRequested: true, explanationRequestedAt: new Date() },
    create: {
      userId,
      findingId,
      explanationRequested: true,
      explanationRequestedAt: new Date(),
    },
  });

  const [intern, findingWithProject] = await Promise.all([
    prisma.user.findUnique({
      where: { id: userId },
    }),
    prisma.finding.findUnique({
      where: { id: findingId },
      include: {
        review: {
          include: {
            project: true,
          },
        },
      },
    }),
  ]);

  if (intern && findingWithProject) {
    try {
      await notifyExplanationRequested(intern, findingWithProject, findingWithProject.review.project);
    } catch (err) {
      console.error('[Telegram] Failed to send explanation notification:', err);
    }
  }

  res.json({ success: true, explanationRequested: userFinding.explanationRequested });
});

// Fetch file content from GitHub
router.get('/:id/file-content', async (req: Request, res: Response): Promise<void> => {
  const findingId = parseInt(req.params.id);
  const finding = await prisma.finding.findUnique({
    where: { id: findingId },
    include: {
      review: {
        include: {
          project: true,
        },
      },
    },
  });

  if (!finding) {
    res.status(404).json({ error: 'Finding not found' });
    return;
  }

  const { project } = finding.review;
  const branch = finding.review.branch || 'main';

  try {
    const response = await octokit.repos.getContent({
      owner: project.githubOwner,
      repo: project.githubRepo,
      path: finding.filePath,
      ref: branch,
    });

    if ('content' in response.data && response.data.type === 'file') {
      const content = Buffer.from(response.data.content, 'base64').toString('utf-8');
      res.json({
        content,
        filePath: finding.filePath,
        branch,
        sha: response.data.sha,
      });
    } else {
      res.status(400).json({ error: 'Not a file' });
    }
  } catch (error: any) {
    console.error('[GitHub] Failed to fetch file content:', error);
    // Return the original code as fallback
    res.json({
      content: finding.originalCode,
      filePath: finding.filePath,
      branch,
      sha: null,
      fallback: true,
    });
  }
});

router.post('/:id/apply-fix', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const findingId = parseInt(req.params.id);
  const finding = await prisma.finding.findUnique({
    where: { id: findingId },
    include: {
      review: {
        include: {
          project: true,
        },
      },
    },
  });

  if (!finding) {
    res.status(404).json({ error: 'Finding not found' });
    return;
  }

  try {
    const prUrl = await applyFixAndCreatePR(finding, finding.review, finding.review.project);

    await prisma.finding.update({
      where: { id: finding.id },
      data: {
        prCreated: true,
        prUrl,
      },
    });

    res.json({ prUrl });
  } catch (error: any) {
    res.status(500).json({ error: error?.message || 'Failed to apply fix and create PR' });
  }
});

export default router;
