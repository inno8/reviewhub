<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useProjectsStore } from '@/stores/projects';
import { useFindingsStore } from '@/stores/findings';
import { api } from '@/composables/useApi';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const projectsStore = useProjectsStore();
const findingsStore = useFindingsStore();

const selectedDate = ref<string | null>(null);

// Modal states
const showNewReviewModal = ref(false);
const showAddProjectModal = ref(false);
const reviewLoading = ref(false);
const projectLoading = ref(false);
const branches = ref<{ name: string; selected: boolean }[]>([]);
const newProjectUrl = ref('');
const newProjectName = ref('');
const newProjectDesc = ref('');
const newProjectCategoryId = ref<number | null>(null);
const newProjectMemberIds = ref<number[]>([]);
const projectCategories = ref<{ id: number; name: string }[]>([]);
const projectUsersList = ref<{ id: number; username: string; email: string }[]>([]);
const memberMode = ref<'individual' | 'category'>('category');
const modalError = ref('');
const modalSuccess = ref('');

onMounted(async () => {
  await projectsStore.fetchProjects();
  fetchActivityDates();
});

const navItems = [
  { name: 'Dashboard', icon: 'dashboard', path: '/' },
  { name: 'Projects', icon: 'folder_open', path: '/projects' },
  { name: 'Skills', icon: 'school', path: '/skills' },
  { name: 'Insights', icon: 'analytics', path: '/insights' },
  { name: 'Dev profile', icon: 'psychology', path: '/dev-profile/results' },
  { name: 'Batch Analysis', icon: 'history', path: '/batch', devOnly: true },
  { name: 'Commit Timeline', icon: 'timeline', path: '/timeline' },
  { name: 'Team Management', icon: 'group', path: '/team', adminOnly: true },
];

function isActive(path: string) {
  if (path === '/dev-profile/results') {
    return (
      route.path === '/dev-profile/results' || route.path === '/dev-profile-setup'
    );
  }
  return route.path === path;
}

// Calendar data
const currentMonth = ref(new Date());

const monthName = computed(() => 
  currentMonth.value.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
);

const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const today = new Date();
const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

const firstDayOffset = computed(() => 
  new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth(), 1).getDay()
);

const daysInMonth = computed(() => 
  new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 0).getDate()
);

const calendarCells = computed(() => {
  const blanks = Array.from({ length: firstDayOffset.value }, () => null);
  const monthDays = Array.from({ length: daysInMonth.value }, (_, i) => i + 1);
  return [...blanks, ...monthDays];
});

const activityDates = ref<Set<string>>(new Set());
const activityCounts = ref<Record<string, number>>({});

const monthString = computed(() => {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
});

async function fetchActivityDates() {
  if (!projectsStore.selectedProjectId) {
    activityDates.value = new Set();
    activityCounts.value = {};
    return;
  }
  try {
    const { data } = await api.reviews.calendar(projectsStore.selectedProjectId, monthString.value);
    const dates = data.dates || [];
    const counts = data.counts || {};
    activityDates.value = new Set(Array.isArray(dates) ? dates : Object.keys(counts));
    activityCounts.value = counts;
  } catch {
    activityDates.value = new Set();
    activityCounts.value = {};
  }
}

function activityDotCount(day: number): number {
  const dateStr = formatDateStr(day);
  return Math.min(4, activityCounts.value[dateStr] || (activityDates.value.has(dateStr) ? 1 : 0));
}

const dotColors = ['bg-primary', 'bg-tertiary', 'bg-green-500', 'bg-yellow-500'];

function formatDateStr(day: number): string {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  const dayStr = String(day).padStart(2, '0');
  return `${year}-${month}-${dayStr}`;
}

function isToday(day: number): boolean {
  return formatDateStr(day) === todayStr;
}

function hasActivity(day: number): boolean {
  return activityDates.value.has(formatDateStr(day));
}

function isSelected(day: number): boolean {
  return formatDateStr(day) === selectedDate.value;
}

