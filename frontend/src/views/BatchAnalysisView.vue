<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { api } from '@/composables/useApi';

interface BatchJob {
  id: number;
  repo_url: string;
  branch: string;
  status: string;
  progress_percent: number;
  total_commits: number;
  processed_commits: number;
  findings_count: number;
  error_message: string;
  created_at: string;
  completed_at: string | null;
}

interface BatchStats {
  total_jobs: number;
  completed_jobs: number;
  running_jobs: number;
  failed_jobs: number;
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
const loading = ref(false);  // Start with false
const submitting = ref(false);
const error = ref('');

// Form
const showForm = ref(false);
const form = ref({
  repo_url: '',
  branch: 'main',
  target_email: '',
  max_commits: 500,
});

// Polling
let pollInterval: number | null = null;

// Computed
const hasRunningJobs = computed(() => 
  jobs.value.some(j => ['pending', 'cloning', 'analyzing', 'building_profile'].includes(j.status))
);

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
    
    // Try to load profile (404 is expected if none exists)
    try {
      const profileRes = await api.batch.getProfile();
      profile.value = profileRes.data;
      console.log('[Batch] Got profile:', profileRes.data);
    } catch (profileErr) {
      console.log('[Batch] No profile (expected):', profileErr);
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
}

async function submitJob() {
  if (!form.value.repo_url) {
    error.value = 'Repository URL is required';
    return;
  }
  
  submitting.value = true;
  error.value = '';
  
  try {
    await api.batch.createJob(form.value);
    showForm.value = false;
    form.value = { repo_url: '', branch: 'main', target_email: '', max_commits: 500 };
    await loadData();
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.response?.data?.repo_url?.[0] || 'Failed to create job';
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

function extractRepoName(url: string): string {
  const parts = url.replace(/\.git$/, '').split('/');
  return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
}

// Lifecycle
onMounted(() => {
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
  <div class="min-h-screen bg-surface p-6">
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
          @click="showForm = true"
          class="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors"
        >
          <span class="material-symbols-outlined text-xl">add</span>
          New Analysis
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
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
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
        <div v-else class="bg-surface-container rounded-xl p-8 text-center">
          <span class="material-symbols-outlined text-5xl text-on-surface-variant mb-3">psychology</span>
          <h3 class="text-lg font-medium text-on-surface mb-2">No Developer Profile Yet</h3>
          <p class="text-sm text-on-surface-variant mb-4">
            Run a batch analysis on your repository to build your profile
          </p>
          <button
            @click="showForm = true"
            class="px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-primary/90 transition-colors"
          >
            Start Analysis
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
            <div v-for="job in jobs" :key="job.id" class="p-4 hover:bg-surface-container-high/50 transition-colors">
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
                  <button
                    v-if="['pending', 'cloning', 'analyzing', 'building_profile'].includes(job.status)"
                    @click="cancelJob(job.id)"
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
              
              <!-- Branch -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Branch
                </label>
                <input
                  v-model="form.branch"
                  type="text"
                  placeholder="main"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary"
                />
              </div>
              
              <!-- Target Email -->
              <div>
                <label class="block text-xs font-semibold uppercase tracking-widest text-outline mb-2">
                  Filter by Author Email
                </label>
                <input
                  v-model="form.target_email"
                  type="email"
                  placeholder="Leave empty to analyze all authors"
                  class="w-full bg-surface-container-lowest border border-outline-variant/30 text-on-surface rounded-lg py-2.5 px-3 focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary"
                />
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
                  :disabled="submitting"
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
    </div>
  </div>
</template>
