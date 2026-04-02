import axios from 'axios';

export interface ReviewFilters {
  projectId?: number;
  date?: string;
  category?: string;
  difficulty?: string;
  author?: string;
  page?: number;
  limit?: number;
}

export type FindingFilters = ReviewFilters;

/** Django expects `project` query param; frontend uses `projectId`. */
function djangoListParams(params: ReviewFilters) {
  const { projectId, ...rest } = params;
  const out: Record<string, unknown> = { ...rest };
  if (projectId !== undefined && projectId !== null) {
    out.project = projectId;
  }
  return out;
}

export interface CreateUser {
  username: string;
  email: string;
  password: string;
  role?: 'ADMIN' | 'INTERN';
  projectIds?: number[];
}

export interface UpdateUser {
  username?: string;
  email?: string;
  password?: string;
  role?: 'ADMIN' | 'INTERN';
  telegramChatId?: string | null;
  projectIds?: number[];
}

export interface PerformanceParams {
  projectId?: number | null;
  periodType?: 'DAILY' | 'WEEKLY' | 'MONTHLY';
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:3000/api',
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('reviewhub_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Track if we're currently on a public page to prevent redirect loops
let skipAuthRedirect = false;
export function setSkipAuthRedirect(skip: boolean) {
  skipAuthRedirect = skip;
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      // Don't redirect if we're on a public page or during bootstrap
      const publicPaths = ['/login', '/onboard'];
      const isPublicPage = publicPaths.some(p => window.location.pathname.startsWith(p));
      if (!isPublicPage && !skipAuthRedirect) {
        localStorage.removeItem('reviewhub_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export const api = {
  onboard: {
    checkEmail: (email: string) => client.post('/onboard/check-email/', { email }),
    verifyCode: (email: string, code: string) => client.post('/onboard/verify-code/', { email, code }),
    setPassword: (token: string, password: string) => client.post('/onboard/set-password/', { token, password }),
  },
  auth: {
    // Django JWT authentication
    login: (email: string, password: string) => client.post('/auth/token/', { email, password }),
    register: (data: CreateUser) => client.post('/users/register/', data),
    me: () => client.get('/users/me/'),
    logout: () => {
      localStorage.removeItem('reviewhub_token');
      return Promise.resolve({ data: { message: 'Logged out' } });
    },
  },
  projects: {
    list: (params?: { page?: number }) => client.get('/projects/', { params }),
    get: (id: number) => client.get(`/projects/${id}/`),
    getBranches: (id: number) => client.get(`/projects/${id}/branches/`),
    createFromUrl: (url: string) => client.post('/projects/', { url }),
    create: (data: { name: string; description?: string; member_ids?: number[]; category_id?: number }) =>
      client.post('/projects/', data),
    update: (
      id: number,
      data: Partial<{
        name: string;
        description: string;
        default_branch: string;
        provider: string;
      }>,
    ) => client.patch(`/projects/${id}/`, data),
    delete: (id: number) => client.delete(`/projects/${id}/`),
    linkRepo: (id: number, repoUrl: string) =>
      client.patch(`/projects/${id}/link-repo/`, { repo_url: repoUrl }),
    unlinkRepo: (id: number) => client.post(`/projects/${id}/unlink-repo/`, {}),
  },
  evaluations: {
    list: (params: ReviewFilters = {}) => client.get('/evaluations/', { params: djangoListParams(params) }),
    get: (id: number) => client.get(`/evaluations/${id}/`),
    dashboard: (projectId?: number) => client.get('/evaluations/dashboard/', { params: { project: projectId } }),
    calendar: (projectId: number, month: string) => client.get('/evaluations/calendar/', { params: { project: projectId, month } }),
    trigger: (projectId: number, branches?: string[]) =>
      Promise.resolve({ data: { message: 'Use webhooks instead' } }),
    patterns: (projectId?: number) =>
      client.get('/evaluations/patterns/', { params: projectId ? { project: projectId } : {} }),
    resolvePattern: (id: number) => client.post(`/evaluations/patterns/${id}/resolve/`),
  },
  reviews: {
    list: (params: ReviewFilters = {}) => client.get('/evaluations/', { params: djangoListParams(params) }),
    calendar: (projectId: number, month: string) => client.get('/evaluations/calendar/', { params: { project: projectId, month } }),
    trigger: (projectId: number, branches?: string[]) => Promise.resolve({ data: { message: 'Use webhooks instead', totalFindings: 0 } }),
    importMarkdown: (projectId: number, date: string) => Promise.resolve({ data: { message: 'Not implemented' } }),
    syncMarkdown: (projectId: number) => Promise.resolve({ data: { message: 'Not implemented' } }),
  },
  findings: {
    list: (params: FindingFilters = {}) => client.get('/evaluations/findings/', { params: djangoListParams(params) }),
    get: (id: number) => client.get(`/evaluations/findings/${id}/`),
    markFixed: (id: number, commitSha?: string) => client.post(`/evaluations/findings/${id}/fix/`, { commit_sha: commitSha }),
    getFileContent: (id: number) =>
      client.get<{ content: string; detail?: string }>(`/evaluations/findings/${id}/file-content/`),
    markUnderstood: (_id: number) => Promise.resolve({ data: { markedUnderstood: true } }),
    requestExplanation: (_id: number) => Promise.resolve({ data: { message: 'Not implemented' } }),
    applyFix: (_id: number) => Promise.resolve({ data: { prUrl: '', message: 'Not implemented' } }),
  },
  files: {
    getContent: (projectId: number, branch: string, filePath: string) =>
      client.get(`/files/${projectId}/${encodeURIComponent(branch)}/${encodeURIComponent(filePath)}`),
  },
  users: {
    list: () => client.get('/users/'),
    me: () => client.get('/users/me/'),
    updateMe: (data: Omit<UpdateUser, 'role' | 'projectIds'>) => client.patch('/users/me/', data),
    create: (data: CreateUser) => client.post('/users/', data),
    update: (id: number, data: UpdateUser) => client.patch(`/users/${id}/`, data),
    delete: (id: number) => client.delete(`/users/${id}/`),
    getProjects: (id: number) => client.get(`/users/${id}/projects/`),
    assignProjects: (id: number, projectIds: number[]) => client.post(`/users/${id}/projects/`, { projectIds }),
    adminStats: (params?: { search?: string; category?: number }) =>
      client.get('/users/admin/stats/', { params }),
    /** Encrypted GitHub PAT for private repo branch listing (batch). */
    githubToken: {
      get: () =>
        client.get<{ configured: boolean; last_four: string | null }>('/users/me/github-token/'),
      save: (token: string) => client.post('/users/me/github-token/', { token }),
      delete: () => client.delete('/users/me/github-token/'),
    },
  },
  categories: {
    list: () => client.get('/users/categories/'),
    get: (id: number) => client.get(`/users/categories/${id}/`),
    create: (data: { name: string; description?: string; member_ids?: number[] }) =>
      client.post('/users/categories/', data),
    update: (id: number, data: { name?: string; description?: string; member_ids?: number[] }) =>
      client.patch(`/users/categories/${id}/`, data),
    delete: (id: number) => client.delete(`/users/categories/${id}/`),
  },
  performance: {
    get: (userId: number, params?: PerformanceParams) =>
      client.get(`/skills/performance/${userId}/`, {
        params:
          params?.projectId != null && params.projectId !== undefined
            ? { project: params.projectId }
            : {},
      }),
    trends: (userId: number, params?: { projectId?: number | null; weeks?: number }) =>
      client.get(`/skills/performance/${userId}/trends/`, {
        params: {
          ...(params?.projectId != null && params.projectId !== undefined
            ? { project: params.projectId }
            : {}),
          ...(params?.weeks != null ? { weeks: params.weeks } : {}),
        },
      }),
    recommendations: (userId: number, params: { projectId: number }) =>
      Promise.resolve({ data: [] }),
    leaderboard: (params: { projectId: number; periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY' }) =>
      Promise.resolve({ data: [] }),
  },
  skills: {
    categories: () => client.get('/skills/categories/'),
    user: (userId: number, projectId?: number) =>
      client.get(`/skills/user/${userId}/`, {
        params: projectId != null ? { project: projectId } : {},
      }),
    breakdown: (userId: number, skillId: number, projectId: number) =>
      client.get(`/skills/user/${userId}/breakdown/${skillId}/`, { params: { project: projectId } }),
    recalculate: (userId: number, projectId: number) =>
      Promise.resolve({ data: { success: true } }),
    recommendations: (projectId?: number) => client.get('/skills/recommendations/', { params: { project: projectId } }),
  },
  dashboard: {
    overview: (projectId?: number) => client.get('/skills/dashboard/overview/', { params: { project: projectId } }),
    skills: (projectId?: number) => client.get('/skills/dashboard/skills/', { params: { project: projectId } }),
    progress: (projectId?: number, weeks?: number) => client.get('/skills/dashboard/progress/', { params: { project: projectId, weeks } }),
    recent: (projectId?: number, limit?: number) => client.get('/skills/dashboard/recent/', { params: { project: projectId, limit } }),
  },
  notifications: {
    list: (limit?: number) => client.get('/notifications/', { params: { limit } }),
    markAsRead: (id: number) => client.patch(`/notifications/${id}/read/`),
    markAllRead: () => client.post('/notifications/mark-all-read/'),
    unreadCount: () => client.get('/notifications/unread-count/'),
  },
  devProfile: {
    get: () => client.get('/users/me/dev-profile/'),
    save: (data: Record<string, unknown>) => client.post('/users/me/dev-profile/', data),
    calibration: (jobId?: number) =>
      client.get('/users/me/dev-calibration/', {
        params: jobId != null ? { job: jobId } : {},
      }),
  },
  gitConnections: {
    list: () => client.get('/users/me/git-connections/'),
    create: (data: { provider: string; username: string; email?: string | null }) =>
      client.post('/users/me/git-connections/', data),
    update: (id: number, data: Partial<{ username: string; email: string | null }>) =>
      client.patch(`/users/me/git-connections/${id}/`, data),
    delete: (id: number) => client.delete(`/users/me/git-connections/${id}/`),
  },
  llmConfig: {
    get: () => client.get('/users/me/llm-config/'),
    save: (data: Record<string, unknown>) => client.post('/users/me/llm-config/', data),
    googleOAuthStart: (data: { model: string }) =>
      client.post<{ authorization_url: string; error?: string }>(
        '/users/me/llm-config/oauth/google/start/',
        data,
      ),
    test: (data: {
      provider: string;
      api_key?: string;
      access_token?: string;
      model?: string;
    }) =>
      client.post<{ success: boolean; message?: string; error?: string; reply_preview?: string }>(
        '/users/me/llm-config/test/',
        data,
      ),
    delete: (provider: string) => client.delete(`/users/me/llm-config/${provider}/`),
  },
  webhooks: {
    info: (projectId: number) => client.get(`/projects/${projectId}/webhook/`),
    test: (projectId: number) => client.post(`/projects/${projectId}/webhook/test/`),
  },
  batch: {
    repoBranches: (params: { repo_url: string; author?: string }) =>
      client.get<{ branches: string[] }>('/batch/repo-branches/', {
        params: { repo_url: params.repo_url, ...(params.author ? { author: params.author } : {}) },
      }),
    checkOrgLlm: () =>
      client.get<{ ready: boolean; detail: string }>('/batch/jobs/check-org-llm/'),
    listJobs: () => client.get('/batch/jobs/'),
    getJob: (id: number) => client.get(`/batch/jobs/${id}/`),
    createJob: (data: {
      repo_url: string;
      project: number;
      branch?: string;
      target_github_username?: string;
      max_commits?: number;
      since_date?: string;
    }) => client.post('/batch/jobs/', data),
    cancelJob: (id: number) => client.delete(`/batch/jobs/${id}/`),
    rerunJob: (id: number) => client.post(`/batch/jobs/${id}/rerun/`, {}),
    getJobResults: (id: number) => client.get(`/batch/jobs/${id}/results/`),
    getJobEvaluations: (id: number) => client.get(`/batch/jobs/${id}/evaluations/`),
    getProfile: () => client.get('/batch/profile/'),
    getStats: () => client.get('/batch/stats/'),
  },
};

export function useApi() {
  return {
    ...api,
    // Project member management
    getProjectMembers: async (projectId: number) => {
      const response = await client.get(`/projects/${projectId}/members/`);
      return response.data;
    },
    inviteProjectMember: async (projectId: number, email: string, role: string) => {
      const response = await client.post(`/projects/${projectId}/members/`, { email, role });
      return response.data;
    },
    updateProjectMemberRole: async (projectId: number, userId: number, role: string) => {
      const response = await client.patch(`/projects/${projectId}/members/${userId}/`, { role });
      return response.data;
    },
    removeProjectMember: async (projectId: number, userId: number) => {
      await client.delete(`/projects/${projectId}/members/${userId}/`);
    },
  };
}
