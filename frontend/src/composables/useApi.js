import axios from 'axios';
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
client.interceptors.response.use((response) => response, (error) => {
    if (error?.response?.status === 401) {
        localStorage.removeItem('reviewhub_token');
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    }
    return Promise.reject(error);
});
export const api = {
    auth: {
        login: (email, password) => client.post('/auth/login', { email, password }),
        me: () => client.get('/auth/me'),
        logout: () => client.post('/auth/logout'),
    },
    projects: {
        list: () => client.get('/projects'),
        get: (id) => client.get(`/projects/${id}`),
        getBranches: (id) => client.get(`/projects/${id}/branches`),
        createFromUrl: (url) => client.post('/projects/from-url', { url }),
    },
    reviews: {
        list: (params = {}) => client.get('/reviews', { params }),
        calendar: (projectId, month) => client.get('/reviews/calendar', { params: { projectId, month } }),
        trigger: (projectId, branches) => client.post('/reviews/trigger', { projectId, branches }),
        importMarkdown: (projectId, date) => client.post(`/reviews/import/${date}`, { projectId }),
        syncMarkdown: (projectId) => client.post('/reviews/sync-markdown', { projectId }),
    },
    findings: {
        list: (params = {}) => client.get('/findings', { params }),
        get: (id) => client.get(`/findings/${id}`),
        getFileContent: (id) => client.get(`/findings/${id}/file-content`),
        markUnderstood: (id) => client.patch(`/findings/${id}/understood`),
        requestExplanation: (id) => client.post(`/findings/${id}/request-explanation`),
        applyFix: (id) => client.post(`/findings/${id}/apply-fix`),
    },
    files: {
        getContent: (projectId, branch, filePath) => client.get(`/files/${projectId}/${encodeURIComponent(branch)}/${encodeURIComponent(filePath)}`),
    },
    users: {
        list: () => client.get('/users'),
        me: () => client.get('/users/me'),
        updateMe: (data) => client.patch('/users/me', data),
        create: (data) => client.post('/users', data),
        update: (id, data) => client.patch(`/users/${id}`, data),
        delete: (id) => client.delete(`/users/${id}`),
        getProjects: (id) => client.get(`/users/${id}/projects`),
        assignProjects: (id, projectIds) => client.post(`/users/${id}/projects`, { projectIds }),
    },
    performance: {
        get: (userId, params) => client.get(`/performance/${userId}`, { params }),
        trends: (userId, params) => client.get(`/performance/${userId}/trends`, { params }),
        recommendations: (userId, params) => client.get(`/performance/${userId}/recommendations`, { params }),
        leaderboard: (params) => client.get('/performance/leaderboard', { params }),
    },
};
export function useApi() {
    return client;
}
