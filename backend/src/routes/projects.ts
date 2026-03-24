import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { Octokit } from '@octokit/rest';
import { z } from 'zod';
import { authMiddleware } from '../middleware/auth';
import { adminMiddleware } from '../middleware/admin';

const router = Router();
const prisma = new PrismaClient();

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
});

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

// Get branches for a project
router.get('/:id/branches', async (req: Request, res: Response): Promise<void> => {
  const project = await prisma.project.findUnique({
    where: { id: parseInt(req.params.id) },
  });

  if (!project) {
    res.status(404).json({ error: 'Project not found' });
    return;
  }

  try {
    const { data: branches } = await octokit.repos.listBranches({
      owner: project.githubOwner,
      repo: project.githubRepo,
      per_page: 100,
    });

    res.json({
      branches: branches.map(b => ({
        name: b.name,
        protected: b.protected,
      })),
    });
  } catch (error: any) {
    console.error('[GitHub] Failed to fetch branches:', error);
    res.status(500).json({ error: 'Failed to fetch branches from GitHub' });
  }
});

const createProjectSchema = z.object({
  name: z.string().min(1),
  displayName: z.string().min(1),
  githubOwner: z.string().min(1),
  githubRepo: z.string().min(1),
});

// Parse GitHub URL to extract owner and repo
function parseGitHubUrl(url: string): { owner: string; repo: string } | null {
  // Handle various formats:
  // https://github.com/owner/repo
  // https://github.com/owner/repo.git
  // git@github.com:owner/repo.git
  // owner/repo
  
  let match = url.match(/github\.com[\/:]([^\/]+)\/([^\/\.]+)/);
  if (match) {
    return { owner: match[1], repo: match[2] };
  }
  
  // Simple owner/repo format
  match = url.match(/^([^\/]+)\/([^\/]+)$/);
  if (match) {
    return { owner: match[1], repo: match[2] };
  }
  
  return null;
}

// Create project from GitHub URL
router.post('/from-url', adminMiddleware, async (req: Request, res: Response): Promise<void> => {
  const { url } = req.body;
  
  if (!url) {
    res.status(400).json({ error: 'GitHub URL is required' });
    return;
  }

  const parsed = parseGitHubUrl(url);
  if (!parsed) {
    res.status(400).json({ error: 'Invalid GitHub URL format' });
    return;
  }

  // Verify repo exists and is accessible
  try {
    const { data: repoData } = await octokit.repos.get({
      owner: parsed.owner,
      repo: parsed.repo,
    });

    // Check if project already exists
    const existing = await prisma.project.findUnique({
      where: { name: parsed.repo },
    });

    if (existing) {
      res.status(400).json({ error: 'Project already exists' });
      return;
    }

    // Create project
    const project = await prisma.project.create({
      data: {
        name: parsed.repo,
        displayName: repoData.name,
        githubOwner: parsed.owner,
        githubRepo: parsed.repo,
      },
    });

    // Assign the current user to the project
    await prisma.userProject.create({
      data: {
        userId: req.user!.userId,
        projectId: project.id,
      },
    });

    res.status(201).json({ 
      project,
      message: `Project "${repoData.name}" created successfully!`,
    });
  } catch (error: any) {
    if (error.status === 404) {
      res.status(404).json({ error: 'Repository not found or not accessible' });
      return;
    }
    console.error('[GitHub] Failed to verify repo:', error);
    res.status(500).json({ error: 'Failed to verify GitHub repository' });
  }
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
