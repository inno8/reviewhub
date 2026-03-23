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