async function selectDate(day: number) {
  const dateStr = formatDateStr(day);
  
  if (selectedDate.value === dateStr) {
    selectedDate.value = null;
    if (projectsStore.selectedProjectId) {
      await findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
    }
  } else {
    selectedDate.value = dateStr;
    if (projectsStore.selectedProjectId) {
      await findingsStore.fetchFindings({ 
        projectId: projectsStore.selectedProjectId,
        date: dateStr 
      });
    }
  }
  
  if (route.path !== '/') {
    router.push('/');
  }
}

function prevMonth() {
  currentMonth.value = new Date(
    currentMonth.value.getFullYear(),
    currentMonth.value.getMonth() - 1,
    1
  );
}

function nextMonth() {
  currentMonth.value = new Date(
    currentMonth.value.getFullYear(),
    currentMonth.value.getMonth() + 1,
    1
  );
}

watch(() => projectsStore.selectedProjectId, () => {
  selectedDate.value = null;
  fetchActivityDates();
});

watch(monthString, fetchActivityDates);

/** All accessible projects — developers can verify webhook/commits on linked repos too. */
const newReviewProjectOptions = computed(() => projectsStore.projects);

// Git identity for commit filtering
interface GitConnection { id: number; provider: string; username: string; email?: string; }
const gitConnections = ref<GitConnection[]>([]);
const selectedGitUsername = ref<string>('');

async function loadGitConnections() {
  try {
    const { data } = await api.gitConnections.list();
    gitConnections.value = Array.isArray(data) ? data : (data as any).results || [];
    // Auto-select first connection if available
    if (gitConnections.value.length && !selectedGitUsername.value) {
      selectedGitUsername.value = gitConnections.value[0].username;
    }
  } catch { gitConnections.value = []; }
}

const hasGitConnection = computed(() => gitConnections.value.length > 0);

// New Review Modal
const reviewProjectId = ref<number | null>(null);
const reviewRepoUrl = ref('');
const reviewStep = ref<'setup' | 'checking' | 'results'>('setup');
const reviewPastCommits = ref<any[]>([]);
const reviewWebhookConnected = ref(false);
/** Latest GET /projects/:id/webhook/ payload for the results step */
const reviewWebhookInfo = ref<Record<string, unknown> | null>(null);
const reviewBranchSummary = ref<{
  seen: string[];
  defaultBranch: string | null;
  matchesDefault: boolean | null;
} | null>(null);

async function openNewReviewModal() {
  showNewReviewModal.value = true;
  modalError.value = '';
  modalSuccess.value = '';
  reviewStep.value = 'setup';
  reviewPastCommits.value = [];
  reviewWebhookConnected.value = false;
  reviewWebhookInfo.value = null;
  reviewBranchSummary.value = null;
  reviewRepoUrl.value = '';
  branches.value = [];

  const options = newReviewProjectOptions.value;
  const sel = projectsStore.selectedProjectId;
  reviewProjectId.value = sel && options.some((p) => p.id === sel) ? sel : options[0]?.id ?? null;

  // Load git connections for commit filtering
  await loadGitConnections();
}

async function analyzeMyHistory() {
  if (!reviewProjectId.value || !selectedGitUsername.value) return;
  reviewLoading.value = true;
  modalError.value = '';
  try {
    await api.batch.createJob({
      project: reviewProjectId.value,
      repo_url: reviewRepoUrl.value || undefined,
      branch: '__all__',
      target_github_username: selectedGitUsername.value,
      max_commits: 50,
    });
    modalSuccess.value = `Batch analysis started for commits by ${selectedGitUsername.value}. Check the Batch Analysis page for progress.`;
    setTimeout(() => { showNewReviewModal.value = false; router.push('/batch'); }, 2000);
  } catch (e: any) {
    modalError.value = e?.response?.data?.detail || e?.response?.data?.error || 'Failed to start analysis';
  } finally {
    reviewLoading.value = false;
  }
}

