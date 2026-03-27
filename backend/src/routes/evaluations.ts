import { Router, Request, Response } from 'express';
import { PrismaClient, Category, Difficulty } from '@prisma/client';

const router = Router();
const prisma = new PrismaClient();

/**
 * Internal API for AI Engine webhook to store evaluation results.
 * No auth required - should only be accessible from localhost or via API key.
 */
router.post('/internal', async (req: Request, res: Response): Promise<void> => {
  const {
    project_id,
    commit_sha,
    commit_message,
    commit_timestamp,
    branch,
    author_name,
    author_email,
    files_changed,
    lines_added,
    lines_removed,
    overall_score,
    llm_model,
    llm_tokens_used,
    processing_ms,
    findings,
  } = req.body;

  try {
    // Validate required fields
    if (!project_id || !commit_sha || !branch) {
      res.status(400).json({ error: 'Missing required fields: project_id, commit_sha, branch' });
      return;
    }

    // Parse review date from commit timestamp or use current date
    const reviewDate = commit_timestamp ? new Date(commit_timestamp) : new Date();

    // Create or update review
    const review = await prisma.review.upsert({
      where: {
        projectId_branch_reviewDate: {
          projectId: project_id,
          branch,
          reviewDate: new Date(reviewDate.toISOString().slice(0, 10)),
        },
      },
      update: {},
      create: {
        projectId: project_id,
        branch,
        reviewDate: new Date(reviewDate.toISOString().slice(0, 10)),
        rawMarkdown: `# Code Review for ${commit_sha.slice(0, 7)}\n\n**Commit:** ${commit_message}\n**Author:** ${author_name} <${author_email}>\n**Files Changed:** ${files_changed}\n**Lines:** +${lines_added}/-${lines_removed}\n**Overall Score:** ${overall_score}/100\n**Model:** ${llm_model}\n**Tokens:** ${llm_tokens_used}\n**Processing:** ${processing_ms}ms`,
      },
    });

    // Create findings
    const createdFindings = [];
    for (const finding of findings || []) {
      const categoryMap: Record<string, Category> = {
        security: 'SECURITY',
        performance: 'PERFORMANCE',
        'code style': 'CODE_STYLE',
        'code_style': 'CODE_STYLE',
        testing: 'TESTING',
        architecture: 'ARCHITECTURE',
        documentation: 'DOCUMENTATION',
      };

      const difficultyMap: Record<string, Difficulty> = {
        critical: 'ADVANCED',
        warning: 'INTERMEDIATE',
        info: 'BEGINNER',
        suggestion: 'BEGINNER',
      };

      // Determine category from skills or default to CODE_STYLE
      let category: Category = 'CODE_STYLE';
      const skills = finding.skills_affected || [];
      if (skills.some((s: string) => s.includes('security') || s.includes('auth'))) {
        category = 'SECURITY';
      } else if (skills.some((s: string) => s.includes('performance') || s.includes('algorithm'))) {
        category = 'PERFORMANCE';
      } else if (skills.some((s: string) => s.includes('test'))) {
        category = 'TESTING';
      } else if (skills.some((s: string) => s.includes('solid') || s.includes('pattern') || s.includes('abstraction'))) {
        category = 'ARCHITECTURE';
      } else if (skills.some((s: string) => s.includes('comment') || s.includes('docs'))) {
        category = 'DOCUMENTATION';
      }

      // Map severity to difficulty
      const difficulty = difficultyMap[finding.severity] || 'INTERMEDIATE';

      const created = await prisma.finding.create({
        data: {
          reviewId: review.id,
          commitSha: commit_sha,
          commitAuthor: author_name,
          filePath: finding.file_path || 'unknown',
          lineStart: finding.line_start || 1,
          lineEnd: finding.line_end || 1,
          originalCode: finding.original_code || '',
          optimizedCode: finding.suggested_code || '',
          explanation: finding.explanation || finding.description || '',
          references: null,
          skills: JSON.stringify(finding.skills_affected || []),
          category,
          difficulty,
        },
      });

      createdFindings.push(created);
    }

    res.status(201).json({
      id: review.id,
      review,
      findings: createdFindings,
      message: `Created review with ${createdFindings.length} findings`,
    });
  } catch (error: any) {
    console.error('[Internal API] Error creating evaluation:', error);
    res.status(500).json({ error: error.message || 'Failed to create evaluation' });
  }
});

export default router;
