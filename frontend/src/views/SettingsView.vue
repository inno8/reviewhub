<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import MyCohortWidget from '@/components/grading/MyCohortWidget.vue';
import { useAuthStore } from '@/stores/auth';
import { useProjectsStore } from '@/stores/projects';
import { api } from '@/composables/useApi';

const auth = useAuthStore();
const projectsStore = useProjectsStore();
const route = useRoute();
const router = useRouter();

const activeTab = ref('profile');

const profile = ref({ username: '', email: '', telegramChatId: '' });
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const toastMessage = ref('');
const toastType = ref<'success' | 'error'>('success');

const notificationSettings = ref({
  emailDigest: true,
  telegramAlerts: false,
  newReviewNotify: true,
  prCreatedNotify: true,
});

// LLM config (admin)
type LlmAuthChoice = 'api_key' | 'token' | 'oauth_google';

interface LLMConfig {
  provider: string;
  auth_method: 'api_key' | 'access_token' | 'oauth_google';
  api_key: string;
  access_token: string;
  model: string;
  is_default: boolean;
}
const llmConfigs = ref<LLMConfig[]>([]);
const llmLoading = ref(false);
const llmTestLoading = ref<string | null>(null);
const llmTestResult = ref<{ success: boolean; message: string } | null>(null);
const googleOAuthLoading = ref(false);
const newLlm = ref({
  provider: 'openai',
  auth_choice: 'api_key' as LlmAuthChoice,
  api_key: '',
  access_token: '',
  model: '',
  is_default: false,
});

function authMethodLabel(m: string) {
  if (m === 'oauth_google') return 'Google OAuth';
  if (m === 'access_token') return 'Access token';
  return 'API key';
}

function credentialPreview(c: LLMConfig) {
  if (c.auth_method === 'oauth_google') return 'Google account';
  const s =
    c.auth_method === 'access_token' ? (c.access_token || '') : (c.api_key || '');
  if (!s || s.length < 4) return '—';
  return `****${s.slice(-4)}`;
}

