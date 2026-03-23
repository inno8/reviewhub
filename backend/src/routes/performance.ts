import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';
import {
  calculatePerformance,
  getCodeProgression,
} from '../services/performance';
import type { Recommendation } from '../services/performance';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

const VALID_PERIODS = ['DAILY', 'WEEKLY', 'MONTHLY'] as const;
type PeriodTypeInput = (typeof VALID_PERIODS)[number];

function parsePeriodType(periodType: unknown): PeriodTypeInput {
  const candidate = String(periodType || 'WEEKLY').toUpperCase();
  if (VALID_PERIODS.includes(candidate as PeriodTypeInput)) {
    return candidate as PeriodTypeInput;
  }
  return 'WEEKLY';
}

function assertAccess(req: Request, userId: number): boolean {
  if (req.user!.role !== 'ADMIN' && userId !== req.user!.userId) {
    return false;
  }
  return true;
}

router.get('/leaderboard', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const projectId = Number(req.query.projectId);
  const periodType = parsePeriodType(req.query.periodType);

  if (!projectId) {
    res.status(400).json({ error: 'projectId is required' });
    return;
  }

  const usersInProject = await prisma.userProject.findMany({
    where: { projectId },
    include: { user: { select: { id: true, username: true } } },
  });

  const leaderboard = await Promise.all(
    usersInProject.map(async (relation) => {
      const current = await calculatePerformance(relation.user.id, projectId, periodType);
      const trends = await getCodeProgression(relation.user.id, projectId, 2);
      const previousFindingCount = trends[0]?.findingCount ?? current.findingCount;
      const improvementRate =
        previousFindingCount > 0
          ? Math.round(((previousFindingCount - current.findingCount) / previousFindingCount) * 100)
          : 0;

      return {
        userId: relation.user.id,
        username: relation.user.username,
        findingCount: current.findingCount,
        improvementRate,
      };
    }),
  );

  leaderboard.sort((a, b) => {
    if (a.findingCount !== b.findingCount) {
      return a.findingCount - b.findingCount;
    }
    return b.improvementRate - a.improvementRate;
  });

  res.json({ leaderboard });
});

router.get('/:userId', async (req: Request, res: Response): Promise<void> => {
  const userId = Number(req.params.userId);
  const projectId = Number(req.query.projectId);
  const periodType = parsePeriodType(req.query.periodType);

  if (!userId || !projectId) {
    res.status(400).json({ error: 'userId and projectId are required' });
    return;
  }

  if (!assertAccess(req, userId)) {
    res.status(403).json({ error: 'Access denied' });
    return;
  }

  const performance = await calculatePerformance(userId, projectId, periodType);
  res.json(performance);
});

router.get('/:userId/trends', async (req: Request, res: Response): Promise<void> => {
  const userId = Number(req.params.userId);
  const projectId = Number(req.query.projectId);
  const weeks = Math.max(1, Number(req.query.weeks || 8));

  if (!userId || !projectId) {
    res.status(400).json({ error: 'userId and projectId are required' });
    return;
  }

  if (!assertAccess(req, userId)) {
    res.status(403).json({ error: 'Access denied' });
    return;
  }

  const trends = await getCodeProgression(userId, projectId, weeks);
  res.json(trends);
});

router.get('/:userId/recommendations', async (req: Request, res: Response): Promise<void> => {
  const userId = Number(req.params.userId);
  const projectId = Number(req.query.projectId);

  if (!userId || !projectId) {
    res.status(400).json({ error: 'userId and projectId are required' });
    return;
  }

  if (!assertAccess(req, userId)) {
    res.status(403).json({ error: 'Access denied' });
    return;
  }

  const performance = await calculatePerformance(userId, projectId, 'WEEKLY');
  const grouped = performance.recommendations.reduce<Record<string, Recommendation[]>>(
    (acc, recommendation) => {
      acc[recommendation.category] = acc[recommendation.category] || [];
      acc[recommendation.category].push(recommendation);
      return acc;
    },
    {},
  );

  res.json({ recommendations: performance.recommendations, groupedByCategory: grouped });
});

export default router;
