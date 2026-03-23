import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { useApi } from '@/composables/useApi';

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  role: 'ADMIN' | 'INTERN';
}

export const useAuthStore = defineStore('auth', () => {
  const api = useApi();
  const token = ref<string | null>(localStorage.getItem('reviewhub_token'));
  const user = ref<AuthUser | null>(null);
  const loading = ref(false);
  const initialized = ref(false);

  const isAuthenticated = computed(() => !!token.value && !!user.value);

  async function login(email: string, password: string) {
    loading.value = true;
    try {
      const { data } = await api.post('/auth/login', { email, password });
      token.value = data.token;
      user.value = data.user;
      localStorage.setItem('reviewhub_token', data.token);
    } finally {
      loading.value = false;
    }
  }

  function logout() {
    token.value = null;
    user.value = null;
    localStorage.removeItem('reviewhub_token');
  }

  async function bootstrap() {
    if (!token.value) {
      initialized.value = true;
      return;
    }
    try {
      const { data } = await api.get('/auth/me');
      user.value = data.user;
    } catch {
      logout();
    } finally {
      initialized.value = true;
    }
  }

  return { token, user, loading, initialized, isAuthenticated, login, logout, bootstrap };
});
