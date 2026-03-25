import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/composables/useApi';
export const useAuthStore = defineStore('auth', () => {
    const token = ref(localStorage.getItem('reviewhub_token'));
    const user = ref(null);
    const loading = ref(false);
    const initialized = ref(false);
    const isAuthenticated = computed(() => !!token.value && !!user.value);
    const isAdmin = computed(() => user.value?.role === 'ADMIN');
    async function login(email, password) {
        loading.value = true;
        try {
            const { data } = await api.auth.login(email, password);
            token.value = data.token;
            user.value = data.user;
            localStorage.setItem('reviewhub_token', data.token);
        }
        finally {
            loading.value = false;
        }
    }
    async function logout() {
        try {
            if (token.value) {
                await api.auth.logout();
            }
        }
        catch {
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
        try {
            const { data } = await api.auth.me();
            user.value = data.user;
        }
        catch {
            await logout();
        }
        finally {
            initialized.value = true;
        }
    }
    return { token, user, loading, initialized, isAuthenticated, isAdmin, login, logout, bootstrap };
});