/** Five current/popular API models per provider (labels for UI, value = provider model id). */
const llmProviders = [
  {
    value: 'openai',
    label: 'ChatGPT (OpenAI)',
    defaultModel: 'gpt-4o',
    models: [
      { value: 'gpt-4o', label: 'GPT-4o' },
      { value: 'gpt-4o-mini', label: 'GPT-4o mini' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
      { value: 'o1', label: 'o1' },
      { value: 'o1-mini', label: 'o1 mini' },
    ],
  },
  {
    value: 'anthropic',
    label: 'Claude (Anthropic)',
    defaultModel: 'claude-sonnet-4-20250514',
    models: [
      { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4' },
      { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
      { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
      { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
      { value: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku' },
    ],
  },
  {
    value: 'google',
    label: 'Gemini (Google)',
    defaultModel: 'gemini-2.0-flash',
    models: [
      { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
      { value: 'gemini-2.0-flash-lite', label: 'Gemini 2.0 Flash-Lite' },
      { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
      { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
      { value: 'gemini-1.5-flash-8b', label: 'Gemini 1.5 Flash 8B' },
    ],
  },
];

const availableProviders = computed(() =>
  llmProviders.filter(p => !llmConfigs.value.some(c => c.provider === p.value))
);

const newLlmModelOptions = computed(() => {
  const p = llmProviders.find(x => x.value === newLlm.value.provider);
  return p?.models ?? [];
});

const newLlmAuthChoices = computed(() => {
  const p = newLlm.value.provider;
  if (p === 'google') {
    return [
      { value: 'api_key' as LlmAuthChoice, label: 'API key' },
      { value: 'oauth_google' as LlmAuthChoice, label: 'Sign in with Google (OAuth)' },
    ];
  }
  if (p === 'anthropic') {
    // Anthropic’s HTTP API only accepts Console API keys (x-api-key). There is no separate “session” token.
    return [{ value: 'api_key' as LlmAuthChoice, label: 'API key (Console)' }];
  }
  return [
    { value: 'api_key' as LlmAuthChoice, label: 'API key' },
    { value: 'token' as LlmAuthChoice, label: 'Codex / ChatGPT access token (Bearer)' },
  ];
});

function syncNewLlmModelToProvider() {
  const opts = newLlmModelOptions.value;
  if (!opts.length) return;
  if (!newLlm.value.model || !opts.some(o => o.value === newLlm.value.model)) {
    newLlm.value.model = opts[0].value;
  }
}

watch(
  () => newLlm.value.provider,
  () => {
    const allowed = newLlmAuthChoices.value.map((x) => x.value);
    if (!allowed.includes(newLlm.value.auth_choice)) {
      newLlm.value.auth_choice = 'api_key';
    }
    syncNewLlmModelToProvider();
  },
  { immediate: true }
);

watch(
  availableProviders,
  (list) => {
    if (!list.length) return;
    if (!list.some(p => p.value === newLlm.value.provider)) {
      newLlm.value.provider = list[0].value;
      syncNewLlmModelToProvider();
    }
  },
  { flush: 'post' }
);

// Webhook config (developer)
const webhookProjectId = ref<number | null>(null);
const webhookTestLoading = ref(false);
const webhookTestResult = ref<{ success: boolean; message: string } | null>(null);
const webhookRepoUrl = ref('');
const webhookRegisterLoading = ref(false);
const webhookRegisterResult = ref<{ success: boolean; message: string } | null>(null);
const webhookInfo = ref<{
  webhook_url: string;
  webhook_secret: string;
  provider: string;
  connected: boolean;
  webhook_active: boolean;
  instructions: string;
} | null>(null);
const webhookInfoLoading = ref(false);
const webhookSecretVisible = ref(false);

async function fetchWebhookInfo(projectId: number) {
  webhookInfoLoading.value = true;
  webhookSecretVisible.value = false;
  webhookRegisterResult.value = null;
  webhookTestResult.value = null;
  try {
    const { data } = await api.webhooks.info(projectId);
    webhookInfo.value = data;
  } catch {
    webhookInfo.value = null;
  } finally {
    webhookInfoLoading.value = false;
  }
}

watch(webhookProjectId, (id) => {
  if (id) fetchWebhookInfo(id);
  else webhookInfo.value = null;
});

interface GitConnRow {
  id: number;
  provider: string;
  username: string;
  email: string | null;
}

const gitConnectionsList = ref<GitConnRow[]>([]);
const newGitConn = ref({ provider: '' as '' | 'github' | 'gitlab' | 'bitbucket', username: '', email: '' });

const githubPat = ref({ configured: false, last_four: null as string | null });
const githubPatInput = ref('');
const githubPatSaving = ref(false);

async function loadGithubPat() {
  try {
    const { data } = await api.users.githubToken.get();
    githubPat.value = {
      configured: !!data.configured,
      last_four: data.last_four ?? null,
    };
  } catch {
    githubPat.value = { configured: false, last_four: null };
  }
}

async function saveGithubPat() {
  const t = githubPatInput.value.trim();
  if (!t) {
    showToast('Paste a token or use Remove if you want to clear it.', 'error');
    return;
  }
  githubPatSaving.value = true;
  try {
    await api.users.githubToken.save(t);
    githubPatInput.value = '';
    await loadGithubPat();
    showToast('GitHub token saved securely.', 'success');
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } } };
    showToast(ax.response?.data?.detail || 'Failed to save token', 'error');
  } finally {
    githubPatSaving.value = false;
  }
}

async function removeGithubPat() {
  if (!confirm('Remove your saved GitHub token? Private batch repos will stop working until you add one again.'))
    return;
  githubPatSaving.value = true;
  try {
    await api.users.githubToken.delete();
    await loadGithubPat();
    showToast('GitHub token removed.', 'success');
  } catch {
    showToast('Failed to remove token', 'error');
  } finally {
    githubPatSaving.value = false;
  }
}

onMounted(async () => {
  try {
    const { data } = await api.users.me();
    const u = (data as any).user || data;
    profile.value.username = u.username;
    profile.value.email = u.email;
    profile.value.telegramChatId = u.telegramChatId || '';
  } catch (e) {
    console.error('Failed to load profile:', e);
  }

  await loadGithubPat();

  await projectsStore.fetchProjects();

  if (auth.isAdmin) {
    await loadLlmConfigs();
    if (route.query.tab === 'llm') activeTab.value = 'llm';
    if (route.query.llm_oauth_success === '1') {
      await loadLlmConfigs();
      showToast('Google account connected for Gemini.', 'success');
      router.replace({ path: route.path, query: {} });
    }
    if (route.query.llm_oauth_error) {
      showToast(`Google sign-in failed: ${String(route.query.llm_oauth_error)}`, 'error');
      router.replace({ path: route.path, query: {} });
    }
  } else {
    await loadGitConnections();
  }
  if (!auth.isAdmin && projectsStore.projects.length) {
    webhookProjectId.value = projectsStore.selectedProjectId;
  }
  // Land on the cohort tab when the URL says so (the redirect from the
  // legacy /my-cohort route uses ?tab=cohort).
  if (auth.isStudent && route.query.tab === 'cohort') {
    activeTab.value = 'cohort';
  }
});

async function loadGitConnections() {
  try {
    const { data } = await api.gitConnections.list();
    gitConnectionsList.value = Array.isArray(data) ? data : (data as any).results || [];
  } catch {
    gitConnectionsList.value = [];
  }
}

async function addGitConnection() {
  if (!newGitConn.value.provider) {
    showToast('Select a provider.', 'error');
    return;
  }
  if (!newGitConn.value.username.trim()) {
    showToast('Enter your username on that host.', 'error');
    return;
  }
  loading.value = true;
  try {
    await api.gitConnections.create({
      provider: newGitConn.value.provider,
      username: newGitConn.value.username.trim(),
      email: newGitConn.value.email.trim() || null,
    });
    newGitConn.value = { provider: '', username: '', email: '' };
    await loadGitConnections();
    showToast('Connection added.', 'success');
  } catch (e: any) {
    const err = e?.response?.data;
    showToast(err?.username?.[0] || err?.error || 'Failed to add', 'error');
  } finally {
    loading.value = false;
  }
}

async function removeGitConnection(id: number) {
  if (!confirm('Remove this Git connection?')) return;
  loading.value = true;
  try {
    await api.gitConnections.delete(id);
    await loadGitConnections();
    showToast('Connection removed.', 'success');
  } catch {
    showToast('Failed to remove', 'error');
  } finally {
    loading.value = false;
  }
}

async function loadLlmConfigs() {
  llmLoading.value = true;
  try {
    const { data } = await api.llmConfig.get();
    const raw = (data as { configs?: LLMConfig[] }).configs || [];
    llmConfigs.value = raw.map((c) => ({
      ...c,
      auth_method: c.auth_method || 'api_key',
      access_token: c.access_token || '',
      api_key: c.api_key || '',
    }));
  } catch {
    llmConfigs.value = [];
  } finally {
    llmLoading.value = false;
  }
}

async function saveLlmConfig() {
  if (newLlm.value.auth_choice === 'oauth_google') {
    showToast('Use “Sign in with Google” to connect Gemini.', 'error');
    return;
  }
  syncNewLlmModelToProvider();
  const auth_method = newLlm.value.auth_choice === 'token' ? 'access_token' : 'api_key';
  if (auth_method === 'api_key' && !newLlm.value.api_key.trim()) {
    showToast('API key is required', 'error');
    return;
  }
  if (auth_method === 'access_token' && !newLlm.value.access_token.trim()) {
    showToast('Access token is required', 'error');
    return;
  }

  llmLoading.value = true;
  try {
    await api.llmConfig.save({
      provider: newLlm.value.provider,
      auth_method,
      api_key: auth_method === 'api_key' ? newLlm.value.api_key.trim() : '',
      access_token: auth_method === 'access_token' ? newLlm.value.access_token.trim() : '',
      model: newLlm.value.model,
      is_default: llmConfigs.value.length === 0,
    });
    showToast('LLM configuration saved!', 'success');
    await loadLlmConfigs();
    newLlm.value = {
      provider: availableProviders.value[0]?.value || 'openai',
      auth_choice: 'api_key',
      api_key: '',
      access_token: '',
      model: '',
      is_default: false,
    };
    syncNewLlmModelToProvider();
  } catch (e: any) {
    showToast(e?.response?.data?.error || 'Failed to save', 'error');
  } finally {
    llmLoading.value = false;
  }
}

async function startGoogleLlmOAuth() {
  if (newLlm.value.provider !== 'google') return;
  syncNewLlmModelToProvider();
  googleOAuthLoading.value = true;
  try {
    const { data } = await api.llmConfig.googleOAuthStart({ model: newLlm.value.model });
    const url = (data as { authorization_url?: string }).authorization_url;
    if (url) window.location.href = url;
    else showToast((data as { error?: string }).error || 'Could not start Google sign-in', 'error');
  } catch (e: any) {
    showToast(e?.response?.data?.error || 'Could not start Google sign-in', 'error');
  } finally {
    googleOAuthLoading.value = false;
  }
}

async function removeLlm(provider: string) {
  if (!confirm(`Remove ${provider} configuration?`)) return;
  try {
    await api.llmConfig.delete(provider);
    showToast('Configuration removed', 'success');
    await loadLlmConfigs();
  } catch {
    showToast('Failed to remove', 'error');
  }
}

async function setDefault(provider: string) {
  const config = llmConfigs.value.find(c => c.provider === provider);
  if (!config) return;
  try {
    await api.llmConfig.save({
      provider: config.provider,
      is_default: true,
      is_default_only: true,
    });
    await loadLlmConfigs();
    showToast(`${provider} set as default`, 'success');
  } catch {
    showToast('Failed to update', 'error');
  }
}

async function testSavedLlm(provider: string) {
  llmTestLoading.value = provider;
  llmTestResult.value = null;
  try {
    const { data } = await api.llmConfig.test({ provider });
    if (data.success) {
      llmTestResult.value = { success: true, message: data.message || 'LLM responded successfully.' };
      showToast('LLM test succeeded', 'success');
    } else {
      llmTestResult.value = { success: false, message: data.error || 'LLM test failed.' };
      showToast(data.error || 'LLM test failed', 'error');
    }
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { error?: string } } };
    const msg = ax.response?.data?.error || 'Could not reach the test endpoint.';
    llmTestResult.value = { success: false, message: msg };
    showToast(msg, 'error');
  } finally {
    llmTestLoading.value = null;
  }
}

async function testNewLlm() {
  if (newLlm.value.auth_choice === 'oauth_google') {
    showToast('Save via Google sign-in first, then use Test on the saved row.', 'error');
    return;
  }
  if (newLlm.value.auth_choice === 'api_key' && !newLlm.value.api_key?.trim()) {
    showToast('Enter an API key to test', 'error');
    return;
  }
  if (newLlm.value.auth_choice === 'token' && !newLlm.value.access_token?.trim()) {
    showToast('Enter an access token to test', 'error');
    return;
  }
  syncNewLlmModelToProvider();
  const model = (newLlm.value.model || '').trim();
  if (!model) {
    showToast('Select a model', 'error');
    return;
  }
  llmTestLoading.value = 'new';
  llmTestResult.value = null;
  try {
    const payload: {
      provider: string;
      model: string;
      api_key?: string;
      access_token?: string;
    } = {
      provider: newLlm.value.provider,
      model,
    };
    if (newLlm.value.auth_choice === 'api_key') {
      payload.api_key = newLlm.value.api_key.trim();
    } else {
      payload.access_token = newLlm.value.access_token.trim();
    }
    const { data } = await api.llmConfig.test(payload);
    if (data.success) {
      llmTestResult.value = { success: true, message: data.message || 'LLM responded successfully.' };
      showToast('LLM test succeeded', 'success');
    } else {
      llmTestResult.value = { success: false, message: data.error || 'LLM test failed.' };
      showToast(data.error || 'LLM test failed', 'error');
    }
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { error?: string } } };
    const msg = ax.response?.data?.error || 'Could not run test.';
    llmTestResult.value = { success: false, message: msg };
    showToast(msg, 'error');
  } finally {
    llmTestLoading.value = null;
  }
}

async function registerWebhook() {
  if (!webhookProjectId.value) { showToast('Select a project first', 'error'); return; }
  if (!githubPat.value.configured) {
    webhookRegisterResult.value = {
      success: false,
      message: 'Add a GitHub Personal Access Token first (above in Git Connections section). The token needs admin:repo_hook scope.',
    };
    return;
  }
  webhookRegisterLoading.value = true;
  webhookRegisterResult.value = null;
  try {
    const { data } = await api.webhooks.register(webhookProjectId.value);
    webhookRegisterResult.value = {
      success: data.success,
      message: data.message || (data.success ? 'Webhook registered!' : 'Registration failed'),
    };
    if (data.success) {
      showToast('Webhook registered on GitHub!', 'success');
      fetchWebhookInfo(webhookProjectId.value);
    }
  } catch (e: any) {
    webhookRegisterResult.value = {
      success: false,
      message: e?.response?.data?.message || e?.response?.data?.error || 'Failed to register webhook',
    };
  } finally {
    webhookRegisterLoading.value = false;
  }
}

async function testWebhook() {
  if (!webhookProjectId.value) { showToast('Select a project first', 'error'); return; }
  webhookTestLoading.value = true;
  webhookTestResult.value = null;
  try {
    const { data } = await api.webhooks.test(webhookProjectId.value);
    webhookTestResult.value = { success: true, message: data.message || 'Webhook test successful!' };
  } catch (e: any) {
    webhookTestResult.value = { success: false, message: e?.response?.data?.error || 'Webhook test failed' };
  } finally {
    webhookTestLoading.value = false;
  }
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
  showToast('Copied to clipboard!', 'success');
}

async function saveProfile() {
  loading.value = true;
  try {
    await api.users.updateMe({ username: profile.value.username, email: profile.value.email, telegramChatId: profile.value.telegramChatId || null });
    showToast('Profile updated successfully!', 'success');
  } catch (e: any) {
    showToast(e?.response?.data?.error || 'Failed to update profile', 'error');
  } finally { loading.value = false; }
}

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) { showToast('Passwords do not match', 'error'); return; }
  if (newPassword.value.length < 6) { showToast('Password must be at least 6 characters', 'error'); return; }
  loading.value = true;
  try {
    await api.users.updateMe({ password: newPassword.value });
    showToast('Password changed successfully!', 'success');
    currentPassword.value = ''; newPassword.value = ''; confirmPassword.value = '';
  } catch (e: any) {
    showToast(e?.response?.data?.error || 'Failed to change password', 'error');
  } finally { loading.value = false; }
}

