import { Octokit } from '@octokit/rest';
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
