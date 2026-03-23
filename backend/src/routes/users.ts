import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

router.get('/', adminMiddleware, async (_req: Request, res: Response): Promise<void> => {
  const users = await prisma.user.findMany({
    select: {
      id: true,
      username: true,
      email: true,
      role: true,
      telegramChatId: true,
      createdAt: true,
      _count: { select: { projects: true, findings: true } },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json({ users });
});

router.put('/:id/role', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { role } = req.body;
  if (!['ADMIN', 'INTERN'].includes(role)) {
    res.status(400).json({ error: 'Invalid role' });
    return;
  }

  const user = await prisma.user.update({
    where: { id: parseInt(req.params.id) },
    data: { role },
    select: { id: true, username: true, email: true, role: true },
  });

  res.json({ user });
});

export default router;
