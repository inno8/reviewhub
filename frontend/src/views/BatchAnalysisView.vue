<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';
import { useProjectsStore } from '@/stores/projects';

const router = useRouter();
const authStore = useAuthStore();
const projectsStore = useProjectsStore();

interface BatchJob {
  id: number;
  repo_url: string;
  branch: string;
  status: string;
  progress_percent: number;
  total_commits: number;
  processed_commits: number;
  skipped_commits?: number;
  findings_count: number;
  target_github_username?: string;
  project?: number | null;
  error_message?: string;
  created_at: string;
  completed_at: string | null;
}

interface BatchJobDetail extends BatchJob {
  skipped_commits: number;
  resolved_branches?: string[];
  skills_detected?: string[];
  patterns_detected?: unknown[];
}

interface BatchEvalRow {
  id: number;
  commit_sha: string;
  commit_message: string;
  branch: string;
  overall_score: number | null;
  finding_count: number;
  commit_complexity?: string;
  created_at: string;
}

interface DashboardOverview {
  total_evaluations: number;
  total_findings: number;
  avg_score: number;
  fix_rate: number;
  critical_count: number;
  warning_count: number;
}

interface PerformanceInsight {
  commitCount: number;
  findingCount: number;
  fixRate: number;
  averageScore: number;
  strengths: string[];
  growthAreas: string[];
}

interface BatchStats {
  total_jobs: number;
  pending_jobs?: number;
  completed_jobs: number;
  running_jobs: number;
  failed_jobs: number;
  cancelled_jobs?: number;
  total_commits_analyzed: number;
  total_findings: number;
}

interface DeveloperProfile {
  level: string;
  overall_score: number;
  trend: string;
  strengths: number[];
  weaknesses: number[];
  commits_analyzed: number;
  total_findings: number;
}

// State
const jobs = ref<BatchJob[]>([]);
const stats = ref<BatchStats | null>(null);
const profile = ref<DeveloperProfile | null>(null);
const insightOverview = ref<DashboardOverview | null>(null);
const performanceInsight = ref<PerformanceInsight | null>(null);
const insightLoading = ref(false);
const loading = ref(false);  // Start with false
const submitting = ref(false);
const error = ref('');

// Form
const showForm = ref(false);
const showLlmBlockDialog = ref(false);
const llmBlockMessage = ref('');
const checkingOrgLlm = ref(false);
const BRANCH_ALL = '__all__';

const form = ref({
  project: null as number | null,
  repo_url: '',
  branch: '',
  target_github_username: '',
  max_commits: 500,
});

const branchNames = ref<string[]>([]);
const branchesLoading = ref(false);
const branchesError = ref('');

const detailJob = ref<BatchJobDetail | null>(null);
const detailEvaluations = ref<BatchEvalRow[]>([]);
const detailLoading = ref(false);
const rerunSubmitting = ref(false);

function parseApiDetail(data: unknown): string {
  if (data == null) return '';
  if (typeof data === 'string') {
    const t = data.trim();
    return t.length > 0 && t.length < 800 ? t : '';
  }
  if (typeof data !== 'object') return '';
  const d = data as Record<string, unknown>;
  const detail = d.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (typeof first === 'string') return first;
  }
  const nfe = d.non_field_errors;
  if (Array.isArray(nfe) && nfe.length && typeof nfe[0] === 'string') return nfe[0];
  for (const [, v] of Object.entries(d)) {
    if (Array.isArray(v) && v.length && typeof v[0] === 'string') return v[0] as string;
  }
  return '';
}

/** Best-effort message for failed axios calls (DRF + HTML fallbacks). */
function formatAxiosError(e: unknown, fallback: string): string {
  const ax = e as {
    response?: { status?: number; data?: unknown };
    message?: string;
  };
  const parsed = parseApiDetail(ax.response?.data);
  if (parsed) return parsed;
  const st = ax.response?.status;
  if (st === 404) {
    return 'Not found (HTTP 404). The job may have been removed, or the server is missing the batch rerun route.';
  }
  if (st && st >= 500) return `Server error (HTTP ${st}). Check Django logs.`;
  if (st === 403) return 'You are not allowed to rerun this batch (HTTP 403).';
  if (ax.message && ax.message !== 'Network Error') return ax.message;
  if (ax.message === 'Network Error') {
    return 'Network error — check API URL / VPN and that Django is running.';
  }
  return fallback;
}

// Polling
let pollInterval: number | null = null;

// Computed
const hasRunningJobs = computed(() => 
  jobs.value.some(j => ['pending', 'cloning', 'analyzing', 'building_profile'].includes(j.status))
);

/** True while the batch open in the detail drawer is still running (rerun disabled). */
const detailJobIsActive = computed(() => {
  const j = detailJob.value;
  if (!j) return false;
  return ['pending', 'cloning', 'analyzing', 'building_profile'].includes(j.status);
});

const hasCompletedJobs = computed(() => jobs.value.some(j => j.status === 'completed'));