function saveNotifications() { showToast('Notification preferences saved!', 'success'); }

function showToast(msg: string, type: 'success' | 'error') {
  toastMessage.value = msg;
  toastType.value = type;
  setTimeout(() => { toastMessage.value = ''; }, 3000);
}

const tabs = computed(() => {
  // v1 grading-first: LLM Config migrated to the Ops Dashboard (/ops/llm-config,
  // superuser only). Schools shouldn't manage the platform's LLM keys — we do.
  // Existing LLM Config UI code below is preserved (tab just hidden) so the
  // /ops page can lift it over in Phase 3.
  const t = [
    { id: 'profile', label: 'Profile', icon: 'person' },
    { id: 'notifications', label: 'Notifications', icon: 'notifications' },
  ];
  // Student-only "My Cohort" tab (cohort name, teachers, courses). Was a
  // top-level nav item; relocated here Apr 26 2026 because it's reference
  // info, not a daily-flow surface. auth.isStudent gates this so teachers
  // / school admins / ops don't see a confusing self-referential cohort tab.
  if (auth.isStudent) {
    t.push({ id: 'cohort', label: 'My Cohort', icon: 'groups' });
  }
  if (auth.isSuperuser) {
    // Platform ops can still access LLM Config from here if they land on
    // settings directly. Primary entry point is /ops/llm-config.
    t.push({ id: 'llm', label: 'LLM Config', icon: 'smart_toy' });
  }
  if (!auth.isAdmin) {
    t.push({ id: 'git', label: 'Git account', icon: 'link' });
    t.push({ id: 'webhooks', label: 'Webhooks', icon: 'webhook' });
  }
  return t;
});
</script>

