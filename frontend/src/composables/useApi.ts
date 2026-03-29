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
    // Express JWT authentication
    login: (email: string, password: string) => client.post('/auth/login', { email, password }),
    register: (data: CreateUser) => client.post('/auth/register', data),
    me: () => client.get('/auth/me'),
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
    // Performance endpoints not yet implemented in Django v2 - return mock data
    get: (userId: number, params: PerformanceParams) => 
      Promise.resolve({ data: { 
        totalReviews: 0, 
        averageScore: 0, 
        criticalIssues: 0, 
        recommendations: [],
        commitCount: 0,
        findingCount: 0,
        fixRate: 0,
        reviewVelocity: null,
        strengths: [],
        growthAreas: []
      } }),
    trends: (userId: number, params: { projectId: number; weeks?: number }) =>
      Promise.resolve({ data: [] }),
    recommendations: (userId: number, params: { projectId: number }) =>
      Promise.resolve({ data: [] }),
    leaderboard: (params: { projectId: number; periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY' }) =>
      Promise.resolve({ data: [] }),
  },
  skills: {
    categories: () => client.get('/skills/categories/'),
    user: (userId: number) => client.get(`/skills/user/${userId}/`),
    // Breakdown not implemented yet - return empty placeholder data
    breakdown: (userId: number, skillId: number, projectId: number) =>
      Promise.resolve({ data: { 
        skill: { 
          id: skillId, 
          name: 'Skill', 
          displayName: 'Skill', 
          description: 'Skill details not available yet.',
          category: { id: 1, name: 'General', displayName: 'General', icon: 'school' }
        }, 
        score: 0,
        level: 0,
        baseScore: 100,
        deductions: [],
        tips: ['Complete more code reviews to build your skill profile.'],
        findings: [], 
        trend: [] 
      } }),
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
