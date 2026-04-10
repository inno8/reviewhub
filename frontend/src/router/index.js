import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import FindingDetailView from '@/views/FindingDetailView.vue';
import FileReviewView from '@/views/FileReviewView.vue';
import PerformanceView from '@/views/PerformanceView.vue';
import UserManagementView from '@/views/UserManagementView.vue';
import SettingsView from '@/views/SettingsView.vue';
import OnboardView from '@/views/OnboardView.vue';
import SkillsDashboardView from '@/views/SkillsDashboardView.vue';
import NotificationsView from '@/views/NotificationsView.vue';
import BatchAnalysisView from '@/views/BatchAnalysisView.vue';
import ProjectsView from '@/views/ProjectsView.vue';
import DevProfileSetupView from '@/views/DevProfileSetupView.vue';
import DevProfileResultsView from '@/views/DevProfileResultsView.vue';
import CommitTimelineView from '@/views/CommitTimelineView.vue';
import RecommendationsView from '@/views/RecommendationsView.vue';
import ResolvedFindingsView from '@/views/ResolvedFindingsView.vue';
import { useAuthStore } from '@/stores/auth';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
        { path: '/onboard', name: 'onboard', component: OnboardView, meta: { public: true } },
        { path: '/dev-profile-setup', name: 'dev-profile-setup', component: DevProfileSetupView, meta: { skipProfileCheck: true } },
        { path: '/dev-profile/results', name: 'dev-profile-results', component: DevProfileResultsView, meta: { skipProfileCheck: true } },
        { path: '/', name: 'dashboard', component: DashboardView },
        { path: '/projects', name: 'projects', component: ProjectsView },
        { path: '/findings/:id', name: 'finding-detail', component: FindingDetailView, props: true },
        { path: '/file-review', name: 'file-review', component: FileReviewView },
        { path: '/skills', name: 'skills', component: SkillsDashboardView },
        { path: '/insights', name: 'insights', component: PerformanceView },
        { path: '/notifications', name: 'notifications', component: NotificationsView },
        { path: '/team', name: 'team', component: UserManagementView, meta: { admin: true } },
        { path: '/batch', name: 'batch', component: BatchAnalysisView },
        { path: '/settings', name: 'settings', component: SettingsView },
        { path: '/recommendations', name: 'recommendations', component: RecommendationsView },
        { path: '/timeline', name: 'timeline', component: CommitTimelineView },
        { path: '/resolved', name: 'resolved', component: ResolvedFindingsView },
    ],
});
router.beforeEach(async (to) => {
    const auth = useAuthStore();
    if (!auth.initialized) {
        await auth.bootstrap();
    }
    if (to.meta.public) {
        return true;
    }
    if (!auth.isAuthenticated) {
        return { name: 'login' };
    }
    if (to.meta.admin && auth.user?.role !== 'ADMIN') {
        return { name: 'dashboard' };
    }
    // Redirect developer (non-admin) to profile setup if not yet completed
    if (!to.meta.skipProfileCheck &&
        auth.user &&
        !auth.user.devProfileCompleted &&
        auth.user.role !== 'ADMIN') {
        return { name: 'dev-profile-setup' };
    }
    return true;
});
export default router;
