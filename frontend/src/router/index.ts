import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '@/views/LoginView.vue';
import DashboardView from '@/views/DashboardView.vue';
import FindingDetailView from '@/views/FindingDetailView.vue';
import PerformanceView from '@/views/PerformanceView.vue';
import UserManagementView from '@/views/UserManagementView.vue';
import { useAuthStore } from '@/stores/auth';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/findings/:id', name: 'finding-detail', component: FindingDetailView, props: true },
    { path: '/performance', name: 'performance', component: PerformanceView },
    { path: '/users', name: 'users', component: UserManagementView, meta: { admin: true } },
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
