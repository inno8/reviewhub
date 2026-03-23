import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

router.get('/', async (req: Request, res: Response): Promise<void> => {
  const { userId, projectId, periodType } = req.query;

  const targetUserId = userId ? parseInt(userId as string) : req.user!.userId;

  // Non-admins can only view their own metrics
  if (req.user!.role !== 'ADMIN' && targetUserId !== req.user!.userId) {
    res.status(403).json({ error: 'Access denied' });
    return;
  }

  const metrics = await prisma.performanceMetric.findMany({
    where: {
      userId: targetUserId,
      ...(projectId && { projectId: parseInt(projectId as string) }),
      ...(periodType && { periodType: periodType as any }),
    },
    include: {
      project: { select: { name: true, displayName: true } },
    },
    orderBy: { periodStart: 'desc' },
  });

  res.json({ metrics });
});

export default router;