/** Prefer project from most recent completed job (evaluations + skills are per-project). */
const insightProjectId = computed(() => {
  const completed = jobs.value.filter(j => j.status === 'completed');
  for (const j of completed) {
    if (j.project != null && j.project !== undefined) return j.project;
  }
  return undefined;
});

const insightHasData = computed(() => {
  const o = insightOverview.value;
  if (!o) return false;
  return o.total_evaluations > 0 || o.total_findings > 0;
});

/** Projects you can attach batch to: no linked repo yet. */
const batchEligibleProjects = computed(() =>
  projectsStore.projects.filter((p) => !p.repoUrl || !String(p.repoUrl).trim()),
);

let branchDebounce: ReturnType<typeof setTimeout> | null = null;
function scheduleBranchFetch() {
  if (branchDebounce) clearTimeout(branchDebounce);
  branchDebounce = window.setTimeout(() => {
    branchDebounce = null;
    loadBranches();
  }, 450);
}

watch(
  () => [form.value.repo_url, form.value.target_github_username] as const,
  () => {
    branchesError.value = '';
    scheduleBranchFetch();
  },
);

async function loadBranches() {
  const url = form.value.repo_url.trim();
  branchesError.value = '';
  if (!url.startsWith('https://github.com/')) {
    branchNames.value = [];
    return;
  }
  branchesLoading.value = true;
  try {
    const { data } = await api.batch.repoBranches({
      repo_url: url,
      author: form.value.target_github_username.trim() || undefined,
    });
    branchNames.value = data.branches || [];
    const valid = new Set(branchNames.value);
    if (
      form.value.branch &&
      form.value.branch !== BRANCH_ALL &&
      !valid.has(form.value.branch)
    ) {
      form.value.branch = branchNames.value.includes('main')
        ? 'main'
        : branchNames.value[0] || '';
    }
    if (form.value.branch === BRANCH_ALL && branchNames.value.length === 0) {
      form.value.branch = '';
    }
    if (!form.value.branch && branchNames.value.length) {
      form.value.branch = branchNames.value.includes('main')
        ? 'main'
        : branchNames.value[0];
    }
  } catch (e: unknown) {
    branchNames.value = [];
    const ax = e as { response?: { data?: unknown } };
    branchesError.value =
      parseApiDetail(ax.response?.data) || 'Could not load branches from GitHub.';
  } finally {
    branchesLoading.value = false;
  }
}

// Status styling
const statusColors: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  cloning: 'bg-blue-500/20 text-blue-400',
  analyzing: 'bg-blue-500/20 text-blue-400',
  building_profile: 'bg-purple-500/20 text-purple-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  cancelled: 'bg-gray-500/20 text-gray-400',
};

