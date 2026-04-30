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
    baseURL: import.meta.env.VITE_API_URL || '/api',
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

/**
 * Singleton refresh promise — when multiple requests fire in parallel and all
 * get 401, we want exactly ONE refresh call. Other requests await this same
 * promise instead of racing N refreshes which would invalidate each other on
 * the Django side (refresh tokens rotate on use when ROTATE_REFRESH_TOKENS
 * is on; even if it isn't, parallel refreshes cause unnecessary load).
 */
let refreshInFlight = null;

function refreshAccessToken() {
    if (refreshInFlight) return refreshInFlight;
    const refresh = localStorage.getItem('reviewhub_refresh_token');
    if (!refresh) return Promise.reject(new Error('no refresh token'));
    // Use a bare axios call so we don't recurse through the interceptor.
    refreshInFlight = axios
        .post(`${client.defaults.baseURL}/auth/token/refresh/`, { refresh })
        .then((response) => {
            const newAccess = response.data?.access;
            if (!newAccess) throw new Error('refresh response missing access token');
            localStorage.setItem('reviewhub_token', newAccess);
            // Django Simple JWT may also rotate the refresh token (when
            // ROTATE_REFRESH_TOKENS=True). If a new refresh comes back, save it.
            if (response.data.refresh) {
                localStorage.setItem('reviewhub_refresh_token', response.data.refresh);
            }
            return newAccess;
        })
        .finally(() => {
            refreshInFlight = null;
        });
    return refreshInFlight;
}

