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
    login: (email: string, password: string) => client.post('/auth/login', { email, password }),
    me: () => client.get('/auth/me'),
    logout: () => client.post('/auth/logout'),
  },
  projects: {
    list: () => client.get('/projects'),
    get: (id: number) => client.get(`/projects/${id}`),
    getBranches: (id: number) => client.get(`/projects/${id}/branches`),
    createFromUrl: (url: string) => client.post('/projects/from-url', { url }),
  },
  reviews: {
    list: (params: ReviewFilters = {}) => client.get('/reviews', { params }),
    calendar: (projectId: number, month: string) =>
      client.get('/reviews/calendar', { params: { projectId, month } }),
    trigger: (projectId: number, branches?: string[]) =>
      client.post('/reviews/trigger', { projectId, branches }),
    importMarkdown: (projectId: number, date: string) =>
      client.post(`/reviews/import/${date}`, { projectId }),
    syncMarkdown: (projectId: number) =>
      client.post('/reviews/sync-markdown', { projectId }),
  },
  findings: {
    list: (params: FindingFilters = {}) => client.get('/findings', { params }),
    get: (id: number) => client.get(`/findings/${id}`),
    getFileContent: (id: number) => client.get(`/findings/${id}/file-content`),
    markUnderstood: (id: number) => client.patch(`/findings/${id}/understood`),
    requestExplanation: (id: number) => client.post(`/findings/${id}/request-explanation`),
    applyFix: (id: number) => client.post(`/findings/${id}/apply-fix`),
  },
  files: {
    getContent: (projectId: number, branch: string, filePath: string) =>
      client.get(`/files/${projectId}/${encodeURIComponent(branch)}/${encodeURIComponent(filePath)}`),
  },
  users: {
    list: () => client.get('/users'),
    me: () => client.get('/users/me'),
    updateMe: (data: Omit<UpdateUser, 'role' | 'projectIds'>) => client.patch('/users/me', data),
    create: (data: CreateUser) => client.post('/users', data),
    update: (id: number, data: UpdateUser) => client.patch(`/users/${id}`, data),
    delete: (id: number) => client.delete(`/users/${id}`),
    getProjects: (id: number) => client.get(`/users/${id}/projects`),
    assignProjects: (id: number, projectIds: number[]) => client.post(`/users/${id}/projects`, { projectIds }),
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
    categories: () => client.get('/skills/categories'),
    user: (userId: number) => client.get(`/skills/user/${userId}`),
    breakdown: (userId: number, skillId: number, projectId: number) =>
      client.get(`/skills/user/${userId}/breakdown/${skillId}`, { params: { projectId } }),
    recalculate: (userId: number, projectId: number) =>
      client.post(`/skills/recalculate/${userId}`, null, { params: { projectId } }),
  },
};

export function useApi() {
  return client;
}
