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
const modalError = ref('');
const modalSuccess = ref('');

onMounted(() => {
  projectsStore.fetchProjects();
});

const navItems = [
  { name: 'Dashboard', icon: 'dashboard', path: '/' },
  { name: 'Insights', icon: 'analytics', path: '/insights' },
  { name: 'Team Management', icon: 'group', path: '/team', adminOnly: true },
];

function isActive(path: string) {
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

const activityDates = ref<Set<string>>(new Set(['2026-03-08', '2026-03-11', '2026-03-16', '2026-03-19', '2026-03-23']));

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
});

// New Review Modal
async function openNewReviewModal() {
  showNewReviewModal.value = true;
  modalError.value = '';
  modalSuccess.value = '';
  branches.value = [];
  
  if (projectsStore.selectedProjectId) {
    try {
      const { data } = await api.projects.getBranches(projectsStore.selectedProjectId);
      branches.value = data.branches.map((b: any) => ({ name: b.name, selected: true }));
    } catch (e) {
      modalError.value = 'Failed to fetch branches';
    }
  }
}

async function triggerReview() {
  if (!projectsStore.selectedProjectId) return;
  
  reviewLoading.value = true;
  modalError.value = '';
  modalSuccess.value = '';
  
  try {
    const selectedBranches = branches.value.filter(b => b.selected).map(b => b.name);
    const { data } = await api.reviews.trigger(
      projectsStore.selectedProjectId,
      selectedBranches.length > 0 ? selectedBranches : undefined
    );
    
    modalSuccess.value = data.message;
    
    // Refresh findings
    await findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
    
    // Close modal after a delay
    setTimeout(() => {
      showNewReviewModal.value = false;
      modalSuccess.value = '';
    }, 2000);
  } catch (e: any) {
    modalError.value = e?.response?.data?.error || 'Failed to trigger review';
  } finally {
    reviewLoading.value = false;
  }
}

