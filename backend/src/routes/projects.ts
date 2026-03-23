import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { z } from 'zod';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

router.get('/', async (_req: Request, res: Response): Promise<void> => {
  const projects = await prisma.project.findMany({
    include: { _count: { select: { reviews: true, users: true } } },
    orderBy: { createdAt: 'desc' },
  });
  res.json({ projects });
});

router.get('/:id', async (req: Request, res: Response): Promise<void> => {
  const project = await prisma.project.findUnique({
    where: { id: parseInt(req.params.id) },
    include: {
      users: { include: { user: { select: { id: true, username: true, email: true, role: true } } } },
      _count: { select: { reviews: true } },
    },
  });

  if (!project) {
    res.status(404).json({ error: 'Project not found' });
    return;
  }

  res.json({ project });
});

const createProjectSchema = z.object({
  name: z.string().min(1),
  displayName: z.string().min(1),
  githubOwner: z.string().min(1),
  githubRepo: z.string().min(1),
});

router.post('/', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  try {
    const data = createProjectSchema.parse(req.body);
    const project = await prisma.project.create({ data });
    res.status(201).json({ project });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

export default router;
