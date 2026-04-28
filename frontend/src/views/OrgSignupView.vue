<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const router = useRouter();
const auth = useAuthStore();

const orgName = ref('');
const adminEmail = ref('');
const adminPassword = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const errors = ref<Record<string, string>>({});
const success = ref(false);

async function handleSubmit() {
  errors.value = {};

  if (!orgName.value.trim()) {
    errors.value.org_name = 'Organization name is required.';
  }
  if (!adminEmail.value.trim()) {
    errors.value.admin_email = 'Email is required.';
  }
  if (adminPassword.value.length < 8) {
    errors.value.admin_password = 'Password must be at least 8 characters.';
  }
  if (adminPassword.value !== confirmPassword.value) {
    errors.value.confirm_password = 'Passwords do not match.';
  }
  if (Object.keys(errors.value).length) return;

  loading.value = true;
  try {
    const { data } = await api.org.signup({
      org_name: orgName.value.trim(),
      admin_email: adminEmail.value.trim(),
      admin_password: adminPassword.value,
    });

    // Log the admin in immediately
    auth.setTokens(data.tokens.access, data.tokens.refresh);
    auth.setUser(data.user);
    success.value = true;

    // Redirect to dashboard after a beat
    setTimeout(() => router.push('/'), 1500);
  } catch (e: any) {
    const data = e?.response?.data;
    if (data && typeof data === 'object') {
      for (const [key, val] of Object.entries(data)) {
        errors.value[key] = Array.isArray(val) ? val[0] : String(val);
      }
    } else {
      errors.value.general = 'Something went wrong. Please try again.';
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-6 tonal-stacking-bg">
    <main class="w-full max-w-md">
      <!-- Brand -->
      <div class="flex flex-col items-center mb-10">
        <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" class="h-9 mb-3" />
        <p class="text-on-surface-variant text-sm tracking-wide">REGISTREER JE ORGANISATIE</p>
      </div>

      <!-- Success state -->
      <div v-if="success" class="bg-surface-container-low rounded-xl border border-primary/20 p-8 text-center">
        <span class="material-symbols-outlined text-primary text-5xl mb-4">check_circle</span>
        <h2 class="text-xl font-bold text-on-surface mb-2">Organization Created</h2>
        <p class="text-on-surface-variant text-sm">Redirecting to your dashboard...</p>
      </div>

      <!-- Signup form -->
      <div v-else class="bg-surface-container-low rounded-xl border border-outline-variant/15 p-8 shadow-2xl relative overflow-hidden">
        <div class="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 blur-[64px] rounded-full"></div>

        <div class="relative z-10">
          <header class="mb-8">
            <h2 class="text-xl font-bold text-on-surface">Create your organization</h2>
            <p class="text-on-surface-variant text-sm mt-1">Set up your school or bootcamp to start monitoring student progress</p>
          </header>

          <!-- General error -->
          <div v-if="errors.general" class="mb-6 p-3 bg-error/10 border border-error/20 rounded-lg">
            <p class="text-error text-sm">{{ errors.general }}</p>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-5">
            <!-- Org name -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Organization Name
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">corporate_fare</span>
                <input v-model="orgName" type="text" placeholder="e.g. CodeCamp Academy"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required />
              </div>
              <p v-if="errors.org_name" class="text-error text-xs ml-1">{{ errors.org_name }}</p>
            </div>

            <!-- Admin email -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Admin Email
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">mail</span>
                <input v-model="adminEmail" type="email" placeholder="admin@yourorg.com"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required />
              </div>
              <p v-if="errors.admin_email" class="text-error text-xs ml-1">{{ errors.admin_email }}</p>
            </div>

            <!-- Password -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Password
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock</span>
                <input v-model="adminPassword" type="password" placeholder="Min. 8 characters"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required />
              </div>
              <p v-if="errors.admin_password" class="text-error text-xs ml-1">{{ errors.admin_password }}</p>
            </div>

            <!-- Confirm password -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Confirm Password
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock</span>
                <input v-model="confirmPassword" type="password" placeholder="Repeat password"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required />
              </div>
              <p v-if="errors.confirm_password" class="text-error text-xs ml-1">{{ errors.confirm_password }}</p>
            </div>

            <!-- Submit -->
            <button type="submit" :disabled="loading"
              class="w-full primary-gradient text-on-primary font-bold py-3.5 rounded-lg active:scale-[0.98] transition-transform flex items-center justify-center gap-2 group disabled:opacity-50">
              <span>{{ loading ? 'Creating...' : 'Create Organization' }}</span>
              <span class="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">arrow_forward</span>
            </button>
          </form>

          <div class="mt-8 pt-6 border-t border-outline-variant/10 text-center">
            <p class="text-sm text-on-surface-variant">
              Already have an account?
              <router-link to="/login" class="text-primary-container font-semibold hover:underline ml-1">Sign in</router-link>
            </p>
          </div>
        </div>
      </div>
    </main>

    <!-- Decorative -->
    <div class="fixed top-0 left-0 w-full h-full pointer-events-none z-[-1] opacity-20 overflow-hidden">
      <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 blur-[120px] rounded-full"></div>
      <div class="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-secondary/10 blur-[100px] rounded-full"></div>
    </div>
  </div>
</template>
