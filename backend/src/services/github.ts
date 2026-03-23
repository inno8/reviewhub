import { Octokit } from '@octokit/rest';
import { Buffer } from 'buffer';
import type { Finding, Review, Project } from '@prisma/client';
import { config } from '../config';

const octokit = new Octokit({ auth: config.github.token });

export async function getRepoInfo(owner: string, repo: string) {
  const { data } = await octokit.repos.get({ owner, repo });
  return data;
}

export async function getCommits(owner: string, repo: string, branch: string, since?: string) {
  const { data } = await octokit.repos.listCommits({
    owner,
    repo,
    sha: branch,
    ...(since && { since }),
  });
  return data;
}

export async function getFileContent(owner: string, repo: string, path: string, ref?: string) {
  const { data } = await octokit.repos.getContent({
    owner,
    repo,
    path,
    ...(ref && { ref }),
  });
  return data;
}

function requireGithubToken() {
  if (!config.github.token || config.github.token === 'ghp_xxxxxxxxxxxxxxxxxxxx') {
    throw new Error('GitHub token is not configured');
  }
}

function buildPatchedFileContent(existingContent: string, finding: Finding): string {
  if (!finding.lineStart || !finding.lineEnd) {
    throw new Error('Finding does not include lineStart and lineEnd');
  }

  const sourceLines = existingContent.split('\n');
  const startIdx = Math.max(0, finding.lineStart - 1);
  const endIdx = Math.min(sourceLines.length, finding.lineEnd);
  const replacementLines = finding.optimizedCode.split('\n');

  return [...sourceLines.slice(0, startIdx), ...replacementLines, ...sourceLines.slice(endIdx)].join('\n');
}

export async function applyFixAndCreatePR(
  finding: Finding,
  review: Review,
  project: Project,
): Promise<string> {
  requireGithubToken();

  const owner = project.githubOwner;
  const repo = project.githubRepo;
  const sourceBranch = review.branch;
  const timestamp = Date.now();
  const fixBranch = `fix/finding-${finding.id}-${timestamp}`;

  try {
    const sourceBranchRef = await octokit.git.getRef({
      owner,
      repo,
      ref: `heads/${sourceBranch}`,
    });
    const sourceSha = sourceBranchRef.data.object.sha;

    await octokit.git.createRef({
      owner,
      repo,
      ref: `refs/heads/${fixBranch}`,
      sha: sourceSha,
    });

    const fileData = await octokit.repos.getContent({
      owner,
      repo,
      path: finding.filePath,
      ref: fixBranch,
    });

    if (!('content' in fileData.data) || !fileData.data.content) {
      throw new Error(`Unable to read file content for ${finding.filePath}`);
    }

    const decoded = Buffer.from(fileData.data.content, 'base64').toString('utf-8');
    const patched = buildPatchedFileContent(decoded, finding);

    await octokit.repos.createOrUpdateFileContents({
      owner,
      repo,
      path: finding.filePath,
      message: `fix: Apply code review suggestion for ${finding.filePath}`,
      content: Buffer.from(patched, 'utf-8').toString('base64'),
      branch: fixBranch,
      sha: fileData.data.sha,
    });

    const pullRequest = await octokit.pulls.create({
      owner,
      repo,
      title: `Fix: ${finding.category} issue in ${finding.filePath}`,
      body: [
        'This PR applies an automated code review suggestion.',
        '',
        `- File: \`${finding.filePath}\``,
        `- Category: ${finding.category}`,
        `- Difficulty: ${finding.difficulty}`,
        '',
        finding.explanation,
        '',
        `Finding ID: ${finding.id}`,
      ].join('\n'),
      base: 'main',
      head: fixBranch,
    });

    return pullRequest.data.html_url;
  } catch (error: any) {
    const message = error?.response?.data?.message || error?.message || 'Unknown GitHub error';
    throw new Error(`Failed to create pull request: ${message}`);
  }
}
