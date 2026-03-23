import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';

const router = Router();
const prisma = new PrismaClient();

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

export default router;