const statusLabels: Record<string, string> = {
  pending: 'Pending',
  cloning: 'Cloning Repository',
  analyzing: 'Analyzing Commits',
  building_profile: 'Building Profile',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const levelColors: Record<string, string> = {
  beginner: 'text-gray-400',
  junior: 'text-blue-400',
  intermediate: 'text-green-400',
  senior: 'text-purple-400',
  expert: 'text-yellow-400',
};

const trendIcons: Record<string, string> = {
  improving: 'trending_up',
  stable: 'trending_flat',
  declining: 'trending_down',
  new: 'fiber_new',
};

// Methods
async function loadData() {
  console.log('[Batch] loadData started, loading=', loading.value);
  loading.value = true;
  error.value = '';
  
  try {
    console.log('[Batch] Fetching jobs and stats...');
    const [jobsRes, statsRes] = await Promise.all([
      api.batch.listJobs(),
      api.batch.getStats(),
    ]);
    console.log('[Batch] Got jobs:', jobsRes.data);
    console.log('[Batch] Got stats:', statsRes.data);
    // Handle paginated response from Django REST Framework
    jobs.value = jobsRes.data?.results || jobsRes.data || [];
    stats.value = statsRes.data;
    
    try {
      const profileRes = await api.batch.getProfile();
      const raw = profileRes.data;
      profile.value =
        raw && typeof raw === 'object' && 'level' in raw ? (raw as DeveloperProfile) : null;
    } catch {
      profile.value = null;
    }
  } catch (e: any) {
    console.error('[Batch] Failed to load batch data:', e);
    error.value = e.response?.data?.detail || 'Failed to load data';
    jobs.value = [];
    stats.value = null;
  }
  
  console.log('[Batch] loadData finished, setting loading=false');
  loading.value = false;
  await loadInsightSummary();
}

async function loadInsightSummary() {
  const uid = authStore.user?.id;
  if (!uid || !hasCompletedJobs.value) {
    insightOverview.value = null;
    performanceInsight.value = null;
    return;
  }
  insightLoading.value = true;
  insightOverview.value = null;
  performanceInsight.value = null;
  const pid = insightProjectId.value;
  try {
    const { data } = await api.dashboard.overview(pid);
    insightOverview.value = data as DashboardOverview;
  } catch (e) {
    console.error('[Batch] dashboard overview failed:', e);
  }
  try {
    const { data } = await api.performance.get(uid, pid != null ? { projectId: pid } : {});
    performanceInsight.value = data as PerformanceInsight;
  } catch (e) {
    console.error('[Batch] performance insight failed:', e);
  }
  insightLoading.value = false;
}

function goSkills() {
  const pid = insightProjectId.value;
  if (pid != null) projectsStore.setSelectedProject(pid);
  const q: Record<string, string> = {};
  if (authStore.user?.id != null) q.user = String(authStore.user.id);
  router.push({ path: '/skills', query: Object.keys(q).length ? q : {} });
}

function goInsights() {
  const pid = insightProjectId.value;
  if (pid != null) projectsStore.setSelectedProject(pid);
  const q: Record<string, string> = {};
  if (authStore.user?.id != null) q.user = String(authStore.user.id);
  router.push({ path: '/insights', query: Object.keys(q).length ? q : {} });
}

async function openBatchForm() {
  checkingOrgLlm.value = true;
  error.value = '';
  try {
    await projectsStore.fetchProjects();
    const { data } = await api.batch.checkOrgLlm();
    if (!data.ready) {
      llmBlockMessage.value =
        data.detail ||
        'An organisation administrator must configure an LLM with API key and model before batch analysis can run.';
      showLlmBlockDialog.value = true;
      return;
    }
    showForm.value = true;
  } catch (e: unknown) {
    const ax = e as { response?: { data?: unknown } };
    error.value = parseApiDetail(ax.response?.data) || 'Could not verify organisation LLM configuration.';
  } finally {
    checkingOrgLlm.value = false;
  }
}

async function submitJob() {
  if (form.value.project == null) {
    error.value = 'Select a project without a linked repository';
    return;
  }
  if (!form.value.repo_url) {
    error.value = 'Repository URL is required';
    return;
  }
  if (!form.value.branch) {
    error.value = 'Select a branch or “All branches”';
    return;
  }

  submitting.value = true;
  error.value = '';

  try {
    await api.batch.createJob({
      project: form.value.project,
      repo_url: form.value.repo_url.trim(),
      branch: form.value.branch,
      target_github_username: form.value.target_github_username.trim() || undefined,
      max_commits: form.value.max_commits,
    });
    showForm.value = false;
    form.value = {
      project: null,
      repo_url: '',
      branch: '',
      target_github_username: '',
      max_commits: 500,
    };
    branchNames.value = [];
    await loadData();
  } catch (e: unknown) {
    const ax = e as { response?: { data?: Record<string, unknown> } };
    const data = ax.response?.data;
    const code = data?.code;
    if (code === 'org_llm_not_configured') {
      llmBlockMessage.value =
        parseApiDetail(data) ||
        'An organisation administrator must configure an LLM with API key and model.';
      showLlmBlockDialog.value = true;
      showForm.value = false;
    } else {
      error.value =
        parseApiDetail(data) ||
        (Array.isArray(data?.repo_url) ? String(data.repo_url[0]) : '') ||
        'Failed to create job';
    }
  } finally {
    submitting.value = false;
  }
}

async function cancelJob(jobId: number) {
  try {
    await api.batch.cancelJob(jobId);
    await loadData();
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to cancel job';
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

function shortSha(sha: string): string {
  return sha?.length > 10 ? sha.slice(0, 7) : sha;
}

async function openJobDetail(job: BatchJob) {
  detailJob.value = null;
  detailEvaluations.value = [];
  detailLoading.value = true;
  try {
    const [jobRes, evRes] = await Promise.all([
      api.batch.getJob(job.id),
      api.batch.getJobEvaluations(job.id),
    ]);
    detailJob.value = jobRes.data as BatchJobDetail;
    const raw = evRes.data;
    detailEvaluations.value = (raw?.results ?? raw ?? []) as BatchEvalRow[];
  } catch (err) {
    console.error('[Batch] job detail failed:', err);
  } finally {
    detailLoading.value = false;
  }
}

async function rerunSelectedBatch() {
  if (!detailJob.value || detailJobIsActive.value) return;
  const jobId = detailJob.value.id;
  if (jobId == null || !Number.isFinite(Number(jobId))) {
    error.value = 'Invalid batch job id.';
    return;
  }
  rerunSubmitting.value = true;
  error.value = '';
  try {
    const { data: llmOk } = await api.batch.checkOrgLlm();
    if (!llmOk.ready) {
      llmBlockMessage.value =
        llmOk.detail ||
        'An organisation administrator must configure an LLM with API key and model before batch analysis can run.';
      showLlmBlockDialog.value = true;
      return;
    }
    const { data: newJob } = await api.batch.rerunJob(Number(jobId));
    closeJobDetail();
    await loadData();
    if (newJob && typeof newJob === 'object' && 'id' in newJob) {
      await openJobDetail(newJob as BatchJob);
    }
  } catch (e: unknown) {
    console.error('[Batch] rerun failed', e);
    const ax = e as { response?: { data?: Record<string, unknown>; status?: number } };
    const data = ax.response?.data;
    const code = data?.code;
    if (code === 'org_llm_not_configured') {
      llmBlockMessage.value =
        parseApiDetail(data) ||
        'An organisation administrator must configure an LLM with API key and model.';
      showLlmBlockDialog.value = true;
    } else {
      error.value = formatAxiosError(e, 'Failed to rerun batch');
    }
  } finally {
    rerunSubmitting.value = false;
  }
}

function closeJobDetail() {
  detailJob.value = null;
  detailEvaluations.value = [];
}

function extractRepoName(url: string): string {
  const parts = url.replace(/\.git$/, '').split('/');
  return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
}

// Lifecycle
onMounted(() => {
  projectsStore.fetchProjects().catch(() => {});
  loadData();
  // Poll for updates if there are running jobs
  pollInterval = window.setInterval(() => {
    if (hasRunningJobs.value) {
      loadData();
    }
  }, 5000);
});

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});
</script>

<template>
  <AppShell>
    <div class="flex-1 bg-surface p-6">
    <div class="max-w-6xl mx-auto space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-on-surface">Batch Analysis</h1>
          <p class="text-on-surface-variant text-sm mt-1">
            Analyze repository history to build your developer profile
          </p>
        </div>
        <button
          type="button"
          :disabled="checkingOrgLlm"
          @click="openBatchForm"
          class="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          <span
            v-if="checkingOrgLlm"
            class="material-symbols-outlined text-xl animate-spin"
          >progress_activity</span>
          <span v-else class="material-symbols-outlined text-xl">add</span>
          {{ checkingOrgLlm ? 'Checking…' : 'New Analysis' }}
        </button>
      </div>

      <!-- Error -->
      <div v-if="error" class="p-4 bg-error/10 border border-error/20 rounded-lg">
        <p class="text-error">{{ error }}</p>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-12">
        <span class="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
      </div>

      <template v-else>
        <!-- Stats Cards -->
        <div
          v-if="(stats?.pending_jobs ?? 0) > 0 && (stats?.running_jobs ?? 0) === 0"
          class="mb-4 p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-sm text-on-surface-variant"
        >
          <span class="font-bold text-yellow-500">Pending job:</span>
          the AI engine may be misconfigured, unreachable, or still starting. Ensure it runs with
          <code class="text-xs bg-surface-container-highest px-1 rounded">BACKEND_API_URL</code>
          pointing at Django (e.g. <code class="text-xs">http://localhost:8000</code>) and restart it after fixing.
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div class="bg-surface-container rounded-xl p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-primary/10 rounded-lg">
                <span class="material-symbols-outlined text-primary">assignment</span>
              </div>
              <div>
                <p class="text-2xl font-bold text-on-surface">{{ stats?.total_jobs || 0 }}</p>
                <p class="text-xs text-on-surface-variant">Total Jobs</p>
              </div>
            </div>
          </div>

          <div class="bg-surface-container rounded-xl p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-outline/10 rounded-lg">
                <span class="material-symbols-outlined text-outline">schedule</span>
              </div>
              <div>
                <p class="text-2xl font-bold text-on-surface">{{ stats?.pending_jobs ?? 0 }}</p>
                <p class="text-xs text-on-surface-variant">Pending</p>
              </div>
            </div>
          </div>
          
          <div class="bg-surface-container rounded-xl p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-green-500/10 rounded-lg">
                <span class="material-symbols-outlined text-green-400">check_circle</span>
              </div>
              <div>
                <p class="text-2xl font-bold text-on-surface">{{ stats?.completed_jobs || 0 }}</p>
                <p class="text-xs text-on-surface-variant">Completed</p>
              </div>
            </div>
          </div>
          
          <div class="bg-surface-container rounded-xl p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-blue-500/10 rounded-lg">
                <span class="material-symbols-outlined text-blue-400">commit</span>
              </div>
              <div>
                <p class="text-2xl font-bold text-on-surface">{{ stats?.total_commits_analyzed || 0 }}</p>
                <p class="text-xs text-on-surface-variant">Commits Analyzed</p>
              </div>
            </div>
          </div>
          
          <div class="bg-surface-container rounded-xl p-4">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-yellow-500/10 rounded-lg">
                <span class="material-symbols-outlined text-yellow-400">bug_report</span>
              </div>
              <div>
                <p class="text-2xl font-bold text-on-surface">{{ stats?.total_findings || 0 }}</p>
                <p class="text-xs text-on-surface-variant">Findings</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Skills & insights from evaluations (shown after batch completes) -->
        <div
          v-if="hasCompletedJobs"
          class="bg-surface-container rounded-xl p-6 border border-outline-variant/10"
        >
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-secondary/10 rounded-lg">
                <span class="material-symbols-outlined text-secondary text-2xl">analytics</span>
              </div>
              <div>
                <h2 class="text-lg font-bold text-on-surface">Skills &amp; insights</h2>
                <p class="text-xs text-on-surface-variant">
                  Summary from your evaluations
                  <template v-if="insightProjectId != null"> (linked project)</template>
                </p>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                class="px-3 py-1.5 text-sm rounded-lg bg-primary/15 text-primary font-medium hover:bg-primary/25 transition-colors"
                @click="goSkills"
              >
                Open skills
              </button>
              <button
                type="button"
                class="px-3 py-1.5 text-sm rounded-lg bg-surface-container-high text-on-surface font-medium hover:bg-surface-container-highest transition-colors border border-outline-variant/20"
                @click="goInsights"
              >
                Open insights
              </button>
            </div>
          </div>

          <div v-if="insightLoading" class="flex items-center justify-center py-10">
            <span class="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
          </div>

          <template v-else-if="insightHasData && insightOverview">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div class="rounded-lg bg-surface-container-high/80 p-3 text-center">
                <p class="text-xl font-bold text-on-surface">{{ insightOverview.total_evaluations }}</p>
                <p class="text-[10px] uppercase tracking-wider text-on-surface-variant">Evaluations</p>
              </div>
              <div class="rounded-lg bg-surface-container-high/80 p-3 text-center">
                <p class="text-xl font-bold text-on-surface">{{ Number(insightOverview.avg_score).toFixed(1) }}</p>
                <p class="text-[10px] uppercase tracking-wider text-on-surface-variant">Avg score</p>
              </div>
              <div class="rounded-lg bg-surface-container-high/80 p-3 text-center">
                <p class="text-xl font-bold text-on-surface">{{ insightOverview.total_findings }}</p>
                <p class="text-[10px] uppercase tracking-wider text-on-surface-variant">Findings</p>
              </div>
              <div class="rounded-lg bg-surface-container-high/80 p-3 text-center">
                <p class="text-xl font-bold text-on-surface">{{ Number(insightOverview.fix_rate).toFixed(1) }}%</p>
                <p class="text-[10px] uppercase tracking-wider text-on-surface-variant">Fix rate</p>
              </div>
            </div>
            <div v-if="performanceInsight" class="grid md:grid-cols-2 gap-4 text-sm">
              <div v-if="performanceInsight.strengths?.length" class="rounded-lg bg-green-500/5 border border-green-500/15 p-4">
                <p class="text-xs font-bold uppercase tracking-wider text-green-500 mb-2">Strengths</p>
                <ul class="list-disc list-inside text-on-surface-variant space-y-1">
                  <li v-for="s in performanceInsight.strengths" :key="s">{{ s }}</li>
                </ul>
              </div>
              <div v-if="performanceInsight.growthAreas?.length" class="rounded-lg bg-amber-500/5 border border-amber-500/15 p-4">
                <p class="text-xs font-bold uppercase tracking-wider text-amber-600 mb-2">Growth areas</p>
                <ul class="list-disc list-inside text-on-surface-variant space-y-1">
                  <li v-for="g in performanceInsight.growthAreas" :key="g">{{ g }}</li>
                </ul>
              </div>
            </div>
            <p
              v-if="performanceInsight && !performanceInsight.strengths?.length && !performanceInsight.growthAreas?.length"
              class="text-sm text-on-surface-variant"
            >
              Category strengths and growth areas appear once skill scores are populated for this scope.
            </p>
          </template>

          <p v-else class="text-sm text-on-surface-variant py-2">
            Batch finished successfully. If you still see no numbers here, evaluations may still be syncing, or commits were filtered out.
            Use <strong class="text-on-surface">Open skills</strong> / <strong class="text-on-surface">Open insights</strong> for the full views.
          </p>
        </div>

        <!-- Developer Profile Card -->
        <div v-if="profile" class="bg-surface-container rounded-xl p-6">
          <div class="flex items-center gap-4 mb-4">
            <div class="p-3 bg-primary/10 rounded-full">
              <span class="material-symbols-outlined text-3xl text-primary">person</span>
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <h2 class="text-xl font-bold text-on-surface">Developer Profile</h2>
                <span :class="levelColors[profile.level]" class="text-sm font-medium capitalize">
                  {{ profile.level }}
                </span>
              </div>
              <div class="flex items-center gap-2 mt-1">
                <span class="material-symbols-outlined text-lg" :class="{
                  'text-green-400': profile.trend === 'improving',
                  'text-gray-400': profile.trend === 'stable',
                  'text-red-400': profile.trend === 'declining',
                  'text-blue-400': profile.trend === 'new',
                }">{{ trendIcons[profile.trend] }}</span>
                <span class="text-sm text-on-surface-variant capitalize">{{ profile.trend }}</span>
              </div>
            </div>
            <div class="text-right">
              <p class="text-3xl font-bold text-primary">{{ profile.overall_score.toFixed(1) }}</p>
              <p class="text-xs text-on-surface-variant">Overall Score</p>
            </div>
          </div>
          
          <!-- Progress Bar -->
          <div class="mb-4">
            <div class="h-2 bg-surface-container-highest rounded-full overflow-hidden">
              <div 
                class="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 transition-all"
                :style="{ width: `${profile.overall_score}%` }"
              ></div>
            </div>
          </div>
          
          <div class="grid grid-cols-3 gap-4 text-center">
            <div>
              <p class="text-lg font-bold text-on-surface">{{ profile.commits_analyzed }}</p>
              <p class="text-xs text-on-surface-variant">Commits</p>
            </div>
            <div>
              <p class="text-lg font-bold text-on-surface">{{ profile.total_findings }}</p>
              <p class="text-xs text-on-surface-variant">Findings</p>
            </div>
            <div>
              <p class="text-lg font-bold text-on-surface">{{ profile.strengths?.length || 0 }}</p>
              <p class="text-xs text-on-surface-variant">Strengths</p>
            </div>
          </div>
        </div>

        <!-- No Profile -->
        <div v-else-if="!hasCompletedJobs" class="bg-surface-container rounded-xl p-8 text-center">
          <span class="material-symbols-outlined text-5xl text-on-surface-variant mb-3">psychology</span>
          <h3 class="text-lg font-medium text-on-surface mb-2">No Developer Profile Yet</h3>
          <p class="text-sm text-on-surface-variant mb-4">
            Run a batch analysis on your repository to build your profile
          </p>
          <button
            type="button"
            :disabled="checkingOrgLlm"
            @click="openBatchForm"
            class="px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {{ checkingOrgLlm ? 'Checking…' : 'Start Analysis' }}
          </button>
        </div>

        <!-- Jobs List -->
        <div class="bg-surface-container rounded-xl overflow-hidden">
          <div class="p-4 border-b border-outline-variant/10">
            <h2 class="font-semibold text-on-surface">Analysis Jobs</h2>
          </div>
          
          <div v-if="jobs.length === 0" class="p-8 text-center">
            <span class="material-symbols-outlined text-4xl text-on-surface-variant mb-2">inbox</span>
            <p class="text-on-surface-variant">No analysis jobs yet</p>
          </div>
          
          <div v-else class="divide-y divide-outline-variant/10">
            <div
              v-for="job in jobs"
              :key="job.id"
              class="p-4 hover:bg-surface-container-high/50 transition-colors cursor-pointer"
              role="button"
              tabindex="0"
              @click="openJobDetail(job)"
              @keydown.enter.prevent="openJobDetail(job)"
            >
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-3">
                  <span class="material-symbols-outlined text-on-surface-variant">folder_code</span>
                  <div>
                    <p class="font-medium text-on-surface">{{ extractRepoName(job.repo_url) }}</p>
                    <p class="text-xs text-on-surface-variant">{{ job.branch }} · {{ formatDate(job.created_at) }}</p>
                  </div>
                </div>
                <div class="flex items-center gap-3">
                  <span :class="statusColors[job.status]" class="px-2 py-1 rounded-full text-xs font-medium">
                    {{ statusLabels[job.status] }}
                  </span>
                  <span class="text-[10px] text-outline uppercase hidden sm:inline">View details</span>
                  <button
                    v-if="['pending', 'cloning', 'analyzing', 'building_profile'].includes(job.status)"
                    type="button"
                    @click.stop="cancelJob(job.id)"
                    class="p-1 text-on-surface-variant hover:text-error transition-colors"
                    title="Cancel"
                  >
                    <span class="material-symbols-outlined text-lg">close</span>
                  </button>
                </div>
              </div>
              
              <!-- Progress Bar for Running Jobs -->
              <div v-if="['cloning', 'analyzing', 'building_profile'].includes(job.status)" class="mt-3">
                <div class="flex items-center justify-between text-xs text-on-surface-variant mb-1">
                  <span>{{ job.processed_commits }} / {{ job.total_commits || '?' }} commits</span>
                  <span>{{ job.progress_percent }}%</span>
                </div>
                <div class="h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                  <div 
                    class="h-full bg-primary transition-all"
                    :style="{ width: `${job.progress_percent}%` }"
                  ></div>
                </div>
              </div>
              
              <!-- Results for Completed Jobs -->
              <div v-if="job.status === 'completed'" class="mt-3 flex items-center gap-4 text-sm text-on-surface-variant">
                <span class="flex items-center gap-1">
                  <span class="material-symbols-outlined text-base">commit</span>
                  {{ job.processed_commits }} commits
                </span>
                <span class="flex items-center gap-1">
                  <span class="material-symbols-outlined text-base">bug_report</span>
                  {{ job.findings_count }} findings
                </span>
              </div>
              
              <!-- Error for Failed Jobs -->
              <div v-if="job.status === 'failed' && job.error_message" class="mt-3">
                <p class="text-xs text-error">{{ job.error_message }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Organisation LLM not configured -->
      <Teleport to="body">
        <div
          v-if="showLlmBlockDialog"
          class="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="llm-block-title"
        >
          <div class="bg-surface-container rounded-xl w-full max-w-md shadow-2xl border border-error/20">
            <div class="p-4 border-b border-outline-variant/10 flex items-start gap-3">
              <span class="material-symbols-outlined text-error text-3xl shrink-0">error</span>
              <div>
                <h2 id="llm-block-title" class="font-bold text-on-surface text-lg">
                  Organisation LLM not configured
                </h2>
                <p class="text-sm text-on-surface-variant mt-2 leading-relaxed">
                  {{ llmBlockMessage }}
                </p>
              </div>
            </div>
            <div class="p-4 flex justify-end">
              <button
                type="button"
                class="px-4 py-2 rounded-lg bg-primary text-on-primary font-semibold text-sm hover:bg-primary/90"
                @click="showLlmBlockDialog = false"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- New Job Modal -->
      <Teleport to="body">
        <div v-if="showForm" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div class="bg-surface-container rounded-xl w-full max-w-md shadow-2xl">
            <div class="flex items-center justify-between p-4 border-b border-outline-variant/10">
              <h2 class="font-semibold text-on-surface">New Batch Analysis</h2>
              <button @click="showForm = false" class="text-on-surface-variant hover:text-on-surface">
                <span class="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <form @submit.prevent="submitJob" class="p-4 space-y-4">
              <p
                v-if="batchEligibleProjects.length === 0"
                class="text-sm text-amber-600 bg-amber-500/10 border border-amber-500/20 rounded-lg p-3"
              >
                You need a project you belong to with no repository linked yet. Create a project (or unlink a repo), then refresh.
              </p>

              <!-- Project -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Project *
                </label>
                <select
                  v-model.number="form.project"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary"
                  required
                >
                  <option disabled :value="null">Select project (no repo linked)</option>
                  <option v-for="p in batchEligibleProjects" :key="p.id" :value="p.id">
                    {{ p.displayName }}
                  </option>
                </select>
                <p class="text-[11px] text-on-surface-variant mt-1">
                  The GitHub URL you enter will be saved on this project when the batch starts.
                </p>
              </div>

              <!-- Repo URL -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Repository URL *
                </label>
                <input
                  v-model="form.repo_url"
                  type="url"
                  placeholder="https://github.com/owner/repo"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary"
                  required
                />
              </div>

              <!-- GitHub author username (before branch list; affects API branch filter) -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Author Git username
                </label>
                <input
                  v-model="form.target_github_username"
                  type="text"
                  autocomplete="off"
                  placeholder="Optional — narrows branch list and commit history"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary"
                />
                <p class="text-[11px] text-on-surface-variant mt-1">
                  If set, only branches with commits by this GitHub user are listed. Also passed to
                  <code class="text-xs">git log --author</code> during analysis.
                </p>
              </div>

              <!-- Branch -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Branch *
                </label>
                <select
                  v-model="form.branch"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary disabled:opacity-50"
                  :disabled="branchesLoading || branchNames.length === 0"
                  required
                >
                  <option value="" disabled>
                    {{
                      branchesLoading
                        ? 'Loading branches…'
                        : branchNames.length
                          ? 'Choose a branch'
                          : 'Enter a valid GitHub repo URL'
                    }}
                  </option>
                  <option v-if="branchNames.length > 0" :value="BRANCH_ALL">
                    All branches ({{ branchNames.length }})
                  </option>
                  <option v-for="b in branchNames" :key="b" :value="b">{{ b }}</option>
                </select>
                <p v-if="branchesError" class="text-xs text-error mt-1.5">{{ branchesError }}</p>
                <button
                  type="button"
                  class="text-xs text-primary font-medium mt-2 hover:underline"
                  @click="loadBranches"
                >
                  Refresh branches
                </button>
              </div>
              
              <!-- Max Commits -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Max Commits
                </label>
                <input
                  v-model.number="form.max_commits"
                  type="number"
                  min="10"
                  max="1000"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary"
                />
              </div>
              
              <!-- Submit -->
              <div class="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  @click="showForm = false"
                  class="px-4 py-2 text-on-surface-variant hover:text-on-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  :disabled="submitting || !form.branch || branchesLoading"
                  class="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  <span v-if="submitting" class="material-symbols-outlined animate-spin text-lg">progress_activity</span>
                  <span>{{ submitting ? 'Starting...' : 'Start Analysis' }}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </Teleport>

      <!-- Job detail / commit history -->
      <Teleport to="body">
        <div
          v-if="detailJob"
          class="fixed inset-0 z-[55] flex justify-end bg-black/40"
          role="presentation"
          @click.self="closeJobDetail"
        >
          <div
            class="bg-surface-container w-full max-w-lg h-full shadow-2xl border-l border-outline-variant/10 flex flex-col overflow-hidden"
            role="dialog"
            aria-modal="true"
            aria-labelledby="batch-detail-title"
            @click.stop
          >
            <div class="p-4 border-b border-outline-variant/10 flex items-start justify-between gap-3 shrink-0">
              <div class="min-w-0">
                <h2 id="batch-detail-title" class="font-bold text-on-surface text-lg truncate">
                  Batch #{{ detailJob.id }}
                </h2>
                <p class="text-xs text-on-surface-variant truncate mt-0.5">
                  {{ extractRepoName(detailJob.repo_url) }} · {{ detailJob.branch }}
                </p>
                <span :class="statusColors[detailJob.status]" class="inline-block mt-2 px-2 py-0.5 rounded-full text-xs font-medium">
                  {{ statusLabels[detailJob.status] }}
                </span>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-primary border border-primary/40 hover:bg-primary/10 disabled:opacity-45 disabled:cursor-not-allowed transition-colors"
                  :disabled="detailLoading || detailJobIsActive || rerunSubmitting"
                  title="Start a new run with the same repository, branches, and filters"
                  @click="rerunSelectedBatch"
                >
                  <span
                    class="material-symbols-outlined text-lg"
                    :class="{ 'animate-spin': rerunSubmitting }"
                  >
                    {{ rerunSubmitting ? 'progress_activity' : 'replay' }}
                  </span>
                  <span class="hidden sm:inline">{{ rerunSubmitting ? 'Starting…' : 'Run again' }}</span>
                </button>
                <button
                  type="button"
                  class="p-2 rounded-lg text-on-surface-variant hover:bg-surface-container-high"
                  aria-label="Close"
                  @click="closeJobDetail"
                >
                  <span class="material-symbols-outlined">close</span>
                </button>
              </div>
            </div>

            <div class="flex-1 overflow-y-auto p-4 space-y-4 text-sm">
              <div v-if="detailLoading" class="flex justify-center py-12">
                <span class="material-symbols-outlined animate-spin text-3xl text-primary">progress_activity</span>
              </div>
              <template v-else>
                <div class="grid grid-cols-2 gap-2">
                  <div class="rounded-lg bg-surface-container-high/60 p-3">
                    <p class="text-[10px] uppercase text-on-surface-variant">Commits (log)</p>
                    <p class="text-lg font-bold text-on-surface">{{ detailJob.total_commits }}</p>
                  </div>
                  <div class="rounded-lg bg-surface-container-high/60 p-3">
                    <p class="text-[10px] uppercase text-on-surface-variant">Processed</p>
                    <p class="text-lg font-bold text-on-surface">{{ detailJob.processed_commits }}</p>
                  </div>
                  <div class="rounded-lg bg-surface-container-high/60 p-3">
                    <p class="text-[10px] uppercase text-on-surface-variant">Skipped</p>
                    <p class="text-lg font-bold text-on-surface">{{ detailJob.skipped_commits ?? '—' }}</p>
                  </div>
                  <div class="rounded-lg bg-surface-container-high/60 p-3">
                    <p class="text-[10px] uppercase text-on-surface-variant">Findings</p>
                    <p class="text-lg font-bold text-on-surface">{{ detailJob.findings_count }}</p>
                  </div>
                </div>

                <div v-if="detailJob.target_github_username" class="text-xs text-on-surface-variant">
                  <span class="font-semibold text-on-surface">Author filter:</span>
                  {{ detailJob.target_github_username }}
                </div>
                <div v-if="detailJob.resolved_branches?.length" class="text-xs text-on-surface-variant">
                  <span class="font-semibold text-on-surface">Branches analyzed:</span>
                  {{ detailJob.resolved_branches.join(', ') }}
                </div>
                <div
                  v-else-if="detailJob.branch && detailJob.branch !== BRANCH_ALL"
                  class="text-xs text-on-surface-variant"
                >
                  <span class="font-semibold text-on-surface">Branch:</span>
                  {{ detailJob.branch }}
                </div>
                <div v-if="detailJob.project" class="text-xs text-on-surface-variant">
                  <span class="font-semibold text-on-surface">Project ID:</span>
                  {{ detailJob.project }}
                </div>
                <div v-if="detailJob.error_message" class="text-xs text-error bg-error/10 border border-error/20 rounded-lg p-2">
                  {{ detailJob.error_message }}
                </div>

                <div>
                  <h3 class="text-xs font-bold uppercase tracking-wider text-outline mb-2">
                    Evaluations (commit history)
                  </h3>
                  <div v-if="detailEvaluations.length === 0" class="text-on-surface-variant text-xs py-4 text-center">
                    No evaluations stored for this batch yet.
                  </div>
                  <div v-else class="border border-outline-variant/10 rounded-lg overflow-hidden">
                    <table class="w-full text-left text-xs">
                      <thead class="bg-surface-container-high/80 text-on-surface-variant uppercase tracking-wide">
                        <tr>
                          <th class="p-2 font-semibold">Commit</th>
                          <th class="p-2 font-semibold">Score</th>
                          <th class="p-2 font-semibold">Findings</th>
                          <th class="p-2 font-semibold">Tier</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-outline-variant/10">
                        <tr
                          v-for="row in detailEvaluations"
                          :key="row.id"
                          class="hover:bg-surface-container-high/40"
                        >
                          <td class="p-2 align-top">
                            <span class="font-mono text-primary">{{ shortSha(row.commit_sha) }}</span>
                            <p class="text-on-surface-variant line-clamp-2 mt-0.5">{{ row.commit_message }}</p>
                          </td>
                          <td class="p-2 align-top whitespace-nowrap">
                            {{ row.overall_score != null ? Number(row.overall_score).toFixed(1) : '—' }}
                          </td>
                          <td class="p-2 align-top">{{ row.finding_count }}</td>
                          <td class="p-2 align-top text-on-surface-variant">
                            {{ row.commit_complexity || '—' }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </Teleport>
    </div>
    </div>
  </AppShell>
</template>
