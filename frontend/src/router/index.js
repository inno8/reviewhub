import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '@/views/LoginView.vue';
import LandingView from '@/views/LandingView.vue';
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
// Cut from v1 nav (Apr 26 2026) — view files retained on disk for v1.1 restore.
// Re-add the import + the matching route entry below to bring back. Both files
// are still maintained against the current data shape; the cut is a routing /
// nav decision, not a code deletion.
//   import ResolvedFindingsView from '@/views/ResolvedFindingsView.vue';
//   import DeveloperJourneyView from '@/views/DeveloperJourneyView.vue';
import OrgSignupView from '@/views/OrgSignupView.vue';
import PrivacyView from '@/views/PrivacyView.vue';
import VoorwaardenView from '@/views/VoorwaardenView.vue';
import DPAView from '@/views/DPAView.vue';
import AcceptInviteView from '@/views/AcceptInviteView.vue';
import OrgStudentDetailView from '@/views/OrgStudentDetailView.vue';
import GradingInboxView from '@/views/GradingInboxView.vue';
import GradingSessionDetailView from '@/views/GradingSessionDetailView.vue';
import StudentPRListView from '@/views/StudentPRListView.vue';
import OpsDashboardView from '@/views/OpsDashboardView.vue';
import OrgMembersView from '@/views/OrgMembersView.vue';
import CohortListView from '@/views/CohortListView.vue';
import CohortDetailView from '@/views/CohortDetailView.vue';
import CourseDetailView from '@/views/CourseDetailView.vue';
import TeacherStudentProfileView from '@/views/TeacherStudentProfileView.vue';
// StudentHomeView retired Apr 26 2026 — its only mount (`/my-cohort`) now
// redirects into Settings. File kept on disk; uncomment this import + the
// route to bring it back.
//   import StudentHomeView from '@/views/StudentHomeView.vue';
import { useAuthStore } from '@/stores/auth';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
        { path: '/welcome', name: 'welcome', component: LandingView, meta: { public: true } },
        { path: '/landing', name: 'landing', component: LandingView, meta: { public: true } },
        // Public rubric page — explains how LEERA grades for school admins,
        // docenten, students, and parents. No auth required so a school
        // admin can share the link before any account exists.
        {
            path: '/rubric',
            name: 'rubric',
            component: () => import('@/views/RubricPublicView.vue'),
            meta: { public: true },
        },
        { path: '/onboard', name: 'onboard', component: OnboardView, meta: { public: true } },
        { path: '/dev-profile-setup', name: 'dev-profile-setup', component: DevProfileSetupView, meta: { skipProfileCheck: true } },
        { path: '/dev-profile/results', name: 'dev-profile-results', component: DevProfileResultsView, meta: { skipProfileCheck: true } },
        // GitHub App install callback. GitHub redirects the student's
        // browser here after a successful install; the view reads
        // installation_id from ?query and POSTs to /api/github/installations/sync.
        {
            path: '/dev-profile/connected',
            name: 'dev-profile-connected',
            component: () => import('@/views/GitHubConnectedView.vue'),
            meta: { skipProfileCheck: true },
        },
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
        // Cut from v1 nav (Apr 26 2026) — see imports block above for context.
        // Restore by uncommenting both the route AND the matching import:
        //   { path: '/resolved', name: 'resolved', component: ResolvedFindingsView },
        //   { path: '/journey', name: 'journey', component: DeveloperJourneyView },
        { path: '/org-signup', name: 'org-signup', component: OrgSignupView, meta: { public: true } },
        // Public legal pages
        { path: '/privacy', name: 'privacy', component: PrivacyView, meta: { public: true } },
        { path: '/voorwaarden', name: 'voorwaarden', component: VoorwaardenView, meta: { public: true } },
        { path: '/dpa', name: 'dpa', component: DPAView, meta: { public: true } },
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
        // Student-facing self route: same component, no admin gate. The view
        // detects the missing :id route param and substitutes the auth user's
        // own id, so a student lands on their own feedback list without the
        // teacher's explicit student-id URL.
        { path: '/my/prs', name: 'my-prs', component: StudentPRListView, props: true },
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
        // Legacy student "My cohort" path — relocated into Settings as a tab
        // Apr 26 2026. Kept as a redirect so old bookmarks / external links
        // (e.g. teacher-shared URLs) keep working. The StudentHomeView file
        // stays on disk in case we want to bring it back later.
        { path: '/my-cohort', redirect: '/settings?tab=cohort' },
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
        // Front door: unauthenticated users hitting `/` see the marketing
        // landing page (LandingView). All other private routes still
        // bounce to /login so deep links don't lose their destination.
        if (to.path === '/' || to.name === 'dashboard') {
            return { name: 'welcome' };
        }
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
