import { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import { PrismaClient } from '@prisma/client';
import { z } from 'zod';
import { signToken, verifyToken } from '../utils/jwt';

const router = Router();
const prisma = new PrismaClient();

const checkEmailSchema = z.object({
  email: z.string().email(),
});

const verifyCodeSchema = z.object({
  email: z.string().email(),
  code: z.string().length(5),
});

const setPasswordSchema = z.object({
  token: z.string(),
  password: z.string().min(8),
});

function generateCode(): string {
  return Math.floor(10000 + Math.random() * 90000).toString();
}

router.post('/check-email', async (req: Request, res: Response): Promise<void> => {
  try {
    const { email } = checkEmailSchema.parse(req.body);

    const user = await prisma.user.findUnique({ where: { email } });
    if (!user) {
      res.json({ found: false });
      return;
    }

    if (user.onboardCompleted) {
      res.json({ found: true, alreadyOnboarded: true });
      return;
    }

    const code = generateCode();
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000); // 15 minutes

    await prisma.onboardCode.create({
      data: {
        userId: user.id,
        code,
        expiresAt,
      },
    });

    // Log code to console (configure SMTP later for real email)
    console.log(`[ONBOARD] Code for ${email}: ${code}`);

    res.json({ found: true, username: user.username, codeSent: true });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

router.post('/verify-code', async (req: Request, res: Response): Promise<void> => {
  try {
    const { email, code } = verifyCodeSchema.parse(req.body);

    const user = await prisma.user.findUnique({ where: { email } });
    if (!user) {
      res.status(400).json({ valid: false, error: 'User not found' });
      return;
    }

    const onboardCode = await prisma.onboardCode.findFirst({
      where: {
        userId: user.id,
        code,
        used: false,
        expiresAt: { gt: new Date() },
      },
      orderBy: { createdAt: 'desc' },
    });

    if (!onboardCode) {
      res.json({ valid: false, error: 'Invalid or expired code' });
      return;
    }

    await prisma.onboardCode.update({
      where: { id: onboardCode.id },
      data: { used: true },
    });

    // Short-lived token (10 minutes) for password setting
    const token = signToken({ userId: user.id, role: 'ONBOARD' });

    res.json({ valid: true, token });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

router.post('/set-password', async (req: Request, res: Response): Promise<void> => {
  try {
    const { token, password } = setPasswordSchema.parse(req.body);

    let payload;
    try {
      payload = verifyToken(token);
    } catch {
      res.status(401).json({ success: false, error: 'Invalid or expired token' });
      return;
    }

    const passwordHash = await bcrypt.hash(password, 12);

    await prisma.user.update({
      where: { id: payload.userId },
      data: { passwordHash, onboardCompleted: true },
    });

    res.json({ success: true });
  } catch (err) {
    if (err instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: err.errors });
      return;
    }
    throw err;
  }
});

export default router;