client.interceptors.response.use((response) => response, async (error) => {
    const originalRequest = error?.config;
    const status = error?.response?.status;

    // 401 path: try to refresh and retry once. Each request is retried at
    // most once (_retry flag) so we don't infinite-loop on a permanently
    // bad token. Skip refresh attempts on public pages and on the refresh
    // endpoint itself (otherwise a failed refresh would recurse forever).
    if (
        status === 401 &&
        originalRequest &&
        !originalRequest._retry &&
        !originalRequest.url?.includes('/auth/token/refresh') &&
        !originalRequest.url?.includes('/auth/token/') // login itself
    ) {
        const publicPaths = ['/login', '/onboard', '/org-signup', '/accept-invite'];
        const isPublicPage = publicPaths.some(p => window.location.pathname.startsWith(p));

        if (!isPublicPage && !skipAuthRedirect) {
            originalRequest._retry = true;
            try {
                const newAccess = await refreshAccessToken();
                originalRequest.headers = originalRequest.headers || {};
                originalRequest.headers.Authorization = `Bearer ${newAccess}`;
                return client(originalRequest);
            } catch (refreshErr) {
                // Refresh failed — refresh token is gone, expired, or invalid.
                // Now we genuinely log the user out.
                localStorage.removeItem('reviewhub_token');
                localStorage.removeItem('reviewhub_refresh_token');
                window.location.href = '/login';
                return Promise.reject(refreshErr);
            }
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
        // SimpleJWT refresh — exposed for cases where code wants to force a
        // refresh outside the 401 retry path (e.g. proactive refresh timer).
        // The interceptor handles the common case; you usually don't need to
        // call this directly.
        refresh: (refreshToken) => client.post('/auth/token/refresh/', { refresh: refreshToken }),
        register: (data) => client.post('/users/register/', data),
        me: () => client.get('/users/me/'),
        logout: () => {
            localStorage.removeItem('reviewhub_token');
            localStorage.removeItem('reviewhub_refresh_token');
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
        chart: (params = {}) => client.get('/evaluations/chart/', { params: djangoListParams(params) }),
        patterns: (params = {}) => client.get('/evaluations/patterns/', { params: { ...(params.projectId ? { project: params.projectId } : {}), ...(params.userId ? { user: params.userId } : {}), ...(params.resolved !== undefined ? { resolved: params.resolved } : {}) } }),
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
        resolved: (params = {}) => client.get('/evaluations/findings/resolved/', { params: djangoListParams(params) }),
        requestExplanation: (_id) => Promise.resolve({ data: { message: 'Not implemented' } }),
        applyFix: (_id) => Promise.resolve({ data: { prUrl: '', message: 'Not implemented' } }),
    },
    files: {
        getContent: (projectId, branch, filePath) => client.get(`/files/${projectId}/${encodeURIComponent(branch)}/${encodeURIComponent(filePath)}`),
    },
    users: {
        list: (params = {}) => client.get('/users/', { params }),
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
                ...(params?.days != null ? { days: params.days } : {}),
                ...(params?.granularity ? { granularity: params.granularity } : {}),
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
        journey: (userId, projectId) => client.get(`/skills/journey/${userId}/`, {
            params: projectId != null ? { project: projectId } : {},
        }),
    },
    dashboard: {
        overview: (projectId, userId) => client.get('/skills/dashboard/overview/', { params: { project: projectId, user: userId } }),
        skills: (projectId, userId) => client.get('/skills/dashboard/skills/', { params: { project: projectId, user: userId } }),
        progress: (projectId, weeks, userId) => client.get('/skills/dashboard/progress/', { params: { project: projectId, weeks, user: userId } }),
        recent: (projectId, limit, userId) => client.get('/skills/dashboard/recent/', { params: { project: projectId, limit, user: userId } }),
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
        calibration: (jobId, userId) => client.get('/users/me/dev-calibration/', {
            params: { ...(jobId != null ? { job: jobId } : {}), ...(userId != null ? { user: userId } : {}) },
        }),
    },
    gitConnections: {
        list: () => client.get('/users/me/git-connections/'),
        create: (data) => client.post('/users/me/git-connections/', data),
        update: (id, data) => client.patch(`/users/me/git-connections/${id}/`, data),
        delete: (id) => client.delete(`/users/me/git-connections/${id}/`),
    },
    github: {
        // Returns the install URL the frontend should redirect to.
        // 503 if the App isn't configured server-side.
        installUrl: () => client.get('/github/install-url/'),
        // Lists current user's GitHub App installations + repos.
        installations: () => client.get('/github/installations/'),
        // Called by /dev-profile/connected after GitHub redirects back
        // with installation_id in the query string. Upserts the
        // GitHubInstallation + StudentRepo rows.
        syncInstallation: (installationId) =>
            client.post('/github/installations/sync/', { installation_id: installationId }),
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
        register: (projectId) => client.post(`/projects/${projectId}/webhook/register/`),
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
    org: {
        signup: (data) => client.post('/users/org-signup/', data),
        acceptInvite: (data) => client.post('/users/accept-invite/', data),
        invite: (data) => client.post('/users/invite/', data),
        resendInvitation: (id) => client.post(`/users/org/invitations/${id}/resend/`),
        cancelInvitation: (id) => client.delete(`/users/org/invitations/${id}/`),
        removeMember: (userId) => client.delete(`/users/org/members/${userId}/`),
        members: () => client.get('/users/org/members/'),
        invitations: () => client.get('/users/org/invitations/'),
        subscription: () => client.get('/users/org/subscription/'),
        dashboard: () => client.get('/skills/org-dashboard/'),
        studentDetail: (studentId) => client.get(`/skills/org-dashboard/students/${studentId}/`),
    },
    // Nakijken Copilot — teacher grading copilot
    grading: {
        rubrics: {
            list: () => client.get('/grading/rubrics/'),
            get: (id) => client.get(`/grading/rubrics/${id}/`),
            create: (data) => client.post('/grading/rubrics/', data),
            update: (id, data) => client.patch(`/grading/rubrics/${id}/`, data),
            delete: (id) => client.delete(`/grading/rubrics/${id}/`),
        },
        cohorts: {
            list: (params = {}) => client.get('/grading/cohorts/', { params }),
            get: (id) => client.get(`/grading/cohorts/${id}/`),
            create: (data) => client.post('/grading/cohorts/', data),
            update: (id, data) => client.patch(`/grading/cohorts/${id}/`, data),
            archive: (id) => client.post(`/grading/cohorts/${id}/archive/`, {}),
            members: (id) => client.get(`/grading/cohorts/${id}/members/`),
            // repoUrl param kept optional for any caller still passing it,
            // but the GitHub App migration moved repo binding to the
            // student's own onboarding flow. Default to empty string so
            // the backend stores NULL.
            addMember: (id, studentId, repoUrl = '') => client.post(
                `/grading/cohorts/${id}/members/`,
                { student_id: studentId, student_repo_url: repoUrl || '' }
            ),
            removeMember: (id, membershipId) => client.delete(
                `/grading/cohorts/${id}/members/${membershipId}/`,
            ),
            teachers: (id) => client.get(`/grading/cohorts/${id}/teachers/`),
            addTeacher: (id, teacherId) => client.post(
                `/grading/cohorts/${id}/teachers/`,
                { teacher_id: teacherId }
            ),
            removeTeacher: (id, assignmentId) => client.delete(
                `/grading/cohorts/${id}/teachers/${assignmentId}/`,
            ),
            recurringErrors: (id) => client.get(`/grading/cohorts/${id}/recurring-errors/`),
            overview: (id) => client.get(`/grading/cohorts/${id}/overview/`),
        },
        courses: {
            list: (params = {}) => client.get('/grading/courses/', { params }),
            get: (id) => client.get(`/grading/courses/${id}/`),
            create: (data) => client.post('/grading/courses/', data),
            update: (id, data) => client.patch(`/grading/courses/${id}/`, data),
            delete: (id) => client.delete(`/grading/courses/${id}/`),
            archive: (id) => client.post(`/grading/courses/${id}/archive/`, {}),
            reassign: (id, newOwnerId) => client.post(`/grading/courses/${id}/reassign/`, { new_owner_id: newOwnerId }),
            members: (id) => client.get(`/grading/courses/${id}/members/`),
            addMember: (id, studentId, repoUrl) => client.post(
                `/grading/courses/${id}/members/`,
                { student_id: studentId, student_repo_url: repoUrl || '' }
            ),
            removeMember: (id, studentId) => client.delete(
                `/grading/courses/${id}/members/`,
                { params: { student_id: studentId } }
            ),
        },
        // Project = assignment within a Course (Apr 28 2026 — assignment layer).
        // CRUD: only the course owner (teacher) can create/update/archive
        // projects under their own courses. Admin override allowed.
        projects: {
            list: (params = {}) => client.get('/grading/projects/', { params }),
            byCourse: (courseId) => client.get('/grading/projects/', {
                params: { course: courseId },
            }),
            get: (id) => client.get(`/grading/projects/${id}/`),
            create: (data) => client.post('/grading/projects/', data),
            update: (id, data) => client.patch(`/grading/projects/${id}/`, data),
            archive: (id) => client.delete(`/grading/projects/${id}/`),
        },
        // StudentProjectRepo = a student's repo URL for one specific Project.
        // Self-service: students write their OWN row only.
        studentProjectRepos: {
            list: (params = {}) => client.get('/grading/student-project-repos/', { params }),
            byProject: (projectId) => client.get('/grading/student-project-repos/', {
                params: { project: projectId },
            }),
            create: (data) => client.post('/grading/student-project-repos/', data),
            update: (id, data) => client.patch(`/grading/student-project-repos/${id}/`, data),
            delete: (id) => client.delete(`/grading/student-project-repos/${id}/`),
        },
        students: {
            list: (params = {}) => client.get('/grading/students/', { params }),
            snapshot: (studentId) => client.get(`/grading/students/${studentId}/snapshot/`),
            trajectory: (studentId, weeks, opts = {}) => {
                const params = {};
                if (weeks) params.weeks = weeks;
                if (opts.granularity) params.granularity = opts.granularity;
                if (opts.includeCohortMean) params.include_cohort_mean = 'true';
                return client.get(`/grading/students/${studentId}/trajectory/`, { params });
            },
            prHistory: (studentId, limit) => client.get(`/grading/students/${studentId}/pr-history/`, { params: limit ? { limit } : {} }),
        },
        submissions: {
            list: (params = {}) => client.get('/grading/submissions/', { params }),
            get: (id) => client.get(`/grading/submissions/${id}/`),
        },
        sessions: {
            list: (params = {}) => client.get('/grading/sessions/', { params }),
            get: (id) => client.get(`/grading/sessions/${id}/`),
            update: (id, data) => client.patch(`/grading/sessions/${id}/`, data),
            startReview: (id) => client.post(`/grading/sessions/${id}/start_review/`, {}),
            generateDraft: (id) => client.post(`/grading/sessions/${id}/generate_draft/`, {}),
            send: (id) => client.post(`/grading/sessions/${id}/send/`, {}),
            resume: (id) => client.post(`/grading/sessions/${id}/resume/`, {}),
            startNewIteration: (id) => client.post(`/grading/sessions/${id}/start_new_iteration/`, {}),
            // Teacher dashboard front-door aggregate. Returns one
            // round-trip of: kpi (state counts), next_up (oldest drafted),
            // review_time (p50/p95 over last 30d), recurring_patterns.
            inboxSummary: () => client.get('/grading/sessions/inbox-summary/'),
        },
        costLogs: {
            list: (params = {}) => client.get('/grading/cost-logs/', { params }),
        },
        // Ops dashboard — superuser only
        ops: {
            summary: () => client.get('/grading/ops/summary/'),
            orgs: () => client.get('/grading/ops/orgs/'),
            courses: (params = {}) => client.get('/grading/ops/courses/', { params }),
            teachers: () => client.get('/grading/ops/teachers/'),
            llmLog: (params = {}) => client.get('/grading/ops/llm-log/', { params }),
            metrics: {
                weekly: (params = {}) => client.get('/grading/ops/metrics/weekly/', { params }),
            },
        },
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