<template>
  <AppShell>
    <div class="p-6 max-w-4xl mx-auto">
      <h1 class="text-2xl font-bold text-on-surface mb-2">Settings</h1>
      <p class="text-on-surface-variant mb-6">Manage your account and preferences</p>

      <!-- Tabs -->
      <div class="flex gap-1 mb-8 bg-surface-container-lowest rounded-lg p-1 w-fit">
        <button v-for="tab in tabs" :key="tab.id"
          :class="['flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all',
            activeTab === tab.id ? 'bg-surface-container text-primary shadow-sm' : 'text-outline hover:text-on-surface']"
          @click="activeTab = tab.id">
          <span class="material-symbols-outlined text-sm">{{ tab.icon }}</span>
          {{ tab.label }}
        </button>
      </div>

      <!-- Profile Tab -->
      <template v-if="activeTab === 'profile'">
        <div class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined text-primary">person</span>
            <h2 class="text-lg font-bold text-on-surface">Profile</h2>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Username</label>
              <input v-model="profile.username" type="text"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Email</label>
              <input v-model="profile.email" type="email"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>
          </div>
          <div class="mb-6">
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
              Telegram Chat ID <span class="text-outline/60 normal-case font-normal ml-2">(for notifications)</span>
            </label>
            <input v-model="profile.telegramChatId" type="text" placeholder="e.g., 123456789"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
          </div>
          <button @click="saveProfile" :disabled="loading" class="primary-gradient text-on-primary font-bold py-3 px-6 rounded-lg disabled:opacity-50">Save Profile</button>
        </div>

        <!-- Developer profile (questionnaire + LLM calibration) — developers only -->
        <div v-if="!auth.isAdmin" class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-2">
            <span class="material-symbols-outlined text-primary">psychology</span>
            <h2 class="text-lg font-bold text-on-surface">Developer profile</h2>
          </div>
          <p class="text-sm text-on-surface-variant mb-4 max-w-xl">
            Open your calibration summary (questionnaire + code insights from reviews). You can also revisit the setup wizard to update your answers.
          </p>
          <div class="flex flex-wrap gap-3">
            <router-link
              :to="{ name: 'dev-profile-results' }"
              class="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary/15 text-primary font-semibold text-sm hover:bg-primary/25 transition-colors"
            >
              <span class="material-symbols-outlined text-base">analytics</span>
              View dev profile
            </router-link>
            <router-link
              :to="{ name: 'dev-profile-setup' }"
              class="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-outline-variant/30 text-sm font-medium text-on-surface hover:bg-surface-container transition-colors"
            >
              <span class="material-symbols-outlined text-base">edit_note</span>
              Edit questionnaire
            </router-link>
          </div>
        </div>

        <!-- Password -->
        <div class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined text-primary">lock</span>
            <h2 class="text-lg font-bold text-on-surface">Change Password</h2>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Current Password</label>
              <input v-model="currentPassword" type="password"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">New Password</label>
              <input v-model="newPassword" type="password"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Confirm Password</label>
              <input v-model="confirmPassword" type="password"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>
          </div>
          <button @click="changePassword" :disabled="loading || !newPassword || !confirmPassword"
            class="bg-surface-container-highest text-on-surface font-bold py-3 px-6 rounded-lg hover:bg-outline-variant transition-colors disabled:opacity-50">Change Password</button>
        </div>

        <!-- GitHub token — teachers (Send-to-GitHub comments) + students (batch on private repos) -->
        <div v-if="!auth.isSchoolAdmin" class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-4">
            <span class="material-symbols-outlined text-primary">key</span>
            <h2 class="text-lg font-bold text-on-surface">GitHub personal access token</h2>
          </div>
          <p class="text-sm text-on-surface-variant mb-4">
            Required for teachers to <strong class="text-on-surface">Send graded feedback as PR comments</strong>
            on GitHub (comments post as you). Optional for students for <strong class="text-on-surface">batch
            analysis</strong> on private repos. Stored encrypted (same as other secrets). Use a fine-grained token
            with <strong class="text-on-surface">Contents: Read &amp; Write</strong> and <strong class="text-on-surface">Pull
            requests: Read &amp; Write</strong> on the repos you grade, or a classic token with
            <code class="text-xs">repo</code> scope.
          </p>
          <p v-if="githubPat.configured" class="text-sm text-on-surface mb-3">
            Token on file<span v-if="githubPat.last_four"> (ends with <span class="font-mono">{{ githubPat.last_four }}</span>)</span>.
          </p>
          <p v-else class="text-sm text-outline mb-3">No token saved.</p>
          <div class="space-y-3 max-w-xl">
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
                New token <span class="text-outline/60 normal-case font-normal">(paste to replace)</span>
              </label>
              <input
                v-model="githubPatInput"
                type="password"
                autocomplete="off"
                placeholder="ghp_… or github_pat_…"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 py-3 px-4 text-sm font-mono"
              />
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                :disabled="githubPatSaving || !githubPatInput.trim()"
                class="primary-gradient text-on-primary font-bold py-2.5 px-5 rounded-lg disabled:opacity-50 text-sm"
                @click="saveGithubPat"
              >
                Save token
              </button>
              <button
                v-if="githubPat.configured"
                type="button"
                :disabled="githubPatSaving"
                class="px-4 py-2.5 rounded-lg border border-error/30 text-error text-sm font-medium hover:bg-error/10 disabled:opacity-50"
                @click="removeGithubPat"
              >
                Remove token
              </button>
            </div>
          </div>
        </div>

        <!-- Danger Zone -->
        <div class="glass-panel rounded-xl p-6 border border-error/20">
          <div class="flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined text-error">warning</span>
            <h2 class="text-lg font-bold text-error">Danger Zone</h2>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-on-surface font-medium">Log out of all devices</p>
              <p class="text-xs text-outline">This will invalidate all active sessions</p>
            </div>
            <button class="px-4 py-2 border border-error/30 text-error rounded-lg hover:bg-error/10 transition-colors text-sm font-medium">Log Out Everywhere</button>
          </div>
        </div>
      </template>

      <!-- Notifications Tab -->
      <template v-if="activeTab === 'notifications'">
        <div class="glass-panel rounded-xl p-6">
          <div class="flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined text-primary">notifications</span>
            <h2 class="text-lg font-bold text-on-surface">Notifications</h2>
          </div>
          <div class="space-y-4 mb-6">
            <label v-for="(val, key) in notificationSettings" :key="key" class="flex items-center gap-3 cursor-pointer group">
              <input type="checkbox" v-model="notificationSettings[key]" class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary" />
              <div>
                <span class="text-sm text-on-surface group-hover:text-primary transition-colors">
                  {{ key === 'emailDigest' ? 'Daily Email Digest' : key === 'telegramAlerts' ? 'Telegram Alerts' : key === 'newReviewNotify' ? 'New Review Notifications' : 'PR Created Notifications' }}
                </span>
              </div>
            </label>
          </div>
          <button @click="saveNotifications" class="bg-surface-container-highest text-on-surface font-bold py-3 px-6 rounded-lg hover:bg-outline-variant transition-colors">Save Preferences</button>
        </div>
      </template>

      <!-- My Cohort (student-only) — relocated from top-nav Apr 26 2026 -->
      <template v-if="activeTab === 'cohort' && auth.isStudent">
        <MyCohortWidget />
      </template>

      <!-- Git accounts (Developer) — multiple connections -->
      <template v-if="activeTab === 'git' && !auth.isAdmin">
        <div class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-4">
            <span class="material-symbols-outlined text-primary">link</span>
            <h2 class="text-lg font-bold text-on-surface">Git connections</h2>
          </div>
          <p class="text-sm text-on-surface-variant mb-6">
            Add one row per host identity (e.g. GitHub work + GitLab personal). Use the
            <strong class="text-on-surface">username</strong> that the platform shows when you push, and optionally a
            <strong class="text-on-surface">commit email</strong> if it differs from your ReviewHub email.
            The provider must match each project&apos;s host (GitHub project ↔ GitHub connection).
          </p>

          <div v-if="gitConnectionsList.length" class="space-y-2 mb-8">
            <div v-for="c in gitConnectionsList" :key="c.id"
              class="flex flex-wrap items-center justify-between gap-3 p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10">
              <div>
                <span class="text-sm font-bold text-on-surface capitalize">{{ c.provider }}</span>
                <span class="text-on-surface-variant mx-2">·</span>
                <span class="text-sm font-mono text-on-surface">{{ c.username }}</span>
                <span v-if="c.email" class="block text-xs text-outline mt-1">{{ c.email }}</span>
              </div>
              <button type="button" @click="removeGitConnection(c.id)" :disabled="loading"
                class="text-xs text-error hover:underline">Remove</button>
            </div>
          </div>
          <p v-else class="text-sm text-outline mb-6">No Git connections yet. Add at least one for the host you use.</p>

          <h3 class="text-sm font-bold text-on-surface mb-4">Add connection</h3>
          <div class="space-y-4 max-w-xl">
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Provider</label>
              <select v-model="newGitConn.provider"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-3 px-4">
                <option value="">Select provider…</option>
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
                <option value="bitbucket">Bitbucket</option>
              </select>
            </div>
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Username on that host</label>
              <input v-model="newGitConn.username" type="text" placeholder="e.g. octocat"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 py-3 px-4 text-sm" />
            </div>
            <div>
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
                Commit email <span class="text-outline/60 normal-case font-normal">(optional)</span>
              </label>
              <input v-model="newGitConn.email" type="email" placeholder="git config user.email if different"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 py-3 px-4 text-sm" />
            </div>
            <button type="button" @click="addGitConnection" :disabled="loading"
              class="primary-gradient text-on-primary font-bold py-3 px-6 rounded-lg disabled:opacity-50">
              Add connection
            </button>
          </div>
        </div>
      </template>

      <!-- LLM Config Tab (Admin only) -->
      <template v-if="activeTab === 'llm' && auth.isSuperuser">
        <div class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined text-primary">smart_toy</span>
            <h2 class="text-lg font-bold text-on-surface">LLM Configuration</h2>
          </div>
          <p class="text-sm text-on-surface-variant mb-6">
            Connect each provider with an <strong class="text-on-surface">API key</strong> or an alternative:
            <strong class="text-on-surface">Google</strong> via OAuth,
            <strong class="text-on-surface">Claude</strong> via long-lived token,
            <strong class="text-on-surface">OpenAI</strong> via Codex / ChatGPT Bearer token when your org uses that instead of a platform API key.
            Only one configuration can be the default.
          </p>

          <!-- Existing Configs -->
          <div v-if="llmConfigs.length" class="space-y-3 mb-8">
            <div v-for="config in llmConfigs" :key="config.provider"
              class="flex items-center gap-4 p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10">
              <div class="w-10 h-10 rounded-lg flex items-center justify-center" :class="config.provider === 'openai' ? 'bg-green-500/10' : config.provider === 'anthropic' ? 'bg-orange-500/10' : 'bg-blue-500/10'">
                <span class="material-symbols-outlined" :class="config.provider === 'openai' ? 'text-green-500' : config.provider === 'anthropic' ? 'text-orange-500' : 'text-blue-500'">smart_toy</span>
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-bold text-on-surface">{{ llmProviders.find(p => p.value === config.provider)?.label || config.provider }}</span>
                  <span v-if="config.is_default" class="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">DEFAULT</span>
                </div>
                <span class="text-xs text-outline">
                  {{ config.model }} &middot; {{ authMethodLabel(config.auth_method) }} &middot;
                  {{ credentialPreview(config) }}
                </span>
              </div>
              <button
                type="button"
                :disabled="llmTestLoading !== null"
                @click="testSavedLlm(config.provider)"
                class="text-xs font-semibold text-on-surface-variant hover:text-primary transition-colors flex items-center gap-1 disabled:opacity-50"
              >
                <span
                  v-if="llmTestLoading === config.provider"
                  class="material-symbols-outlined text-sm animate-spin"
                >progress_activity</span>
                <span v-else class="material-symbols-outlined text-sm">science</span>
                Test
              </button>
              <button v-if="!config.is_default" @click="setDefault(config.provider)"
                class="text-xs text-primary hover:underline">Set Default</button>
              <button @click="removeLlm(config.provider)"
                class="text-outline hover:text-error transition-colors">
                <span class="material-symbols-outlined text-sm">delete</span>
              </button>
            </div>
          </div>

          <div
            v-if="llmTestResult"
            class="mb-6 p-4 rounded-xl border"
            :class="llmTestResult.success ? 'bg-primary/10 border-primary/20' : 'bg-error/10 border-error/20'"
          >
            <p class="text-sm" :class="llmTestResult.success ? 'text-on-surface' : 'text-error'">
              {{ llmTestResult.message }}
            </p>
          </div>

          <!-- Add New -->
          <div v-if="availableProviders.length" class="border-t border-outline-variant/10 pt-6">
            <h3 class="text-sm font-bold text-on-surface mb-4">Add Provider</h3>
            <div class="mb-4">
              <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Connection</label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="opt in newLlmAuthChoices"
                  :key="opt.value"
                  type="button"
                  @click="newLlm.auth_choice = opt.value"
                  :class="[
                    'px-3 py-2 rounded-lg text-xs font-bold border transition-colors',
                    newLlm.auth_choice === opt.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-outline-variant/30 text-on-surface-variant hover:border-outline-variant/50',
                  ]"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Provider</label>
                <select v-model="newLlm.provider"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-3 px-4">
                  <option v-for="p in availableProviders" :key="p.value" :value="p.value">{{ p.label }}</option>
                </select>
              </div>
              <div>
                <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Model</label>
                <select
                  v-model="newLlm.model"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-3 px-4"
                >
                  <option v-for="m in newLlmModelOptions" :key="m.value" :value="m.value">
                    {{ m.label }}
                  </option>
                </select>
              </div>
              <div v-if="newLlm.auth_choice === 'api_key'">
                <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">API key</label>
                <input v-model="newLlm.api_key" type="password" placeholder="sk-... or AIza..."
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
                <p v-if="newLlm.provider === 'anthropic'" class="text-[11px] text-outline mt-1.5 leading-relaxed">
                  From <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener noreferrer" class="text-primary underline">Anthropic Console → API keys</a> (starts with sk-ant-). Claude Code login is separate and will not work here.
                </p>
              </div>
              <div v-else-if="newLlm.auth_choice === 'token'" class="md:col-span-2">
                <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
                  Access token (Bearer)
                </label>
                <input v-model="newLlm.access_token" type="password" placeholder="OAuth / platform access token (OpenAI-style)"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
                <p class="text-[11px] text-outline mt-1.5 leading-relaxed">
                  Paste a Bearer token if your org uses OAuth instead of a platform API key (not used for Anthropic).
                </p>
              </div>
              <div v-else class="md:col-span-2 flex flex-col justify-end">
                <p class="text-xs text-on-surface-variant mb-2">
                  You will be redirected to Google to authorize Gemini access. Ensure the server has
                  <code class="text-[10px] bg-surface-container-highest px-1 rounded">GOOGLE_OAUTH_CLIENT_ID</code>
                  and redirect URI configured.
                </p>
                <button
                  type="button"
                  @click="startGoogleLlmOAuth"
                  :disabled="googleOAuthLoading || llmLoading"
                  class="py-3 px-6 rounded-lg border border-outline-variant/40 text-on-surface font-bold text-sm hover:bg-surface-container-high transition-colors disabled:opacity-50 flex items-center gap-2 w-fit"
                >
                  <span v-if="googleOAuthLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                  <span v-else class="material-symbols-outlined text-sm">account_circle</span>
                  Sign in with Google
                </button>
              </div>
            </div>
            <div class="flex flex-wrap gap-3">
              <button
                type="button"
                @click="testNewLlm"
                :disabled="
                  llmLoading ||
                  llmTestLoading !== null ||
                  newLlm.auth_choice === 'oauth_google' ||
                  (newLlm.auth_choice === 'api_key' && !newLlm.api_key) ||
                  (newLlm.auth_choice === 'token' && !newLlm.access_token)
                "
                class="py-3 px-6 rounded-lg border border-outline-variant/40 text-on-surface font-bold text-sm hover:bg-surface-container-high transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <span
                  v-if="llmTestLoading === 'new'"
                  class="material-symbols-outlined text-sm animate-spin"
                >progress_activity</span>
                <span v-else class="material-symbols-outlined text-sm">science</span>
                Test connection
              </button>
              <button
                @click="saveLlmConfig"
                :disabled="
                  llmLoading ||
                  newLlm.auth_choice === 'oauth_google' ||
                  (newLlm.auth_choice === 'api_key' && !newLlm.api_key) ||
                  (newLlm.auth_choice === 'token' && !newLlm.access_token)
                "
                class="primary-gradient text-on-primary font-bold py-3 px-6 rounded-lg disabled:opacity-50 flex items-center gap-2"
              >
                <span v-if="llmLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                Add Provider
              </button>
            </div>
          </div>
          <p v-else class="text-sm text-outline text-center py-4">All available providers have been configured.</p>
        </div>
      </template>

      <!-- Webhooks Tab (Developer only) -->
      <template v-if="activeTab === 'webhooks' && !auth.isAdmin">
        <div class="glass-panel rounded-xl p-6 mb-6">
          <div class="flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined text-primary">webhook</span>
            <h2 class="text-lg font-bold text-on-surface">Webhook Integration</h2>
          </div>
          <p class="text-sm text-on-surface-variant mb-6">Connect your repositories to receive automatic code reviews on every push.</p>

          <!-- Step 1: Select project -->
          <div class="mb-6">
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Select Project</label>
            <select v-model="webhookProjectId"
              class="w-full max-w-md bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-3 px-4">
              <option :value="null" disabled>Select a project...</option>
              <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
            </select>
          </div>

          <!-- Loading state -->
          <div v-if="webhookInfoLoading" class="flex items-center gap-2 text-sm text-on-surface-variant py-8 justify-center">
            <span class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            Loading webhook info...
          </div>

          <!-- No project selected -->
          <div v-else-if="!webhookProjectId" class="text-center py-8 text-on-surface-variant text-sm">
            Select a project above to see its webhook setup details.
          </div>

          <!-- Project webhook info -->
          <template v-else-if="webhookInfo">
            <!-- Webhook URL -->
            <div class="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10 mb-4">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold uppercase tracking-widest text-outline">Payload URL</span>
                <button @click="copyToClipboard(webhookInfo.webhook_url)" class="text-xs text-primary hover:underline flex items-center gap-1">
                  <span class="material-symbols-outlined text-sm">content_copy</span> Copy
                </button>
              </div>
              <code class="text-xs text-on-surface-variant bg-surface-container-highest px-3 py-1.5 rounded block select-all break-all">{{ webhookInfo.webhook_url }}</code>
            </div>

            <!-- Webhook Secret -->
            <div class="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10 mb-6">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-bold uppercase tracking-widest text-outline">Secret</span>
                <div class="flex items-center gap-2">
                  <button @click="webhookSecretVisible = !webhookSecretVisible" class="text-xs text-on-surface-variant hover:text-on-surface flex items-center gap-1">
                    <span class="material-symbols-outlined text-sm">{{ webhookSecretVisible ? 'visibility_off' : 'visibility' }}</span>
                    {{ webhookSecretVisible ? 'Hide' : 'Reveal' }}
                  </button>
                  <button @click="copyToClipboard(webhookInfo.webhook_secret)" class="text-xs text-primary hover:underline flex items-center gap-1">
                    <span class="material-symbols-outlined text-sm">content_copy</span> Copy
                  </button>
                </div>
              </div>
              <code class="text-xs text-on-surface-variant bg-surface-container-highest px-3 py-1.5 rounded block select-all break-all">{{
                webhookSecretVisible ? webhookInfo.webhook_secret : '••••••••••••••••••••••••••••••••'
              }}</code>
            </div>

            <!-- Status badge -->
            <div class="flex items-center gap-2 mb-6">
              <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
                :class="webhookInfo.webhook_active
                  ? 'bg-primary/10 text-primary border border-primary/20'
                  : 'bg-on-surface-variant/10 text-on-surface-variant border border-outline-variant/20'">
                <span class="w-2 h-2 rounded-full" :class="webhookInfo.webhook_active ? 'bg-primary' : 'bg-outline-variant'"></span>
                {{ webhookInfo.webhook_active ? 'Active — receiving webhooks' : 'Not yet active' }}
              </span>
            </div>

            <!-- Quick Setup Guide (provider-specific) -->
            <div class="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant/10 mb-6">
              <h3 class="text-sm font-bold text-on-surface mb-4">Manual Setup</h3>
              <ol class="space-y-3 text-sm text-on-surface-variant list-decimal list-inside">
                <template v-if="webhookInfo.provider === 'github'">
                  <li>Go to your repository <strong class="text-on-surface">Settings → Webhooks → Add webhook</strong></li>
                  <li>Paste the <strong class="text-on-surface">Payload URL</strong> from above</li>
                  <li>Set Content type to <code class="bg-surface-container-highest px-1 rounded">application/json</code></li>
                  <li>Paste the <strong class="text-on-surface">Secret</strong> from above (click Reveal, then Copy)</li>
                  <li>Select <strong class="text-on-surface">"Just the push event"</strong></li>
                  <li>Click <strong class="text-on-surface">"Add webhook"</strong></li>
                </template>
                <template v-else-if="webhookInfo.provider === 'gitlab'">
                  <li>Go to your project <strong class="text-on-surface">Settings → Webhooks</strong></li>
                  <li>Paste the <strong class="text-on-surface">URL</strong> from above</li>
                  <li>Paste the <strong class="text-on-surface">Secret token</strong> from above</li>
                  <li>Check <strong class="text-on-surface">Push events</strong></li>
                  <li>Click <strong class="text-on-surface">"Add webhook"</strong></li>
                </template>
                <template v-else>
                  <li>Go to your repository webhook settings</li>
                  <li>Use the Payload URL and Secret shown above</li>
                  <li>Set the trigger to push events</li>
                </template>
              </ol>
            </div>

            <!-- Auto-register (GitHub only) -->
            <div v-if="webhookInfo.provider === 'github'" class="border-t border-outline-variant/10 pt-6 mb-6">
              <h3 class="text-sm font-bold text-on-surface mb-2">One-Click Setup</h3>
              <p class="text-sm text-on-surface-variant mb-4">
                Skip the manual steps — automatically register the webhook on GitHub.
                <template v-if="!githubPat.configured">
                  <br><span class="text-error">Requires a GitHub Personal Access Token with <code class="bg-surface-container-highest px-1 rounded">admin:repo_hook</code> scope. Add one in the Git Connections section above.</span>
                </template>
              </p>
              <button @click="registerWebhook" :disabled="webhookRegisterLoading || !githubPat.configured"
                class="primary-gradient text-on-primary font-bold py-3 px-6 rounded-lg disabled:opacity-50 flex items-center gap-2">
                <span v-if="webhookRegisterLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                <span class="material-symbols-outlined text-sm">add_link</span>
                Register Webhook on GitHub
              </button>
              <div v-if="webhookRegisterResult" class="mt-4 p-3 rounded-lg" :class="webhookRegisterResult.success ? 'bg-primary/10 border border-primary/20' : 'bg-error/10 border border-error/20'">
                <p class="text-sm" :class="webhookRegisterResult.success ? 'text-primary' : 'text-error'">{{ webhookRegisterResult.message }}</p>
              </div>
            </div>

            <!-- Test webhook -->
            <div class="border-t border-outline-variant/10 pt-6">
              <h3 class="text-sm font-bold text-on-surface mb-4">Test Connection</h3>
              <button @click="testWebhook" :disabled="webhookTestLoading"
                class="primary-gradient text-on-primary font-bold py-3 px-6 rounded-lg disabled:opacity-50 flex items-center gap-2">
                <span v-if="webhookTestLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                <span class="material-symbols-outlined text-sm">lan</span>
                Test Connection
              </button>
              <div v-if="webhookTestResult" class="mt-4 p-3 rounded-lg" :class="webhookTestResult.success ? 'bg-primary/10 border border-primary/20' : 'bg-error/10 border border-error/20'">
                <p class="text-sm" :class="webhookTestResult.success ? 'text-primary' : 'text-error'">{{ webhookTestResult.message }}</p>
              </div>
            </div>
          </template>
        </div>
      </template>
    </div>

    <!-- Toast -->
    <div v-if="toastMessage"
      :class="['fixed bottom-4 right-4 rounded-lg px-4 py-2 text-sm shadow-lg cursor-pointer z-50',
        toastType === 'success' ? 'bg-primary/20 border border-primary/30 text-primary' : 'bg-error/20 border border-error/30 text-error']"
      @click="toastMessage = ''">
      {{ toastMessage }}
    </div>
  </AppShell>
</template>
