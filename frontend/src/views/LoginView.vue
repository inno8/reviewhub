<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();

const email = ref('');
const password = ref('');
const error = ref('');
const loading = ref(false);

async function handleSubmit() {
  error.value = '';
  loading.value = true;

  try {
    await auth.login(email.value, password.value);
    router.push('/');
  } catch (e: any) {
    error.value = e.response?.data?.error || 'Invalid credentials';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-6 tonal-stacking-bg">
    <main class="w-full max-w-md">
      <!-- Brand Identity -->
      <div class="flex flex-col items-center mb-10">
        <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" class="h-9 mb-3" />
        <p class="text-on-surface-variant text-sm tracking-wide">Nakijken Copilot voor het MBO</p>
      </div>

      <!-- Login Card -->
      <div class="bg-surface-container-low rounded-xl border border-outline-variant/15 p-8 shadow-2xl relative overflow-hidden">
        <!-- Asymmetric Glow Accent -->
        <div class="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 blur-[64px] rounded-full"></div>

        <div class="relative z-10">
          <header class="mb-8">
            <h2 class="text-xl font-bold text-on-surface">Welcome back</h2>
            <p class="text-on-surface-variant text-sm mt-1">Access your editorial code space</p>
          </header>

          <!-- Error Message -->
          <div v-if="error" class="mb-6 p-3 bg-error/10 border border-error/20 rounded-lg">
            <p class="text-error text-sm">{{ error }}</p>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-6">
            <!-- Email Field -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Email
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">person</span>
                <input
                  v-model="email"
                  type="email"
                  placeholder="naam@school.nl"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required
                />
              </div>
            </div>

            <!-- Password Field -->
            <div class="space-y-2">
              <div class="ml-1">
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline">
                  Password
                </label>
                <!-- Forgot-password flow not implemented yet (v1.1 backlog —
                     see docs/TODO.md). The link is removed until the
                     PasswordResetRequest + PasswordResetConfirm views land. -->
              </div>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock</span>
                <input
                  v-model="password"
                  type="password"
                  placeholder="••••••••"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required
                />
              </div>
            </div>

            <!-- CTA Button -->
            <button
              type="submit"
              :disabled="loading"
              class="w-full primary-gradient text-on-primary font-bold py-3.5 rounded-lg active:scale-[0.98] transition-transform flex items-center justify-center gap-2 group disabled:opacity-50"
            >
              <span>{{ loading ? 'Signing in...' : 'Sign In' }}</span>
              <span class="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">arrow_forward</span>
            </button>
          </form>

          <!-- Footer Links -->
          <div class="mt-8 pt-6 border-t border-outline-variant/10 text-center space-y-2">
            <p class="text-sm text-on-surface-variant">
              First time here?
              <router-link to="/onboard" class="text-primary-container font-semibold hover:underline ml-1">Set up your account</router-link>
            </p>
            <p class="text-sm text-on-surface-variant">
              Running a school or bootcamp?
              <router-link to="/org-signup" class="text-primary-container font-semibold hover:underline ml-1">Register your organization</router-link>
            </p>
          </div>
        </div>
      </div>

    </main>

    <!-- Footer -->
    <footer class="mt-auto py-8 w-full max-w-4xl flex flex-col md:flex-row justify-between items-center px-6 gap-4">
      <div class="text-[10px] uppercase tracking-[0.2em] text-outline font-medium">
        © 2026 Leera
      </div>
      <div class="flex gap-6">
        <a href="#" class="text-[10px] uppercase tracking-[0.2em] text-outline hover:text-primary transition-colors">Documentation</a>
        <a href="#" class="text-[10px] uppercase tracking-[0.2em] text-outline hover:text-primary transition-colors">System Status</a>
        <a href="#" class="text-[10px] uppercase tracking-[0.2em] text-outline hover:text-primary transition-colors">Privacy</a>
      </div>
    </footer>

    <!-- Decorative Elements -->
    <div class="fixed top-0 left-0 w-full h-full pointer-events-none z-[-1] opacity-20 overflow-hidden">
      <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 blur-[120px] rounded-full"></div>
      <div class="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-secondary/10 blur-[100px] rounded-full"></div>
    </div>
  </div>
</template>