// Add Project Modal
async function createProject() {
  if (!newProjectUrl.value) {
    modalError.value = 'Please enter a GitHub URL';
    return;
  }
  
  projectLoading.value = true;
  modalError.value = '';
  modalSuccess.value = '';
  
  try {
    const { data } = await api.projects.createFromUrl(newProjectUrl.value);
    
    modalSuccess.value = data.message;
    
    // Refresh projects
    await projectsStore.fetchProjects();
    projectsStore.setSelectedProject(data.project.id);
    
    // Close modal after a delay
    setTimeout(() => {
      showAddProjectModal.value = false;
      newProjectUrl.value = '';
      modalSuccess.value = '';
    }, 2000);
  } catch (e: any) {
    modalError.value = e?.response?.data?.error || 'Failed to create project';
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
        @click="showAddProjectModal = true"
        class="w-full mt-2 py-2 px-3 border border-dashed border-outline-variant/30 rounded-lg text-xs text-outline hover:text-primary hover:border-primary/50 transition-colors flex items-center justify-center gap-2"
      >
        <span class="material-symbols-outlined text-sm">add</span>
        Add Project
      </button>
    </div>

    <!-- New Review Button -->
    <div class="px-4 mb-6">
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
        v-show="!item.adminOnly || auth.isAdmin"
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
                'p-1 text-center rounded transition-all',
                !day && 'invisible',
                day && isToday(day) && !isSelected(day) && 'bg-primary text-on-primary font-bold shadow-lg shadow-primary/20',
                day && isSelected(day) && 'ring-2 ring-primary bg-primary/20 text-primary font-bold',
                day && !isToday(day) && !isSelected(day) && hasActivity(day) && 'bg-primary-container/20 text-primary border border-primary/30 hover:bg-primary-container/40 cursor-pointer',
                day && !isToday(day) && !isSelected(day) && !hasActivity(day) && 'text-on-surface-variant hover:bg-surface-container cursor-pointer',
              ]"
              @click="day && selectDate(day)"
            >
              {{ day || '' }}
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
    <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
      <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
        <h3 class="text-lg font-bold text-on-surface">Run Code Review</h3>
        <button @click="showNewReviewModal = false" class="text-outline hover:text-on-surface">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="p-6">
        <p class="text-sm text-on-surface-variant mb-4">
          Run @code-review on 
          <span class="font-bold text-primary">
            {{ projectsStore.projects.find(p => p.id === projectsStore.selectedProjectId)?.displayName }}
          </span>
        </p>

        <!-- Branch Selection -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Select Branches</label>
            <div class="flex gap-2">
              <button @click="toggleAllBranches(true)" class="text-[10px] text-primary hover:underline">All</button>
              <button @click="toggleAllBranches(false)" class="text-[10px] text-outline hover:underline">None</button>
            </div>
          </div>
          <div class="max-h-48 overflow-y-auto bg-surface-container-lowest rounded-lg p-3 space-y-2">
            <label
              v-for="branch in branches"
              :key="branch.name"
              class="flex items-center gap-2 cursor-pointer group"
            >
              <input
                type="checkbox"
                v-model="branch.selected"
                class="h-4 w-4 rounded border-outline-variant bg-surface-container text-primary"
              />
              <span class="text-sm text-on-surface-variant group-hover:text-on-surface font-mono">
                {{ branch.name }}
              </span>
            </label>
            <p v-if="branches.length === 0" class="text-sm text-outline">Loading branches...</p>
          </div>
        </div>

        <!-- Error/Success Messages -->
        <div v-if="modalError" class="mb-4 p-3 bg-error/10 border border-error/20 rounded-lg">
          <p class="text-sm text-error">{{ modalError }}</p>
        </div>
        <div v-if="modalSuccess" class="mb-4 p-3 bg-primary/10 border border-primary/20 rounded-lg">
          <p class="text-sm text-primary">{{ modalSuccess }}</p>
        </div>

        <!-- Actions -->
        <div class="flex gap-3">
          <button
            @click="showNewReviewModal = false"
            class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
          >
            Cancel
          </button>
          <button
            @click="triggerReview"
            :disabled="reviewLoading || branches.filter(b => b.selected).length === 0"
            class="flex-1 py-3 primary-gradient text-on-primary font-bold rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <span v-if="reviewLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            {{ reviewLoading ? 'Running...' : 'Start Review' }}
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
    <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
      <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
        <h3 class="text-lg font-bold text-on-surface">Add New Project</h3>
        <button @click="showAddProjectModal = false" class="text-outline hover:text-on-surface">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="p-6">
        <p class="text-sm text-on-surface-variant mb-4">
          Enter the GitHub repository URL to connect it with @code-review.
        </p>

        <!-- GitHub URL Input -->
        <div class="mb-4">
          <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
            GitHub Repository URL
          </label>
          <input
            v-model="newProjectUrl"
            type="text"
            placeholder="https://github.com/owner/repo"
            class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
          />
          <p class="text-[10px] text-outline mt-2">
            Examples: https://github.com/inno8/project or inno8/project
          </p>
        </div>

        <!-- Error/Success Messages -->
        <div v-if="modalError" class="mb-4 p-3 bg-error/10 border border-error/20 rounded-lg">
          <p class="text-sm text-error">{{ modalError }}</p>
        </div>
        <div v-if="modalSuccess" class="mb-4 p-3 bg-primary/10 border border-primary/20 rounded-lg">
          <p class="text-sm text-primary">{{ modalSuccess }}</p>
        </div>

        <!-- Actions -->
        <div class="flex gap-3">
          <button
            @click="showAddProjectModal = false"
            class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
          >
            Cancel
          </button>
          <button
            @click="createProject"
            :disabled="projectLoading || !newProjectUrl"
            class="flex-1 py-3 primary-gradient text-on-primary font-bold rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <span v-if="projectLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            {{ projectLoading ? 'Creating...' : 'Add Project' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
