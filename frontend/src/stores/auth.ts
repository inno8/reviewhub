import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api, setSkipAuthRedirect } from '@/composables/useApi';

/**
 * Real role taxonomy from Django's User.Role enum.
 *
 * Before the grading app this store collapsed everything to ADMIN | INTERN,
 * which made it impossible to distinguish a teacher (grader) from an admin
 * (school owner) from a developer (student) from a platform superuser (us).
 *
 * Nakijken Copilot v1 needs four distinct navigation experiences:
 *   - developer (student)       → skills, recommendations, journey, timeline
 *   - teacher (docent)           → grading inbox + team, nothing dev-y
 *   - admin (school owner)       → org dashboard + team + LLM usage
 *   - is_superuser (platform ops)→ ops dashboard (cost across all schools, LLM config)
 */
export type UserRole = 'admin' | 'teacher' | 'developer' | 'viewer';

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  isSuperuser: boolean;
  devProfileCompleted: boolean;
}

function normalizeRole(raw: unknown): UserRole {
  const s = String(raw ?? '').toLowerCase();
  if (s === 'admin') return 'admin';
  if (s === 'teacher' || s === 'docent') return 'teacher';
  if (s === 'viewer') return 'viewer';
  // Any legacy value (INTERN, empty, unknown) maps to developer — safest default.
  return 'developer';
}

function mapUserData(userData: any): AuthUser {
  return {
    id: userData.id,
    username: userData.username,
    email: userData.email,
    role: normalizeRole(userData.role),
    isSuperuser: Boolean(userData.is_superuser),
    devProfileCompleted: !!userData.dev_profile_completed,
  };
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('reviewhub_token'));
  const user = ref<AuthUser | null>(null);
  const loading = ref(false);
  const initialized = ref(false);

  const isAuthenticated = computed(() => !!token.value && !!user.value);

  // ── role predicates ────────────────────────────────────────────────
  // Use these in components instead of string-matching role yourself.
  const isStudent = computed(() => user.value?.role === 'developer');
  const isTeacher = computed(() => user.value?.role === 'teacher');
  const isSchoolAdmin = computed(() => user.value?.role === 'admin');
  const isSuperuser = computed(() => user.value?.isSuperuser === true);

  // Legacy compat: some components still check `isAdmin`. Keep it around but
  // expand its meaning: admin OR teacher OR superuser (i.e. "not a student").
  const isAdmin = computed(
    () => isSchoolAdmin.value || isTeacher.value || isSuperuser.value,
  );

  // "Can see the ops dashboard" — strictly platform owners.
  const isOps = computed(() => isSuperuser.value);

  async function login(email: string, password: string) {
    loading.value = true;
    try {
      const { data } = await api.auth.login(email, password);
      const newToken = data.access || data.token;
      if (newToken) {
        token.value = newToken;
        localStorage.setItem('reviewhub_token', newToken);
      }
      const meResponse = await api.auth.me();
      const userData = meResponse.data.user || meResponse.data;
      user.value = mapUserData(userData);
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    try {
      if (token.value) await api.auth.logout();
    } catch {
      // ignore logout API errors and clear local session anyway.
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
    setSkipAuthRedirect(true);
    try {
      const { data } = await api.auth.me();
      const userData = data.user || data;
      user.value = mapUserData(userData);
    } catch {
      token.value = null;
      user.value = null;
      localStorage.removeItem('reviewhub_token');
    } finally {
      setSkipAuthRedirect(false);
      initialized.value = true;
    }
  }

  function setTokens(accessToken: string, refreshToken?: string) {
    token.value = accessToken;
    localStorage.setItem('reviewhub_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('reviewhub_refresh_token', refreshToken);
    }
  }

  function setUser(userData: any) {
    user.value = mapUserData(userData);
  }

  function markDevProfileCompleted() {
    if (user.value) {
      user.value = { ...user.value, devProfileCompleted: true };
    }
  }

  return {
    token, user, loading, initialized,
    isAuthenticated,
    // role predicates
    isStudent, isTeacher, isSchoolAdmin, isSuperuser, isOps,
    // legacy compat
    isAdmin,
    login, logout, bootstrap, setTokens, setUser, markDevProfileCompleted,
  };
});
