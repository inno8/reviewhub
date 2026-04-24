import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import FindingDetailView from '@/views/FindingDetailView.vue';
import FileReviewView from '@/views/FileReviewView.vue';
import PerformanceView from '@/views/PerformanceView.vue';
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
import OrgStudentDetailView from '@/views/OrgStudentDetailView.vue';
import DeveloperJourneyView from '@/views/DeveloperJourneyView.vue';
import GradingInboxView from '@/views/GradingInboxView.vue';
import GradingSessionDetailView from '@/views/GradingSessionDetailView.vue';
import StudentPRListView from '@/views/StudentPRListView.vue';
import OpsDashboardView from '@/views/OpsDashboardView.vue';
import OrgMembersView from '@/views/OrgMembersView.vue';
import CohortListView from '@/views/CohortListView.vue';
import CohortDetailView from '@/views/CohortDetailView.vue';
import CourseDetailView from '@/views/CourseDetailView.vue';
import TeacherStudentProfileView from '@/views/TeacherStudentProfileView.vue';
import StudentHomeView from '@/views/StudentHomeView.vue';
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
        // Unified org members page (Workstream B Part 2 of Scope B1).
        // /team and /org-dashboard redirect here to preserve bookmarks.
        { path: '/org/members', name: 'org-members', component: OrgMembersView, meta: { admin: true } },
        { path: '/team', redirect: '/org/members' },
        { path: '/batch', name: 'batch', component: BatchAnalysisView },
        { path: '/settings', name: 'settings', component: SettingsView },
        { path: '/recommendations', name: 'recommendations', component: RecommendationsView },
        { path: '/timeline', name: 'timeline', component: CommitTimelineView },
        { path: '/resolved', name: 'resolved', component: ResolvedFindingsView },
        { path: '/journey', name: 'journey', component: DeveloperJourneyView },
        { path: '/org-signup', name: 'org-signup', component: OrgSignupView, meta: { public: true } },
        { path: '/accept-invite', name: 'accept-invite', component: AcceptInviteView, meta: { public: true } },
        // /org-dashboard redirects to the unified view; the old OrgDashboardView
        // component file stays on disk and will be cleaned up in a later pass.
        { path: '/org-dashboard', redirect: '/org/members' },
        { path: '/org-dashboard/students/:studentId', name: 'org-student-detail', component: OrgStudentDetailView, meta: { admin: true }, props: true },
        // Nakijken Copilot — teacher grading copilot
        { path: '/grading', name: 'grading-inbox', component: GradingInboxView },
        { path: '/grading/sessions/:id', name: 'grading-session-detail', component: GradingSessionDetailView, props: true },
        // Piece 2 — per-student PR list, intermediate view between inbox and session detail
        { path: '/grading/students/:id/prs', name: 'grading-student-prs', component: StudentPRListView, meta: { admin: true }, props: true },
        // Workstream E3 — teacher-facing full student profile
        { path: '/grading/students/:id', name: 'grading-student-profile', component: TeacherStudentProfileView, meta: { admin: true }, props: true },
        // Workstream E1 — cohort + course management.
        // Teachers can view their own cohorts; the backend queryset scopes results.
        { path: '/org/cohorts', name: 'org-cohorts', component: CohortListView, meta: { admin: true } },
        { path: '/org/cohorts/:id', name: 'cohort-detail', component: CohortDetailView, meta: { admin: true }, props: true },
        // Workstream E5 — cohort overview ("klas-overzicht") for teachers.
        { path: '/grading/cohorts/:id/overview', name: 'grading-cohort-overview', component: () => import('@/views/CohortOverviewView.vue'), meta: { admin: true }, props: true },
        // Klas-overzicht entry — picks the right cohort overview (redirects
        // when the teacher has exactly one cohort).
        { path: '/grading/klas-overzicht', name: 'grading-klas-overzicht', component: () => import('@/views/CohortOverviewPickerView.vue'), meta: { admin: true } },
        // Teacher's student roster — all students across all their cohorts.
        { path: '/grading/students', name: 'grading-students', component: () => import('@/views/TeacherStudentListView.vue'), meta: { admin: true } },
        { path: '/org/courses/:id', name: 'course-detail', component: CourseDetailView, meta: { admin: true }, props: true },
        // Workstream E4 — student "My cohort" page (mount point for MyCohortWidget)
        { path: '/my-cohort', name: 'my-cohort', component: StudentHomeView },
        // Platform ops — superuser only
        { path: '/ops', name: 'ops-dashboard', component: OpsDashboardView, meta: { ops: true } },
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
