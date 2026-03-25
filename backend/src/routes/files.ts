import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { authMiddleware } from '../middleware/auth';
import { getFileContent } from '../services/github';

const router = Router();
const prisma = new PrismaClient();

router.use(authMiddleware);

// GET /api/files/:projectId/:branch/:filePath
// Fetches file content from GitHub
// filePath should be URL-encoded (e.g., cart%2Ftemplates%2Fhome.html)
router.get('/:projectId/:branch/:filePath', async (req: Request, res: Response): Promise<void> => {
  const projectId = parseInt(req.params.projectId as string);
  const branch = req.params.branch as string;
  const filePath = decodeURIComponent(req.params.filePath as string);

  if (!projectId || !branch || !filePath) {
    res.status(400).json({ error: 'projectId, branch, and file path required' });
    return;
  }

  const project = await prisma.project.findUnique({ where: { id: projectId } });
  if (!project) {
    res.status(404).json({ error: 'Project not found' });
    return;
  }

  try {
    const data = await getFileContent(project.githubOwner, project.githubRepo, filePath, branch);

    if (Array.isArray(data) || !('content' in data) || data.type !== 'file') {
      res.status(400).json({ error: 'Path is not a file' });
      return;
    }

    // Decode base64 content
    const content = Buffer.from(data.content!, 'base64').toString('utf-8');

    res.json({
      content,
      path: filePath,
      sha: data.sha,
      size: data.size,
      encoding: 'utf-8',
    });
  } catch (error: any) {
    if (error.status === 404) {
      res.status(404).json({ error: 'File not found in repository' });
    } else {
      console.error('[GitHub] Failed to fetch file:', error);
      res.status(500).json({ error: 'Failed to fetch file from GitHub' });
    }
  }
});

export default router;
