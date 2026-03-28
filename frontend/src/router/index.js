import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '@/views/LoginView.vue';
import RegisterView from '@/views/RegisterView.vue';
import DashboardView from '@/views/DashboardView.vue';
import SkillsDashboardView from '@/views/SkillsDashboardView.vue';
import FindingDetailView from '@/views/FindingDetailView.vue';
import FileReviewView from '@/views/FileReviewView.vue';
import PerformanceView from '@/views/PerformanceView.vue';
import UserManagementView from '@/views/UserManagementView.vue';
import SettingsView from '@/views/SettingsView.vue';
import NotificationsView from '@/views/NotificationsView.vue';
import { useAuthStore } from '@/stores/auth';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
        { path: '/register', name: 'register', component: RegisterView, meta: { public: true } },
        { path: '/', name: 'dashboard', component: DashboardView },
        { path: '/skills', name: 'skills', component: SkillsDashboardView },
        { path: '/findings/:id', name: 'finding-detail', component: FindingDetailView, props: true },
        { path: '/file-review', name: 'file-review', component: FileReviewView },
        { path: '/insights', name: 'insights', component: PerformanceView },
        { path: '/team', name: 'team', component: UserManagementView, meta: { admin: true } },
        { path: '/settings', name: 'settings', component: SettingsView },
        { path: '/notifications', name: 'notifications', component: NotificationsView },
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
    return true;
});
export default router;
