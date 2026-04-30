<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const token = ref('');
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const errors = ref<Record<string, string>>({});
const success = ref(false);
const orgName = ref('');
const expired = ref(false);

onMounted(() => {
  token.value = (route.query.token as string) || '';
  if (!token.value) {
    errors.value.token = 'No invitation token provided. Check your email link.';
  }
});

async function handleSubmit() {
  errors.value = {};

  if (!token.value) {
    errors.value.token = 'Invalid invitation link.';
    return;
  }
  if (password.value.length < 8) {
    errors.value.password = 'Password must be at least 8 characters.';
  }
  if (password.value !== confirmPassword.value) {
    errors.value.confirm_password = 'Passwords do not match.';
  }
  if (Object.keys(errors.value).length) return;

  loading.value = true;
  try {
    const { data } = await api.org.acceptInvite({
      token: token.value,
      username: username.value.trim() || undefined,
      password: password.value,
    });

    orgName.value = data.organization?.name || '';
    auth.setTokens(data.tokens.access, data.tokens.refresh);
    auth.setUser(data.user);
    success.value = true;

    // Backend sets `returning: true` when the user previously existed
    // and had Submissions — typical case is being re-added after a
    // school-admin removal. Stash a flag in localStorage so the
    // dashboard can show "Welkom terug" once instead of the default
    // first-time copy.
    if (data.returning) {
      try {
        localStorage.setItem(
          'leera.welcomeBack',
          JSON.stringify({ orgName: orgName.value, ts: Date.now() }),
        );
      } catch { /* localStorage may be disabled in private mode */ }
    }

    // Role-aware landing:
    //   teacher → /grading (their primary surface)
    //   admin   → /org-dashboard
    //   student (developer) → / (Dashboard)
    //   ops (is_superuser)  → /ops
    const role = String(data.user?.role ?? '').toLowerCase();
    let landingPath = '/';
    if (data.user?.is_superuser) landingPath = '/ops';
    else if (role === 'teacher') landingPath = '/grading';
    else if (role === 'admin') landingPath = '/org-dashboard';
    setTimeout(() => router.push(landingPath), 2000);
  } catch (e: any) {
    const data = e?.response?.data;
    if (data && typeof data === 'object') {
      for (const [key, val] of Object.entries(data)) {
        errors.value[key] = Array.isArray(val) ? val[0] : String(val);
      }
      if (errors.value.token?.toLowerCase().includes('expired')) {
        expired.value = true;
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
        <p class="text-on-surface-variant text-sm tracking-wide">Nakijken Copilot voor het MBO</p>
      </div>

      <!-- Expired -->
      <div v-if="expired" class="bg-surface-container-low rounded-xl border border-error/20 p-8 text-center">
        <span class="material-symbols-outlined text-error text-5xl mb-4">timer_off</span>
        <h2 class="text-xl font-bold text-on-surface mb-2">Uitnodiging verlopen</h2>
        <p class="text-on-surface-variant text-sm mb-6">Deze uitnodigingslink is verlopen. Vraag je beheerder om een nieuwe te versturen.</p>
        <router-link to="/login" class="text-primary font-semibold hover:underline">Naar inloggen</router-link>
      </div>

      <!-- Success -->
      <div v-else-if="success" class="bg-surface-container-low rounded-xl border border-primary/20 p-8 text-center">
        <span class="material-symbols-outlined text-primary text-5xl mb-4">celebration</span>
        <h2 class="text-xl font-bold text-on-surface mb-2">Welkom!</h2>
        <p class="text-on-surface-variant text-sm">
          Je bent nu lid van <strong class="text-on-surface">{{ orgName }}</strong>. Je wordt doorgestuurd...
        </p>
      </div>

      <!-- No token -->
      <div v-else-if="!token" class="bg-surface-container-low rounded-xl border border-error/20 p-8 text-center">
        <span class="material-symbols-outlined text-error text-5xl mb-4">link_off</span>
        <h2 class="text-xl font-bold text-on-surface mb-2">Ongeldige link</h2>
        <p class="text-on-surface-variant text-sm mb-6">Geen uitnodigingstoken gevonden. Gebruik de volledige link uit je e-mail.</p>
        <router-link to="/login" class="text-primary font-semibold hover:underline">Naar inloggen</router-link>
      </div>

      <!-- Accept form -->
      <div v-else class="bg-surface-container-low rounded-xl border border-outline-variant/15 p-8 shadow-2xl relative overflow-hidden">
        <div class="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 blur-[64px] rounded-full"></div>

        <div class="relative z-10">
          <header class="mb-8">
            <h2 class="text-xl font-bold text-on-surface">Stel je account in</h2>
            <p class="text-on-surface-variant text-sm mt-1">Kies een gebruikersnaam en wachtwoord om je registratie af te ronden</p>
          </header>

          <div v-if="errors.general || errors.token" class="mb-6 p-3 bg-error/10 border border-error/20 rounded-lg">
            <p class="text-error text-sm">{{ errors.general || errors.token }}</p>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-5">
            <!-- Username (optional) -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Gebruikersnaam <span class="text-outline/50 normal-case">(optioneel)</span>
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">person</span>
                <input v-model="username" type="text" placeholder="Je weergavenaam"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40" />
              </div>
            </div>

            <!-- Password -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Wachtwoord
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock</span>
                <input v-model="password" type="password" placeholder="Min. 8 karakters"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required />
              </div>
              <p v-if="errors.password" class="text-error text-xs ml-1">{{ errors.password }}</p>
            </div>

            <!-- Confirm password -->
            <div class="space-y-2">
              <label class="block text-xs font-semibold uppercase tracking-widest text-outline ml-1">
                Bevestig wachtwoord
              </label>
              <div class="relative">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-xl">lock</span>
                <input v-model="confirmPassword" type="password" placeholder="Herhaal wachtwoord"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-3 pl-10 pr-4 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary transition-all placeholder:text-outline/40"
                  required />
              </div>
              <p v-if="errors.confirm_password" class="text-error text-xs ml-1">{{ errors.confirm_password }}</p>
            </div>

            <button type="submit" :disabled="loading"
              class="w-full primary-gradient text-on-primary font-bold py-3.5 rounded-lg active:scale-[0.98] transition-transform flex items-center justify-center gap-2 group disabled:opacity-50">
              <span>{{ loading ? 'Bezig met aanmelden...' : 'Account aanmaken' }}</span>
              <span class="material-symbols-outlined text-sm transition-transform group-hover:translate-x-1">arrow_forward</span>
            </button>
          </form>

          <div class="mt-8 pt-6 border-t border-outline-variant/10 text-center">
            <p class="text-sm text-on-surface-variant">
              Heb je al een account?
              <router-link to="/login" class="text-primary-container font-semibold hover:underline ml-1">Inloggen</router-link>
            </p>
          </div>
        </div>
      </div>
    </main>

    <div class="fixed top-0 left-0 w-full h-full pointer-events-none z-[-1] opacity-20 overflow-hidden">
      <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/20 blur-[120px] rounded-full"></div>
      <div class="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-secondary/10 blur-[100px] rounded-full"></div>
    </div>
  </div>
</template>
