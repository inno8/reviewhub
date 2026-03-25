import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';
import { calculateSkillScores, getUserSkillsByCategory } from '../services/skillMapping';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

// GET /api/skills/categories - List all skill categories with skills
router.get('/categories', async (_req: Request, res: Response): Promise<void> => {
  const categories = await prisma.skillCategory.findMany({
    include: { skills: true },
    orderBy: { id: 'asc' },
  });
  res.json({ categories });
});

// GET /api/skills/user/:userId - Get user's skill scores grouped by category
router.get('/user/:userId', async (req: Request, res: Response): Promise<void> => {
  const userId = Number(req.params.userId);
  if (!userId) {
    res.status(400).json({ error: 'userId is required' });
    return;
  }

  // Allow admin to view any user, otherwise only own skills
  if (req.user!.role !== 'ADMIN' && userId !== req.user!.userId) {
    res.status(403).json({ error: 'Access denied' });
    return;
  }

  const categories = await getUserSkillsByCategory(userId);
  res.json({ categories });
});

// POST /api/skills/recalculate/:userId - Recalculate scores from findings
router.post('/recalculate/:userId', async (req: Request, res: Response): Promise<void> => {
  const userId = Number(req.params.userId);
  const projectId = Number(req.query.projectId);

  if (!userId || !projectId) {
    res.status(400).json({ error: 'userId and projectId are required' });
    return;
  }

  if (req.user!.role !== 'ADMIN' && userId !== req.user!.userId) {
    res.status(403).json({ error: 'Access denied' });
    return;
  }

  const userSkills = await calculateSkillScores(userId, projectId);
  const categories = await getUserSkillsByCategory(userId);
  res.json({ updated: userSkills.length, categories });
});

export default router;