async function startReviewCheck() {
  if (!reviewProjectId.value) {
    modalError.value = 'Select a project';
    return;
  }
  reviewLoading.value = true;
  modalError.value = '';
  reviewStep.value = 'checking';
  reviewWebhookInfo.value = null;
  reviewBranchSummary.value = null;
  reviewPastCommits.value = [];

  try {
    let projectDetail: { repo_url?: string | null; default_branch?: string } | null = null;
    try {
      const { data } = await api.projects.get(reviewProjectId.value);
      projectDetail = data as { repo_url?: string | null; default_branch?: string };
    } catch {
      projectDetail = null;
    }
    const serverHasRepo = Boolean(projectDetail?.repo_url && String(projectDetail.repo_url).trim());
    const urlTrim = reviewRepoUrl.value.trim();
    if (!serverHasRepo && !urlTrim) {
      modalError.value = 'This project has no repository URL yet. Enter one above, then run the check again.';
      reviewStep.value = 'setup';
      reviewLoading.value = false;
      return;
    }
    if (urlTrim) {
      try {
        const { data } = await api.projects.linkRepo(reviewProjectId.value, urlTrim);
        projectsStore.updateProjectRepoUrl(reviewProjectId.value, data.repo_url ?? urlTrim);
        await projectsStore.fetchProjects();
        projectDetail = { ...projectDetail, ...(data as object) } as typeof projectDetail;
      } catch (linkErr: any) {
        modalError.value = linkErr?.response?.data?.error || 'Failed to save repository URL';
        reviewStep.value = 'setup';
        reviewLoading.value = false;
        return;
      }
    }

    const pid = reviewProjectId.value;
    const [evalRes, webhookRes] = await Promise.allSettled([
      api.evaluations.list({ projectId: pid, limit: 20 }),
      api.webhooks.info(pid),
    ]);

    let defaultBranch: string | null = projectDetail?.default_branch ?? null;
    if (webhookRes.status === 'fulfilled') {
      const w = webhookRes.value.data as Record<string, unknown>;
      reviewWebhookInfo.value = w;
      reviewWebhookConnected.value = Boolean(w.connected);
      if (!defaultBranch && w.default_branch) {
        defaultBranch = String(w.default_branch);
      }
    } else {
      reviewWebhookInfo.value = null;
      reviewWebhookConnected.value = false;
    }

    if (evalRes.status === 'fulfilled') {
      const raw = evalRes.value.data as { results?: unknown[] } | unknown[];
      const all = Array.isArray(raw) ? raw : raw?.results ?? [];
      const list = Array.isArray(all) ? all : [];
      reviewPastCommits.value = list.slice(0, 10);
      const branches = [
        ...new Set(
          reviewPastCommits.value.map((e: { branch?: string }) => e.branch).filter(Boolean) as string[],
        ),
      ];
      let matchesDefault: boolean | null = null;
      if (defaultBranch && branches.length) {
        matchesDefault = branches.some((b) => b === defaultBranch || b.endsWith(`/${defaultBranch}`));
      }
      reviewBranchSummary.value = {
        seen: branches,
        defaultBranch,
        matchesDefault,
      };
    } else {
      reviewPastCommits.value = [];
      reviewBranchSummary.value = {
        seen: [],
        defaultBranch,
        matchesDefault: null,
      };
      const reason = evalRes.status === 'rejected' ? evalRes.reason : null;
      console.error('Evaluations list failed', reason);
      const ax = reason && typeof reason === 'object' && 'response' in reason
        ? (reason as { response?: { data?: unknown } }).response?.data
        : null;
      const msg =
        ax && typeof ax === 'object' && ax !== null && 'detail' in ax
          ? String((ax as { detail: unknown }).detail)
          : null;
      modalError.value = msg || 'Could not load past commits for this project.';
    }

    reviewStep.value = 'results';
  } catch {
    modalError.value = 'Failed to check project status';
    reviewStep.value = 'setup';
  } finally {
    reviewLoading.value = false;
  }
}

