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
  projectId: number;
  periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY';
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

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('reviewhub_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export const api = {
  auth: {
    // Django JWT uses email field for authentication
    login: (email: string, password: string) => client.post('/auth/token/', { email, password }),
    register: (data: CreateUser) => client.post('/users/register/', data),
    me: () => client.get('/users/me/'),
    logout: () => {
      localStorage.removeItem('reviewhub_token');
      return Promise.resolve({ data: { message: 'Logged out' } });
    },
  },
  projects: {
    list: () => client.get('/projects/'),
    get: (id: number) => client.get(`/projects/${id}/`),
    getBranches: (id: number) => client.get(`/projects/${id}/branches/`),
    createFromUrl: (url: string) => client.post('/projects/', { url }),
  },
  evaluations: {
    list: (params: ReviewFilters = {}) => client.get('/evaluations/', { params }),
    get: (id: number) => client.get(`/evaluations/${id}/`),
    dashboard: (projectId?: number) => client.get('/evaluations/dashboard/', { params: { project: projectId } }),
    // Legacy reviews API (for backward compatibility during migration)
    calendar: (projectId: number, month: string) => {
      console.warn('Calendar API not yet implemented in Django backend');
      return Promise.resolve({ data: { dates: [] as string[] } });
    },
    trigger: (projectId: number, branches?: string[]) => {
      console.warn('Manual trigger not needed - use webhook flow');
      return Promise.resolve({ data: { message: 'Use webhooks instead' } });
    },
  },
  // Keep reviews as alias during migration
  reviews: {
    list: (params: ReviewFilters = {}) => client.get('/evaluations/', { params }),
    calendar: (projectId: number, month: string) => Promise.resolve({ data: { dates: [] as string[] } }),
    trigger: (projectId: number, branches?: string[]) => Promise.resolve({ data: { message: 'Use webhooks instead', totalFindings: 0 } }),
    importMarkdown: (projectId: number, date: string) => Promise.resolve({ data: { message: 'Not implemented' } }),
    syncMarkdown: (projectId: number) => Promise.resolve({ data: { message: 'Not implemented' } }),
  },
  findings: {
    list: (params: FindingFilters = {}) => client.get('/evaluations/findings/', { params }),
    get: (id: number) => client.get(`/evaluations/findings/${id}/`),
    markFixed: (id: number, commitSha?: string) => client.post(`/evaluations/findings/${id}/fix/`, { commit_sha: commitSha }),
    // Not yet implemented in Django
    getFileContent: (id: number) => {
      console.warn('File content API not yet implemented');
      return Promise.resolve({ data: { content: '' } });
    },
    markUnderstood: (id: number) => Promise.resolve({ data: { markedUnderstood: true } }),
    requestExplanation: (id: number) => Promise.resolve({ data: { message: 'Not implemented' } }),
    applyFix: (id: number) => Promise.resolve({ data: { prUrl: '', message: 'Not implemented' } }),
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
  },
  performance: {
    get: (userId: number, params: PerformanceParams) => client.get(`/performance/${userId}`, { params }),
    trends: (userId: number, params: { projectId: number; weeks?: number }) =>
      client.get(`/performance/${userId}/trends`, { params }),
    recommendations: (userId: number, params: { projectId: number }) =>
      client.get(`/performance/${userId}/recommendations`, { params }),
    leaderboard: (params: { projectId: number; periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY' }) =>
      client.get('/performance/leaderboard', { params }),
  },
  skills: {
    categories: () => client.get('/skills/categories/'),
    user: (userId: number) => client.get(`/skills/user/${userId}/`),
    breakdown: (userId: number, skillId: number, projectId: number) =>
      client.get(`/skills/user/${userId}/breakdown/${skillId}/`, { params: { projectId } }),
    recalculate: (userId: number, projectId: number) =>
      client.post(`/skills/recalculate/${userId}/`, null, { params: { projectId } }),
  },
  dashboard: {
    overview: (projectId?: number) => client.get('/skills/dashboard/overview/', { params: { project: projectId } }),
    skills: (projectId?: number) => client.get('/skills/dashboard/skills/', { params: { project: projectId } }),
    progress: (projectId?: number, weeks?: number) => client.get('/skills/dashboard/progress/', { params: { project: projectId, weeks } }),
    recent: (projectId?: number, limit?: number) => client.get('/skills/dashboard/recent/', { params: { project: projectId, limit } }),
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
