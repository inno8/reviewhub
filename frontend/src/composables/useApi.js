import axios from 'axios';
/** Django expects `project` query param; frontend uses `projectId`. */
function djangoListParams(params) {
    const { projectId, ...rest } = params;
    const out = { ...rest };
    if (projectId !== undefined && projectId !== null) {
        out.project = projectId;
    }
    return out;
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
export function setSkipAuthRedirect(skip) {
    skipAuthRedirect = skip;
}
client.interceptors.response.use((response) => response, (error) => {
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
});
export const api = {
    onboard: {
        checkEmail: (email) => client.post('/onboard/check-email/', { email }),
        verifyCode: (email, code) => client.post('/onboard/verify-code/', { email, code }),
        setPassword: (token, password) => client.post('/onboard/set-password/', { token, password }),
    },
    auth: {
        // Django JWT authentication
        login: (email, password) => client.post('/auth/token/', { email, password }),
        register: (data) => client.post('/users/register/', data),
        me: () => client.get('/users/me/'),
        logout: () => {
            localStorage.removeItem('reviewhub_token');
            return Promise.resolve({ data: { message: 'Logged out' } });
        },
    },
    projects: {
        list: (params) => client.get('/projects/', { params }),
        get: (id) => client.get(`/projects/${id}/`),
        getBranches: (id) => client.get(`/projects/${id}/branches/`),
        createFromUrl: (url) => client.post('/projects/', { url }),
        create: (data) => client.post('/projects/', data),
        update: (id, data) => client.patch(`/projects/${id}/`, data),
        delete: (id) => client.delete(`/projects/${id}/`),
        linkRepo: (id, repoUrl) => client.patch(`/projects/${id}/link-repo/`, { repo_url: repoUrl }),
        unlinkRepo: (id) => client.post(`/projects/${id}/unlink-repo/`, {}),
    },
    evaluations: {
        list: (params = {}) => client.get('/evaluations/', { params: djangoListParams(params) }),
        get: (id) => client.get(`/evaluations/${id}/`),
        dashboard: (projectId) => client.get('/evaluations/dashboard/', { params: { project: projectId } }),
        calendar: (projectId, month) => client.get('/evaluations/calendar/', { params: { project: projectId, month } }),
        trigger: (projectId, branches) => Promise.resolve({ data: { message: 'Use webhooks instead' } }),
        patterns: (projectId) => client.get('/evaluations/patterns/', { params: projectId ? { project: projectId } : {} }),
        resolvePattern: (id, force = false) => client.post(`/evaluations/patterns/${id}/resolve/`, { force }),
    },
    reviews: {
        list: (params = {}) => client.get('/evaluations/', { params: djangoListParams(params) }),
        calendar: (projectId, month) => client.get('/evaluations/calendar/', { params: { project: projectId, month } }),
        trigger: (projectId, branches) => Promise.resolve({ data: { message: 'Use webhooks instead', totalFindings: 0 } }),
        importMarkdown: (projectId, date) => Promise.resolve({ data: { message: 'Not implemented' } }),
        syncMarkdown: (projectId) => Promise.resolve({ data: { message: 'Not implemented' } }),
    },
    findings: {
        list: (params = {}) => client.get('/evaluations/findings/', { params: djangoListParams(params) }),
        get: (id) => client.get(`/evaluations/findings/${id}/`),
        markFixed: (id, commitSha) => client.post(`/evaluations/findings/${id}/fix/`, { commit_sha: commitSha }),
        getFileContent: (id) => client.get(`/evaluations/findings/${id}/file-content/`),
        markUnderstood: (_id) => Promise.resolve({ data: { markedUnderstood: true } }),
        checkUnderstanding: (findings) => client.post('/evaluations/findings/check-understanding/', { findings }),
        requestExplanation: (_id) => Promise.resolve({ data: { message: 'Not implemented' } }),
        applyFix: (_id) => Promise.resolve({ data: { prUrl: '', message: 'Not implemented' } }),
    },
    files: {
        getContent: (projectId, branch, filePath) => client.get(`/files/${projectId}/${encodeURIComponent(branch)}/${encodeURIComponent(filePath)}`),
    },
    users: {
        list: () => client.get('/users/'),
        me: () => client.get('/users/me/'),
        updateMe: (data) => client.patch('/users/me/', data),
        create: (data) => client.post('/users/', data),
        update: (id, data) => client.patch(`/users/${id}/`, data),
        delete: (id) => client.delete(`/users/${id}/`),
        getProjects: (id) => client.get(`/users/${id}/projects/`),
        assignProjects: (id, projectIds) => client.post(`/users/${id}/projects/`, { projectIds }),
        adminStats: (params) => client.get('/users/admin/stats/', { params }),
        /** Encrypted GitHub PAT for private repo branch listing (batch). */
        githubToken: {
            get: () => client.get('/users/me/github-token/'),
            save: (token) => client.post('/users/me/github-token/', { token }),
            delete: () => client.delete('/users/me/github-token/'),
        },
    },
    categories: {
        list: () => client.get('/users/categories/'),
        get: (id) => client.get(`/users/categories/${id}/`),
        create: (data) => client.post('/users/categories/', data),
        update: (id, data) => client.patch(`/users/categories/${id}/`, data),
        delete: (id) => client.delete(`/users/categories/${id}/`),
    },
    performance: {
        get: (userId, params) => client.get(`/skills/performance/${userId}/`, {
            params: params?.projectId != null && params.projectId !== undefined
                ? { project: params.projectId }
                : {},
        }),
        trends: (userId, params) => client.get(`/skills/performance/${userId}/trends/`, {
            params: {
                ...(params?.projectId != null && params.projectId !== undefined
                    ? { project: params.projectId }
                    : {}),
                ...(params?.weeks != null ? { weeks: params.weeks } : {}),
            },
        }),
        recommendations: (userId, params) => Promise.resolve({ data: [] }),
        leaderboard: (params) => Promise.resolve({ data: [] }),
    },
    skills: {
        categories: () => client.get('/skills/categories/'),
        user: (userId, projectId) => client.get(`/skills/user/${userId}/`, {
            params: projectId != null ? { project: projectId } : {},
        }),
        breakdown: (userId, skillId, projectId) => client.get(`/skills/user/${userId}/breakdown/${skillId}/`, { params: { project: projectId } }),
        recalculate: (userId, projectId) => Promise.resolve({ data: { success: true } }),
        recommendations: (projectId) => client.get('/skills/recommendations/', { params: { project: projectId } }),
    },
    dashboard: {
        overview: (projectId) => client.get('/skills/dashboard/overview/', { params: { project: projectId } }),
        skills: (projectId) => client.get('/skills/dashboard/skills/', { params: { project: projectId } }),
        progress: (projectId, weeks) => client.get('/skills/dashboard/progress/', { params: { project: projectId, weeks } }),
        recent: (projectId, limit) => client.get('/skills/dashboard/recent/', { params: { project: projectId, limit } }),
    },
    notifications: {
        list: (limit) => client.get('/notifications/', { params: { limit } }),
        markAsRead: (id) => client.patch(`/notifications/${id}/read/`),
        markAllRead: () => client.post('/notifications/mark-all-read/'),
        unreadCount: () => client.get('/notifications/unread-count/'),
    },
    devProfile: {
        get: () => client.get('/users/me/dev-profile/'),
        save: (data) => client.post('/users/me/dev-profile/', data),
        calibration: (jobId) => client.get('/users/me/dev-calibration/', {
            params: jobId != null ? { job: jobId } : {},
        }),
    },
    gitConnections: {
        list: () => client.get('/users/me/git-connections/'),
        create: (data) => client.post('/users/me/git-connections/', data),
        update: (id, data) => client.patch(`/users/me/git-connections/${id}/`, data),
        delete: (id) => client.delete(`/users/me/git-connections/${id}/`),
    },
    llmConfig: {
        get: () => client.get('/users/me/llm-config/'),
        save: (data) => client.post('/users/me/llm-config/', data),
        googleOAuthStart: (data) => client.post('/users/me/llm-config/oauth/google/start/', data),
        test: (data) => client.post('/users/me/llm-config/test/', data),
        delete: (provider) => client.delete(`/users/me/llm-config/${provider}/`),
    },
    webhooks: {
        info: (projectId) => client.get(`/projects/${projectId}/webhook/`),
        test: (projectId) => client.post(`/projects/${projectId}/webhook/test/`),
    },
    batch: {
        repoBranches: (params) => client.get('/batch/repo-branches/', {
            params: { repo_url: params.repo_url, ...(params.author ? { author: params.author } : {}) },
        }),
        checkOrgLlm: () => client.get('/batch/jobs/check-org-llm/'),
        listJobs: () => client.get('/batch/jobs/'),
        getJob: (id) => client.get(`/batch/jobs/${id}/`),
        createJob: (data) => client.post('/batch/jobs/', data),
        cancelJob: (id) => client.delete(`/batch/jobs/${id}/`),
        rerunJob: (id) => client.post(`/batch/jobs/${id}/rerun/`, {}),
        getJobResults: (id) => client.get(`/batch/jobs/${id}/results/`),
        getJobEvaluations: (id) => client.get(`/batch/jobs/${id}/evaluations/`),
        getProfile: () => client.get('/batch/profile/'),
        getStats: () => client.get('/batch/stats/'),
    },
};
export function useApi() {
    return {
        ...api,
        // Project member management
        getProjectMembers: async (projectId) => {
            const response = await client.get(`/projects/${projectId}/members/`);
            return response.data;
        },
        inviteProjectMember: async (projectId, email, role) => {
            const response = await client.post(`/projects/${projectId}/members/`, { email, role });
            return response.data;
        },
        updateProjectMemberRole: async (projectId, userId, role) => {
            const response = await client.patch(`/projects/${projectId}/members/${userId}/`, { role });
            return response.data;
        },
        removeProjectMember: async (projectId, userId) => {
            await client.delete(`/projects/${projectId}/members/${userId}/`);
        },
    };
}
