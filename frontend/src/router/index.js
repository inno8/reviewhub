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
import OrgSignupView from '@/views/OrgSignupView.vue';
import AcceptInviteView from '@/views/AcceptInviteView.vue';
import OrgDashboardView from '@/views/OrgDashboardView.vue';
import OrgStudentDetailView from '@/views/OrgStudentDetailView.vue';
import DeveloperJourneyView from '@/views/DeveloperJourneyView.vue';
import GradingInboxView from '@/views/GradingInboxView.vue';
import GradingSessionDetailView from '@/views/GradingSessionDetailView.vue';
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
        { path: '/journey', name: 'journey', component: DeveloperJourneyView },
        { path: '/org-signup', name: 'org-signup', component: OrgSignupView, meta: { public: true } },
        { path: '/accept-invite', name: 'accept-invite', component: AcceptInviteView, meta: { public: true } },
        { path: '/org-dashboard', name: 'org-dashboard', component: OrgDashboardView, meta: { admin: true } },
        { path: '/org-dashboard/students/:studentId', name: 'org-student-detail', component: OrgStudentDetailView, meta: { admin: true }, props: true },
        // Nakijken Copilot — teacher grading copilot
        { path: '/grading', name: 'grading-inbox', component: GradingInboxView },
        { path: '/grading/sessions/:id', name: 'grading-session-detail', component: GradingSessionDetailView, props: true },
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
    // Admin-gated routes: allow admin, teacher, and platform ops (superuser).
    // Role is lowercase per auth store normalization.
    if (to.meta.admin && !['admin', 'teacher'].includes(auth.user?.role) && !auth.user?.isSuperuser) {
        return { name: 'dashboard' };
    }
    // Ops-gated routes: platform superuser only.
    if (to.meta.ops && !auth.user?.isSuperuser) {
        return { name: 'dashboard' };
    }
    // Redirect students (not teachers/admins/ops) to profile setup if incomplete.
    const isStaff = ['admin', 'teacher'].includes(auth.user?.role) || auth.user?.isSuperuser;
    if (!to.meta.skipProfileCheck &&
        auth.user &&
        !auth.user.devProfileCompleted &&
        !isStaff) {
        return { name: 'dev-profile-setup' };
    }
    return true;
});
export default router;
