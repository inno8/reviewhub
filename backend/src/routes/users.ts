import { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import { PrismaClient } from '@prisma/client';
import { z } from 'zod';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

const roleSchema = z.enum(['ADMIN', 'INTERN']);

const createUserSchema = z.object({
  username: z.string().min(3).max(30),
  email: z.string().email(),
  password: z.string().min(6),
  role: roleSchema.default('INTERN'),
  projectIds: z.array(z.number().int().positive()).default([]),
});

const updateUserSchema = z.object({
  username: z.string().min(3).max(30).optional(),
  email: z.string().email().optional(),
  password: z.string().min(6).optional(),
  role: roleSchema.optional(),
  projectIds: z.array(z.number().int().positive()).optional(),
});

router.get('/', adminMiddleware, async (_req: Request, res: Response): Promise<void> => {
  const users = await prisma.user.findMany({
    select: {
      id: true,
      username: true,
      email: true,
      role: true,
      telegramChatId: true,
      createdAt: true,
      projects: {
        select: {
          project: {
            select: { id: true, name: true, displayName: true },
          },
        },
      },
      _count: { select: { projects: true, findings: true } },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json({
    users: users.map((user) => ({
      ...user,
      projects: user.projects.map((relation) => relation.project),
    })),
  });
});

router.post('/', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  try {
    const payload = createUserSchema.parse(req.body);

    const existing = await prisma.user.findFirst({
      where: {
        OR: [{ email: payload.email }, { username: payload.username }],
      },
    });

    if (existing) {
      res.status(409).json({ error: 'Username or email already exists' });
      return;
    }

    const passwordHash = await bcrypt.hash(payload.password, 12);
    const user = await prisma.user.create({
      data: {
        username: payload.username,
        email: payload.email,
        passwordHash,
        role: payload.role,
        projects: payload.projectIds.length
          ? {
              createMany: {
                data: payload.projectIds.map((projectId) => ({ projectId })),
                skipDuplicates: true,
              },
            }
          : undefined,
      },
      include: {
        projects: {
          include: {
            project: {
              select: { id: true, name: true, displayName: true },
            },
          },
        },
      },
    });

    res.status(201).json({
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role,
        projects: user.projects.map((relation) => relation.project),
      },
    });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

router.patch('/:id', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  try {
    const userId = parseInt(req.params.id);
    const payload = updateUserSchema.parse(req.body);

    const existingUser = await prisma.user.findUnique({ where: { id: userId } });
    if (!existingUser) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    if (payload.username || payload.email) {
      const duplicate = await prisma.user.findFirst({
        where: {
          id: { not: userId },
          OR: [
            ...(payload.email ? [{ email: payload.email }] : []),
            ...(payload.username ? [{ username: payload.username }] : []),
          ],
        },
      });

      if (duplicate) {
        res.status(409).json({ error: 'Username or email already exists' });
        return;
      }
    }

    await prisma.user.update({
      where: { id: userId },
      data: {
        ...(payload.username && { username: payload.username }),
        ...(payload.email && { email: payload.email }),
        ...(payload.role && { role: payload.role }),
        ...(payload.password && { passwordHash: await bcrypt.hash(payload.password, 12) }),
      },
    });

    if (payload.projectIds) {
      await prisma.userProject.deleteMany({ where: { userId } });
      if (payload.projectIds.length > 0) {
        await prisma.userProject.createMany({
          data: payload.projectIds.map((projectId) => ({ userId, projectId })),
          skipDuplicates: true,
        });
      }
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      include: {
        projects: {
          include: {
            project: {
              select: { id: true, name: true, displayName: true },
            },
          },
        },
      },
    });

    res.json({
      user: {
        id: user!.id,
        username: user!.username,
        email: user!.email,
        role: user!.role,
        projects: user!.projects.map((relation) => relation.project),
      },
    });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

router.delete('/:id', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const userId = parseInt(req.params.id);
  const existingUser = await prisma.user.findUnique({ where: { id: userId } });
  if (!existingUser) {
    res.status(404).json({ error: 'User not found' });
    return;
  }
  await prisma.user.delete({ where: { id: userId } });
  res.json({ success: true });
});

router.get('/:id/projects', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const userId = parseInt(req.params.id);
  const projects = await prisma.userProject.findMany({
    where: { userId },
    include: {
      project: {
        select: { id: true, name: true, displayName: true },
      },
    },
  });
  res.json({ projects: projects.map((relation) => relation.project) });
});

router.post('/:id/projects', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const userId = parseInt(req.params.id);
  const bodySchema = z.object({
    projectIds: z.array(z.number().int().positive()),
  });

  try {
    const { projectIds } = bodySchema.parse(req.body);

    const existingUser = await prisma.user.findUnique({ where: { id: userId } });
    if (!existingUser) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    await prisma.userProject.deleteMany({ where: { userId } });
    if (projectIds.length > 0) {
      await prisma.userProject.createMany({
        data: projectIds.map((projectId) => ({ userId, projectId })),
        skipDuplicates: true,
      });
    }

    const projects = await prisma.userProject.findMany({
      where: { userId },
      include: {
        project: {
          select: { id: true, name: true, displayName: true },
        },
      },
    });

    res.json({ projects: projects.map((relation) => relation.project) });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

export default router;
