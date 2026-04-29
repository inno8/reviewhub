<script setup lang="ts">
/**
 * GitHubConnectedView — landing page after a successful GitHub App install.
 *
 * GitHub redirects the student's browser to:
 *   https://on-boardia.com/dev-profile/connected
 *     ?installation_id=12345678
 *     &setup_action=install
 *
 * This view reads installation_id from the query string, calls
 * api.github.syncInstallation(), and shows the result. Three outcomes:
 *
 *   1. Success — display "Connected to N repos" + a Continue button
 *      that bounces back to /dev-profile-setup so the student finishes
 *      onboarding with a connected install
 *   2. Already-linked-to-different-account (409) — uncommon but worth
 *      a clear message ("This install belongs to another LEERA user")
 *   3. Backend error — show the message + a Retry button
 */
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/composables/useApi';

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const error = ref<string | null>(null);
const result = ref<{
  installation_id: number;
  github_account_login: string;
  repo_count: number;
  repos: { github_repo_id: number; full_name: string }[];
} | null>(null);

async function syncInstallation() {
  loading.value = true;
  error.value = null;
  const raw = route.query.installation_id;
  const installationId = Number(Array.isArray(raw) ? raw[0] : raw);
  if (!installationId || Number.isNaN(installationId)) {
    error.value =
      'No installation id in the URL. Did you start the install from inside LEERA? ' +
      'Try again from your dev-profile setup.';
    loading.value = false;
    return;
  }
  try {
    const { data } = await api.github.syncInstallation(installationId);
    result.value = data;
  } catch (e: any) {
    const status = e?.response?.status;
    const detail = e?.response?.data?.detail;
    if (status === 409) {
      error.value =
        detail || 'This GitHub install is already linked to another LEERA account.';
    } else if (status === 503) {
      error.value =
        'GitHub App is not configured on this server. Contact support.';
    } else if (status === 502) {
      error.value =
        detail ||
        'GitHub did not respond as expected. Try again, or re-install the App if the issue persists.';
    } else {
      error.value = detail || `Couldn't complete the connection (status ${status ?? '?'}).`;
    }
  } finally {
    loading.value = false;
  }
}

function continueOnboarding() {
  router.push({ name: 'dev-profile-setup' });
}

function retry() {
  syncInstallation();
}

function tryAgainFromOnboarding() {
  router.push({ name: 'dev-profile-setup' });
}

onMounted(syncInstallation);
</script>

<template>
  <div class="min-h-screen bg-background flex flex-col items-center justify-center p-6">
    <main class="w-full max-w-lg">
      <!-- Brand -->
      <div class="flex flex-col items-center mb-8">
        <img src="/logo/leera-wordmark-primary.svg" alt="LEERA" class="h-9 mb-3" />
        <p class="text-on-surface-variant text-sm tracking-wide">GitHub gekoppeld</p>
      </div>

      <!-- Loading -->
      <div
        v-if="loading"
        class="bg-surface-container-low rounded-xl border border-outline-variant/15 p-8 text-center"
      >
        <span class="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
        <p class="mt-3 text-sm text-on-surface-variant">Connecting your GitHub install...</p>
      </div>

      <!-- Success -->
      <div
        v-else-if="result"
        class="bg-surface-container-low rounded-xl border border-primary/30 p-8 text-center shadow-2xl"
      >
        <span class="material-symbols-outlined text-primary text-5xl mb-4">check_circle</span>
        <h1 class="text-2xl font-bold text-on-surface mb-2">
          GitHub connected
        </h1>
        <p class="text-on-surface-variant text-sm mb-6">
          LEERA can now read pull requests + post review comments on
          <strong class="text-on-surface">{{ result.repo_count }}</strong>
          {{ result.repo_count === 1 ? 'repository' : 'repositories' }}
          under
          <strong class="text-on-surface">@{{ result.github_account_login }}</strong>.
        </p>

        <!-- Repo list -->
        <ul
          v-if="result.repos.length"
          class="bg-surface-container rounded-lg border border-outline-variant/10 mb-6 text-left"
        >
          <li
            v-for="repo in result.repos"
            :key="repo.github_repo_id"
            class="px-4 py-3 border-b border-outline-variant/5 last:border-b-0 flex items-center gap-3"
          >
            <span class="material-symbols-outlined text-sm text-primary">folder_open</span>
            <span class="font-mono text-sm text-on-surface">{{ repo.full_name }}</span>
          </li>
        </ul>

        <button
          @click="continueOnboarding"
          class="primary-gradient text-on-primary px-6 py-3 rounded-lg font-bold text-sm w-full hover:opacity-95 transition-opacity active:scale-95"
        >
          Continue onboarding
          <span class="material-symbols-outlined text-sm align-middle ml-1">arrow_forward</span>
        </button>

        <p class="text-xs text-outline mt-4">
          Need to add or remove repos later?
          <a
            :href="`https://github.com/settings/installations/${result.installation_id}`"
            target="_blank"
            rel="noopener"
            class="text-primary hover:underline"
          >Manage on GitHub</a>
        </p>
      </div>

      <!-- Error -->
      <div
        v-else-if="error"
        class="bg-surface-container-low rounded-xl border border-error/30 p-8 text-center shadow-2xl"
      >
        <span class="material-symbols-outlined text-error text-5xl mb-4">error</span>
        <h1 class="text-xl font-bold text-on-surface mb-2">
          Connection failed
        </h1>
        <p class="text-on-surface-variant text-sm mb-6">{{ error }}</p>
        <div class="flex gap-3 justify-center">
          <button
            @click="retry"
            class="bg-surface-container-highest text-on-surface px-5 py-2.5 rounded-lg font-bold text-sm hover:bg-surface-container-high transition-colors active:scale-95"
          >
            Try again
          </button>
          <button
            @click="tryAgainFromOnboarding"
            class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold text-sm active:scale-95"
          >
            Back to onboarding
          </button>
        </div>
      </div>
    </main>
  </div>
</template>