// Add Project Modal
async function openAddProjectModal() {
  showAddProjectModal.value = true;
  modalError.value = '';
  modalSuccess.value = '';
  newProjectName.value = '';
  newProjectDesc.value = '';
  newProjectCategoryId.value = null;
  newProjectMemberIds.value = [];
  memberMode.value = 'category';

  try {
    const [catsRes, usersRes] = await Promise.all([
      api.categories.list(),
      api.users.list(),
    ]);
    projectCategories.value = (catsRes.data.results || catsRes.data || []);
    const allUsers = usersRes.data.results || usersRes.data || [];
    projectUsersList.value = allUsers.filter((u: any) => u.role !== 'admin');
  } catch { /* ignore */ }
}

function toggleMember(userId: number) {
  const idx = newProjectMemberIds.value.indexOf(userId);
  if (idx >= 0) newProjectMemberIds.value.splice(idx, 1);
  else newProjectMemberIds.value.push(userId);
}

async function createProject() {
  if (!newProjectName.value.trim()) {
    modalError.value = 'Project name is required';
    return;
  }

  projectLoading.value = true;
  modalError.value = '';
  modalSuccess.value = '';

  try {
    const payload: any = {
      name: newProjectName.value.trim(),
      description: newProjectDesc.value.trim(),
    };
    if (memberMode.value === 'category' && newProjectCategoryId.value) {
      payload.category_id = newProjectCategoryId.value;
    } else if (memberMode.value === 'individual' && newProjectMemberIds.value.length) {
      payload.member_ids = newProjectMemberIds.value;
    }

    await api.projects.create(payload);
    modalSuccess.value = 'Project created!';
    await projectsStore.fetchProjects();

    setTimeout(() => {
      showAddProjectModal.value = false;
      modalSuccess.value = '';
    }, 1500);
  } catch (e: any) {
    modalError.value = e?.response?.data?.error || e?.response?.data?.name?.[0] || 'Failed to create project';
  } finally {
    projectLoading.value = false;
  }
}

function toggleAllBranches(selected: boolean) {
  branches.value.forEach(b => b.selected = selected);
}
</script>

