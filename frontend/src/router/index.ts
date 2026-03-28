import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import FindingDetailView from '@/views/FindingDetailView.vue';
import FileReviewView from '@/views/FileReviewView.vue';
import PerformanceView from '@/views/PerformanceView.vue';
import UserManagementView from '@/views/UserManagementView.vue';
import SettingsView from '@/views/SettingsView.vue';
import OnboardView from '@/views/OnboardView.vue';
import { useAuthStore } from '@/stores/auth';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/onboard', name: 'onboard', component: OnboardView, meta: { public: true } },
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/findings/:id', name: 'finding-detail', component: FindingDetailView, props: true },
    { path: '/file-review', name: 'file-review', component: FileReviewView },
    { path: '/insights', name: 'insights', component: PerformanceView },
    { path: '/team', name: 'team', component: UserManagementView, meta: { admin: true } },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
});

router.beforeEach(async (to) => {
  console.log('[Router] Navigating to:', to.path, 'meta:', to.meta);
  const auth = useAuthStore();
  if (!auth.initialized) {
    console.log('[Router] Bootstrap starting...');
    await auth.bootstrap();
    console.log('[Router] Bootstrap done, isAuthenticated:', auth.isAuthenticated);
  }

  if (to.meta.public) {
    console.log('[Router] Public route, allowing');
    return true;
  }
  if (!auth.isAuthenticated) {
    console.log('[Router] Not authenticated, redirecting to login');
    return { name: 'login' };
  }
  if (to.meta.admin && auth.user?.role !== 'ADMIN') {
    return { name: 'dashboard' };
  }
  return true;
});

export default router;
