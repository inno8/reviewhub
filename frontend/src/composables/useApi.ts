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
}

export interface UpdateUser {
  username?: string;
  email?: string;
  role?: 'ADMIN' | 'INTERN';
  telegramChatId?: string | null;
}

export interface PerformanceParams {
  projectId?: number;
  periodType?: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  startDate?: string;
  endDate?: string;
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
  },
  reviews: {
    list: (params: ReviewFilters = {}) => client.get('/reviews', { params }),
    calendar: (projectId: number, month: string) =>
      client.get('/reviews/calendar', { params: { projectId, month } }),
  },
  findings: {
    list: (params: FindingFilters = {}) => client.get('/findings', { params }),
    get: (id: number) => client.get(`/findings/${id}`),
    markUnderstood: (id: number) => client.patch(`/findings/${id}/understood`),
    requestExplanation: (id: number) => client.post(`/findings/${id}/request-explanation`),
  },
  users: {
    list: () => client.get('/users'),
    create: (data: CreateUser) => client.post('/users', data),
    update: (id: number, data: UpdateUser) => client.patch(`/users/${id}`, data),
    delete: (id: number) => client.delete(`/users/${id}`),
  },
  performance: {
    get: (userId: number, params: PerformanceParams) => client.get(`/performance/${userId}`, { params }),
  },
};

export function useApi() {
  return client;
}
