import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api, setSkipAuthRedirect } from '@/composables/useApi';

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  role: 'ADMIN' | 'INTERN';
  devProfileCompleted: boolean;
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('reviewhub_token'));
  const user = ref<AuthUser | null>(null);
  const loading = ref(false);
  const initialized = ref(false);

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const isAdmin = computed(() => user.value?.role === 'ADMIN');

  async function login(email: string, password: string) {
    loading.value = true;
    try {
      const { data } = await api.auth.login(email, password);
      // Django JWT returns { access, refresh }
      const newToken = data.access || data.token; // Support both formats
      if (newToken) {
        token.value = newToken;
        localStorage.setItem('reviewhub_token', newToken);
      }
      
      // Fetch user profile separately
      const meResponse = await api.auth.me();
      // Express returns { user: {...} }
      const userData = meResponse.data.user || meResponse.data;
      user.value = {
        id: userData.id,
        username: userData.username,
        email: userData.email,
        role: mapRoleToFrontend(userData.role),
        devProfileCompleted: !!userData.dev_profile_completed,
      };
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    try {
      if (token.value) {
        await api.auth.logout();
      }
    } catch {
      // Ignore logout API errors and clear local session anyway.
    }
    token.value = null;
    user.value = null;
    localStorage.removeItem('reviewhub_token');
  }

  async function bootstrap() {
    if (!token.value) {
      initialized.value = true;
      return;
    }
    // Skip auth redirect during bootstrap to prevent redirect loops
    setSkipAuthRedirect(true);
    try {
      const { data } = await api.auth.me();
      // Express returns { user: {...} }
      const userData = data.user || data;
      user.value = {
        id: userData.id,
        username: userData.username,
        email: userData.email,
        role: mapRoleToFrontend(userData.role),
        devProfileCompleted: !!userData.dev_profile_completed,
      };
    } catch {
      // Token is invalid, clear it silently
      token.value = null;
      user.value = null;
      localStorage.removeItem('reviewhub_token');
    } finally {
      setSkipAuthRedirect(false);
      initialized.value = true;
    }
  }
  
  function mapRoleToFrontend(role: string): 'ADMIN' | 'INTERN' {
    // Map roles to frontend format (Express uses ADMIN/INTERN directly)
    if (role === 'ADMIN' || role === 'admin') {
      return 'ADMIN';
    }
    return 'INTERN';
  }

  function setTokens(accessToken: string, refreshToken?: string) {
    token.value = accessToken;
    localStorage.setItem('reviewhub_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('reviewhub_refresh_token', refreshToken);
    }
  }

  function setUser(userData: any) {
    user.value = {
      id: userData.id,
      username: userData.username,
      email: userData.email,
      role: mapRoleToFrontend(userData.role || 'INTERN'),
      devProfileCompleted: !!userData.dev_profile_completed,
    };
  }

  function markDevProfileCompleted() {
    if (user.value) {
      user.value = { ...user.value, devProfileCompleted: true };
    }
  }

  return { token, user, loading, initialized, isAuthenticated, isAdmin, login, logout, bootstrap, setTokens, setUser, markDevProfileCompleted };
});
