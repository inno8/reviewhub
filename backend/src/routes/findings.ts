import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';
import { notifyExplanationRequested } from '../services/telegram';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

router.get('/', async (req: Request, res: Response): Promise<void> => {
  const { projectId, category, difficulty } = req.query;

  const findings = await prisma.finding.findMany({
    where: {
      ...(projectId && { review: { projectId: parseInt(projectId as string) } }),
      ...(category && { category: category as any }),
      ...(difficulty && { difficulty: difficulty as any }),
    },
    include: {
      review: {
        include: { project: { select: { name: true, displayName: true } } },
      },
      userFindings: {
        where: { userId: req.user!.userId },
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json({ findings });
});

router.get('/:id', async (req: Request, res: Response): Promise<void> => {
  const finding = await prisma.finding.findUnique({
    where: { id: parseInt(req.params.id) },
    include: {
      review: {
        include: { project: true },
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

  res.json({ finding });
});

router.post('/:id/understand', async (req: Request, res: Response): Promise<void> => {
  const findingId = parseInt(req.params.id);
  const userId = req.user!.userId;

  const userFinding = await prisma.userFinding.upsert({
    where: { userId_findingId: { userId, findingId } },
    update: { markedUnderstood: true },
    create: { userId, findingId, markedUnderstood: true },
  });

  res.json({ userFinding });
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

  const [intern, finding] = await Promise.all([
    prisma.user.findUnique({
      where: { id: userId },
      select: { username: true },
    }),
    prisma.finding.findUnique({
      where: { id: findingId },
      select: {
        filePath: true,
        review: {
          include: {
            project: {
              select: { displayName: true },
            },
          },
        },
      },
    }),
  ]);

  if (intern && finding) {
    await notifyExplanationRequested(
      intern.username,
      finding.filePath,
      finding.review.project.displayName,
    );
  }

  res.json({ userFinding });
});

export default router;