<template>
  <aside class="fixed left-0 top-16 h-[calc(100vh-64px)] w-64 flex flex-col py-4 bg-surface-container-low z-40">
    <!-- Project Selector -->
    <div class="px-4 mb-4">
      <div class="flex items-center gap-3 p-3 bg-surface-container rounded-lg border border-outline-variant/20">
        <div class="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
          <span class="material-symbols-outlined text-primary text-lg">terminal</span>
        </div>
        <div class="flex-1 min-w-0">
          <select
            :value="projectsStore.selectedProjectId"
            @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
            class="w-full bg-transparent border-none text-sm font-bold text-primary focus:ring-0 cursor-pointer p-0 truncate"
          >
            <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
              {{ project.displayName }}
            </option>
          </select>
          <p class="text-[10px] text-outline uppercase tracking-widest">Active Project</p>
        </div>
      </div>
      
      <!-- Add Project Button -->
      <button
        v-if="auth.isAdmin"
        @click="openAddProjectModal"
        class="w-full mt-2 py-2 px-3 border border-dashed border-outline-variant/30 rounded-lg text-xs text-outline hover:text-primary hover:border-primary/50 transition-colors flex items-center justify-center gap-2"
      >
        <span class="material-symbols-outlined text-sm">add</span>
        Add Project
      </button>
    </div>

    <!-- New Review Button (developers only) -->
    <div v-if="!auth.isAdmin" class="px-4 mb-6">
      <button
        @click="openNewReviewModal"
        class="w-full primary-gradient text-on-primary font-bold py-3 px-4 rounded-lg flex items-center justify-center gap-2 active:scale-95 transition-transform"
      >
        <span class="material-symbols-outlined text-xl">add</span>
        <span class="text-sm">New Review</span>
      </button>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        v-show="(!item.adminOnly || auth.isAdmin) && (!item.devOnly || !auth.isAdmin)"
        :class="[
          'rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium',
          isActive(item.path)
            ? 'bg-surface-container text-primary'
            : 'text-outline hover:bg-surface-container/50 hover:text-on-surface'
        ]"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.name }}</span>
      </router-link>

      <!-- Calendar Widget -->
      <div class="mt-8 px-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-[10px] uppercase tracking-widest text-outline font-bold">
            Activity — {{ monthName }}
          </h3>
          <div class="flex gap-1">
            <button 
              @click="prevMonth"
              class="p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors"
            >
              <span class="material-symbols-outlined text-sm">chevron_left</span>
            </button>
            <button 
              @click="nextMonth"
              class="p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors"
            >
              <span class="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </div>
        </div>
        
        <div class="bg-surface-container-lowest rounded-xl p-3 border border-outline-variant/10">
          <div class="grid grid-cols-7 gap-1 text-center mb-2">
            <span v-for="day in days" :key="day" class="text-[8px] text-outline">{{ day }}</span>
          </div>

          <div class="grid grid-cols-7 gap-1 text-[10px]">
            <button
              v-for="(day, index) in calendarCells"
              :key="`cell-${index}`"
              :disabled="!day"
              :class="[
                'p-1 text-center rounded transition-all flex flex-col items-center',
                !day && 'invisible',
                day && isToday(day) && !isSelected(day) && 'bg-primary text-on-primary font-bold shadow-lg shadow-primary/20',
                day && isSelected(day) && 'ring-2 ring-primary bg-primary/20 text-primary font-bold',
                day && !isToday(day) && !isSelected(day) && hasActivity(day) && 'text-primary hover:bg-primary-container/40 cursor-pointer',
                day && !isToday(day) && !isSelected(day) && !hasActivity(day) && 'text-on-surface-variant hover:bg-surface-container cursor-pointer',
              ]"
              @click="day && selectDate(day)"
            >
              <span>{{ day || '' }}</span>
              <span v-if="day && activityDotCount(day) > 0" class="flex gap-[2px] mt-[1px]">
                <span v-for="d in activityDotCount(day)" :key="d"
                  :class="['w-1 h-1 rounded-full', dotColors[(d - 1) % dotColors.length]]"></span>
              </span>
            </button>
          </div>
          
          <div v-if="selectedDate" class="mt-3 pt-3 border-t border-outline-variant/10">
            <div class="flex items-center justify-between">
              <span class="text-[10px] text-primary font-bold">Filtering: {{ selectedDate }}</span>
              <button 
                @click="selectDate(parseInt(selectedDate.split('-')[2]))"
                class="text-[10px] text-outline hover:text-error"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Bottom Section -->
    <div class="mt-auto border-t border-outline-variant/10 pt-4">
      <router-link
        to="/settings"
        :class="[
          'rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium',
          isActive('/settings')
            ? 'bg-surface-container text-primary'
            : 'text-outline hover:bg-surface-container/50 hover:text-on-surface'
        ]"
      >
        <span class="material-symbols-outlined">settings</span>
        <span>Settings</span>
      </router-link>
      <a
        href="#"
        class="text-outline hover:bg-surface-container/50 hover:text-on-surface rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium"
      >
        <span class="material-symbols-outlined">help</span>
        <span>Support</span>
      </a>
    </div>
  </aside>

  <!-- New Review Modal -->
  <div
    v-if="showNewReviewModal"
    class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
  >
    <div class="glass-panel w-full max-w-lg rounded-xl overflow-hidden shadow-2xl max-h-[90vh] overflow-y-auto">
      <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
        <h3 class="text-lg font-bold text-on-surface">New Review</h3>
        <button @click="showNewReviewModal = false" class="text-outline hover:text-on-surface">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="p-6 space-y-4">
        <!-- Step 1: Setup -->
        <template v-if="reviewStep === 'setup'">
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Project</label>
            <p v-if="!newReviewProjectOptions.length" class="text-sm text-outline py-2">
              No projects available. Ask an admin to add you to a project.
            </p>
            <select v-else v-model="reviewProjectId"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-3 px-4">
              <option :value="null" disabled>Select project...</option>
              <option v-for="p in newReviewProjectOptions" :key="p.id" :value="p.id">{{ p.displayName }}</option>
            </select>
            <p v-if="newReviewProjectOptions.length" class="text-[10px] text-outline">
              Pick the project whose repo and webhook you want to inspect. Enter a URL only if that project is not linked yet.
            </p>
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Repository URL</label>
            <input v-model="reviewRepoUrl" type="url" placeholder="https://github.com/user/repo"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4 text-sm" />
            <p class="text-[10px] text-outline">GitHub, GitLab, or Bitbucket repository URL</p>
          </div>

          <!-- Git Identity Selector -->
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Your Git Identity</label>
            <div v-if="hasGitConnection">
              <select v-model="selectedGitUsername"
                class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-3 px-4">
                <option v-for="c in gitConnections" :key="c.id" :value="c.username">
                  {{ c.username }} ({{ c.provider }}{{ c.email ? ' · ' + c.email : '' }})
                </option>
              </select>
              <p class="text-[10px] text-outline mt-1">
                Only commits matching this git username will be fetched and reviewed.
              </p>
            </div>
            <div v-else class="p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <p class="text-sm text-orange-400 flex items-center gap-2">
                <span class="material-symbols-outlined text-sm">warning</span>
                No git account configured.
              </p>
              <p class="text-[10px] text-outline mt-1">
                Go to <router-link to="/settings" class="text-primary font-semibold" @click="showNewReviewModal = false">Settings → Git Connections</router-link>
                to link your GitHub/GitLab account first. This is needed to identify your commits.
              </p>
            </div>
          </div>
        </template>

        <!-- Step 2: Checking -->
        <template v-if="reviewStep === 'checking'">
          <div class="flex flex-col items-center py-8">
            <span class="material-symbols-outlined text-4xl text-primary animate-spin mb-4">progress_activity</span>
            <p class="text-sm text-on-surface-variant">Checking for past commits & webhook status...</p>
          </div>
        </template>

        <!-- Step 3: Results -->
        <template v-if="reviewStep === 'results'">
          <!-- Past commits (evaluations for this project only) -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-sm" :class="reviewPastCommits.length ? 'text-green-400' : 'text-yellow-400'">
                {{ reviewPastCommits.length ? 'check_circle' : 'info' }}
              </span>
              <span class="text-sm font-bold text-on-surface">
                {{ reviewPastCommits.length ? `${reviewPastCommits.length} recent evaluations (this project)` : 'No evaluations yet for this project' }}
              </span>
            </div>
            <div v-if="reviewPastCommits.length" class="max-h-36 overflow-y-auto bg-surface-container-lowest rounded-lg p-3 space-y-2">
              <div v-for="c in reviewPastCommits" :key="c.id" class="text-xs text-on-surface-variant flex flex-col gap-0.5 border-b border-outline-variant/10 pb-2 last:border-0 last:pb-0">
                <div class="flex justify-between gap-2">
                  <span class="font-mono truncate">{{ c.commit_sha?.slice(0, 8) || c.id }}</span>
                  <span class="text-outline shrink-0">{{ c.created_at?.split('T')[0] || '' }}</span>
                </div>
                <span v-if="c.branch" class="text-[10px] text-primary font-mono">branch: {{ c.branch }}</span>
              </div>
            </div>
          </div>

          <!-- Branches vs default -->
          <div v-if="reviewBranchSummary" class="space-y-2 pt-2 border-t border-outline-variant/10">
            <p class="text-xs font-bold text-on-surface">Branches in recent activity</p>
            <p v-if="reviewBranchSummary.seen.length" class="text-xs text-on-surface-variant">
              <span class="font-mono text-primary">{{ reviewBranchSummary.seen.join(', ') }}</span>
              <template v-if="reviewBranchSummary.defaultBranch">
                · default: <span class="font-mono">{{ reviewBranchSummary.defaultBranch }}</span>
              </template>
            </p>
            <p v-else class="text-xs text-outline">No branch info until at least one evaluation exists for this repo.</p>
            <p
              v-if="reviewBranchSummary.defaultBranch && reviewBranchSummary.seen.length"
              class="text-[11px] flex items-center gap-1.5"
              :class="reviewBranchSummary.matchesDefault ? 'text-green-400' : 'text-yellow-500'"
            >
              <span class="material-symbols-outlined text-sm">{{ reviewBranchSummary.matchesDefault ? 'check_circle' : 'warning' }}</span>
              {{
                reviewBranchSummary.matchesDefault
                  ? 'Recent pushes include the project default branch.'
                  : 'Recent activity is on other branches; ensure your webhook fires for the branch you care about (e.g. default branch).'
              }}
            </p>
          </div>

          <!-- Webhook: ReviewHub endpoint + optional live traffic -->
          <div class="space-y-2 pt-2 border-t border-outline-variant/10">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-sm" :class="reviewWebhookConnected ? 'text-green-400' : 'text-outline'">
                {{ reviewWebhookConnected ? 'link' : 'link_off' }}
              </span>
              <span class="text-sm font-bold text-on-surface">Webhook endpoint (ReviewHub)</span>
            </div>
            <p class="text-[11px] text-on-surface-variant">
              Paste this URL and secret in your Git host so pushes create evaluations for
              <strong class="text-on-surface">this project</strong>.
            </p>
            <div v-if="reviewWebhookInfo?.webhook_url" class="bg-surface-container-lowest rounded-lg p-3 space-y-2">
              <div>
                <p class="text-[10px] uppercase text-outline font-bold mb-0.5">Payload URL</p>
                <code class="text-[11px] text-primary break-all select-all block">{{ reviewWebhookInfo.webhook_url }}</code>
              </div>
              <div v-if="reviewWebhookInfo.webhook_secret">
                <p class="text-[10px] uppercase text-outline font-bold mb-0.5">Secret</p>
                <code class="text-[11px] text-on-surface-variant break-all select-all block">{{ reviewWebhookInfo.webhook_secret }}</code>
              </div>
            </div>
            <div
              v-if="reviewWebhookInfo && reviewWebhookInfo.receiving_webhooks"
              class="flex items-center gap-2 text-xs text-green-400"
            >
              <span class="material-symbols-outlined text-sm">rss_feed</span>
              Webhook traffic has been recorded for this project.
            </div>
            <div
              v-else-if="reviewWebhookInfo && !reviewWebhookInfo.receiving_webhooks"
              class="text-[11px] text-outline"
            >
              No webhook deliveries recorded yet—after you add the hook in GitHub/GitLab/Bitbucket, push a commit to see evaluations appear.
            </div>
          </div>

          <!-- Analyze History Button -->
          <div v-if="!reviewPastCommits.length && hasGitConnection" class="pt-2 border-t border-outline-variant/10">
            <p class="text-xs text-outline mb-2">No evaluations yet? Analyze your past commits:</p>
            <button @click="analyzeMyHistory" :disabled="reviewLoading"
              class="w-full py-2.5 bg-primary/10 text-primary font-bold text-sm rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
              <span class="material-symbols-outlined text-sm">history</span>
              Analyze My Commit History
            </button>
            <p class="text-[10px] text-outline mt-1">
              Fetches commits by <strong>{{ selectedGitUsername }}</strong> and runs AI code review on each.
            </p>
          </div>

          <button type="button" @click="reviewStep = 'setup'" class="text-xs text-primary hover:underline">← Back to setup</button>
        </template>

        <!-- Error/Success -->
        <div v-if="modalError" class="p-3 bg-error/10 border border-error/20 rounded-lg">
          <p class="text-sm text-error">{{ modalError }}</p>
        </div>
        <div v-if="modalSuccess" class="p-3 bg-primary/10 border border-primary/20 rounded-lg">
          <p class="text-sm text-primary">{{ modalSuccess }}</p>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 pt-2">
          <button @click="showNewReviewModal = false"
            class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors">
            Cancel
          </button>
          <button v-if="reviewStep === 'setup'" @click="startReviewCheck"
            :disabled="reviewLoading || !reviewProjectId || !newReviewProjectOptions.length || !hasGitConnection"
            class="flex-1 py-3 primary-gradient text-on-primary font-bold rounded-lg disabled:opacity-50 flex items-center justify-center gap-2">
            Start Review
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Add Project Modal -->
  <div
    v-if="showAddProjectModal"
    class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
  >
    <div class="glass-panel w-full max-w-lg rounded-xl overflow-hidden shadow-2xl max-h-[90vh] overflow-y-auto">
      <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
        <h3 class="text-lg font-bold text-on-surface">Add New Project</h3>
        <button @click="showAddProjectModal = false" class="text-outline hover:text-on-surface">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="p-6 space-y-4">
        <div class="space-y-1.5">
          <label class="text-xs font-bold uppercase tracking-widest text-outline">Project Name</label>
          <input v-model="newProjectName" type="text" placeholder="e.g. ReviewHub" required
            class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
        </div>

        <div class="space-y-1.5">
          <label class="text-xs font-bold uppercase tracking-widest text-outline">Description</label>
          <input v-model="newProjectDesc" type="text" placeholder="Short description..."
            class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
        </div>

        <!-- Member Assignment -->
        <div class="space-y-2">
          <label class="text-xs font-bold uppercase tracking-widest text-outline">Add Members</label>
          <div class="flex bg-surface-container-lowest p-1 rounded-lg w-fit">
            <button type="button"
              :class="['px-4 py-1.5 text-xs font-bold rounded-md transition-all', memberMode === 'category' ? 'bg-surface-container text-primary shadow-sm' : 'text-outline hover:text-on-surface']"
              @click="memberMode = 'category'">By Category</button>
            <button type="button"
              :class="['px-4 py-1.5 text-xs font-bold rounded-md transition-all', memberMode === 'individual' ? 'bg-surface-container text-primary shadow-sm' : 'text-outline hover:text-on-surface']"
              @click="memberMode = 'individual'">Individual</button>
          </div>

          <div v-if="memberMode === 'category'" class="space-y-1.5">
            <select v-model="newProjectCategoryId"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-3 px-4">
              <option :value="null">Select a category...</option>
              <option v-for="cat in projectCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
          </div>

          <div v-else class="max-h-40 overflow-y-auto bg-surface-container-lowest rounded-lg p-3 space-y-2 border border-outline-variant/30">
            <label v-for="u in projectUsersList" :key="u.id" class="flex items-center gap-2 cursor-pointer group">
              <input type="checkbox" :checked="newProjectMemberIds.includes(u.id)" @change="toggleMember(u.id)"
                class="h-4 w-4 rounded border-outline-variant bg-surface-container text-primary" />
              <span class="text-sm text-on-surface-variant group-hover:text-on-surface">{{ u.username }} <span class="text-outline text-xs">({{ u.email }})</span></span>
            </label>
            <p v-if="!projectUsersList.length" class="text-xs text-outline">No users available</p>
          </div>
        </div>

        <div v-if="modalError" class="p-3 bg-error/10 border border-error/20 rounded-lg">
          <p class="text-sm text-error">{{ modalError }}</p>
        </div>
        <div v-if="modalSuccess" class="p-3 bg-primary/10 border border-primary/20 rounded-lg">
          <p class="text-sm text-primary">{{ modalSuccess }}</p>
        </div>

        <div class="flex gap-3 pt-2">
          <button @click="showAddProjectModal = false"
            class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors">Cancel</button>
          <button @click="createProject" :disabled="projectLoading || !newProjectName.trim()"
            class="flex-1 py-3 primary-gradient text-on-primary font-bold rounded-lg disabled:opacity-50 flex items-center justify-center gap-2">
            <span v-if="projectLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            {{ projectLoading ? 'Creating...' : 'Create Project' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
