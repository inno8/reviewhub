<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import CalendarWidget from '@/components/calendar/CalendarWidget.vue';
import { useFindingsStore } from '@/stores/findings';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const router = useRouter();
const findingsStore = useFindingsStore();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const selectedCategory = ref('all');
const selectedDifficulty = ref('all');
const selectedAuthor = ref('all');
const selectedDate = ref<string | null>(null);

// Sync state
const syncing = ref(false);
const syncMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null);

const categories = ['SECURITY', 'PERFORMANCE', 'CODE_STYLE', 'TESTING', 'ARCHITECTURE'];
const difficulties = ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'];

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (projectsStore.selectedProjectId) {
    await findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
  }
});

watch(() => projectsStore.selectedProjectId, async (newId) => {
  if (newId) {
    selectedCategory.value = 'all';
    selectedDifficulty.value = 'all';
    selectedAuthor.value = 'all';
    selectedDate.value = null;
    await findingsStore.fetchFindings({ projectId: newId });
  }
});

function onDateSelected(date: string | null) {
  selectedDate.value = date;
  if (projectsStore.selectedProjectId) {
    findingsStore.fetchFindings({
      projectId: projectsStore.selectedProjectId,
      date: date ?? undefined,
    });
  }
}

function clearDateFilter() {
  selectedDate.value = null;
  if (projectsStore.selectedProjectId) {
    findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
  }
}

// Get unique authors from findings
const authors = computed(() => {
  const authorSet = new Set<string>();
  findingsStore.findings.forEach(f => {
    if (f.commitAuthor) authorSet.add(f.commitAuthor);
  });
  return Array.from(authorSet);
});

// Filter findings
const filteredFindings = computed(() => {
  return findingsStore.findings.filter((finding) => {
    if (selectedCategory.value !== 'all' && finding.category !== selectedCategory.value) return false;
    if (selectedDifficulty.value !== 'all' && finding.difficulty !== selectedDifficulty.value) return false;
    if (selectedAuthor.value !== 'all' && finding.commitAuthor !== selectedAuthor.value) return false;
    return true;
  });
});

// Group findings by file path
const groupedByFile = computed(() => {
  const groups: Record<string, typeof filteredFindings.value> = {};
  filteredFindings.value.forEach(finding => {
    const key = finding.filePath;
    if (!groups[key]) groups[key] = [];
    groups[key].push(finding);
  });
  return groups;
});

const fileGroups = computed(() => {
  return Object.entries(groupedByFile.value).map(([filePath, findings]) => ({
    filePath,
    findings,
    branch: findings[0]?.review?.branch || 'main',
    categories: [...new Set(findings.map(f => f.category))],
    difficulties: [...new Set(findings.map(f => f.difficulty))],
    authors: [...new Set(findings.map(f => f.commitAuthor).filter(Boolean))],
  }));
});

const currentDate = computed(() => {
  const now = new Date();
  return now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
});

function getCategoryClass(category: string) {
  const cat = category.toLowerCase().replace('_', '');
  return {
    security: 'bg-error/10 text-error border-error/20',
    performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    codestyle: 'bg-primary/10 text-primary border-primary/20',
    testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
    architecture: 'bg-secondary/10 text-secondary border-secondary/20',
  }[cat] || 'bg-outline/10 text-outline border-outline/20';
}

function openFile(filePath: string) {
  // Navigate to file detail view with all findings for this file
  const findingIds = groupedByFile.value[filePath].map(f => f.id);
  router.push({ path: '/file-review', query: { file: filePath, ids: findingIds.join(',') } });
}

function formatCategory(cat: string) {
  return cat.replace('_', ' ');
}

// Sync/refresh function for admins
async function triggerSync() {
  if (!projectsStore.selectedProjectId || syncing.value) return;
  
  syncing.value = true;
  syncMessage.value = null;
  
  try {
    const { data } = await api.reviews.trigger(projectsStore.selectedProjectId);
    syncMessage.value = {
      type: 'success',
      text: data.totalFindings > 0 
        ? `Synced! Found ${data.totalFindings} new findings.`
        : 'Synced. No new issues found.'
    };
    // Refresh findings list
    await findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
  } catch (error: any) {
    syncMessage.value = {
      type: 'error',
      text: error?.response?.data?.error || 'Sync failed. Please try again.'
    };
  } finally {
    syncing.value = false;
    // Auto-hide message after 5 seconds
    setTimeout(() => {
      syncMessage.value = null;
    }, 5000);
  }
}
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Content Header -->
      <header class="mb-10">
        <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">
          {{ currentDate }}
        </h1>
        <p class="text-outline text-sm">
          Welcome back. You have 
          <span class="text-primary font-semibold">{{ filteredFindings.length }} pending reviews</span>
          across {{ fileGroups.length }} files.
        </p>
      </header>

      <!-- Filter Bar -->
      <div class="flex flex-wrap items-center gap-4 mb-8 bg-surface-container-low p-3 rounded-xl border border-outline-variant/10">
        <!-- Project Selector -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">folder</span>
          <select
            :value="projectsStore.selectedProjectId"
            @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
              {{ project.displayName }}
            </option>
          </select>
        </div>

        <!-- Category Filter -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">filter_list</span>
          <select
            v-model="selectedCategory"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Category: All</option>
            <option v-for="cat in categories" :key="cat" :value="cat">
              {{ formatCategory(cat) }}
            </option>
          </select>
        </div>

        <!-- Difficulty Filter -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">signal_cellular_alt</span>
          <select
            v-model="selectedDifficulty"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Difficulty: All</option>
            <option v-for="diff in difficulties" :key="diff" :value="diff">
              {{ diff.charAt(0) + diff.slice(1).toLowerCase() }}
            </option>
          </select>
        </div>

        <!-- Author Filter -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">person</span>
          <select
            v-model="selectedAuthor"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Author: All</option>
            <option v-for="author in authors" :key="author" :value="author">
              {{ author }}
            </option>
          </select>
        </div>

        <!-- Sync Button (Admin Only) -->
        <button
          v-if="authStore.isAdmin"
          @click="triggerSync"
          :disabled="syncing || !projectsStore.selectedProjectId"
          class="flex items-center gap-2 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 rounded-lg border border-primary/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span 
            :class="['material-symbols-outlined text-sm text-primary', { 'animate-spin': syncing }]"
          >
            {{ syncing ? 'progress_activity' : 'sync' }}
          </span>
          <span class="text-xs text-primary font-medium">
            {{ syncing ? 'Syncing...' : 'Refresh' }}
          </span>
        </button>

        <!-- Sync Message -->
        <div
          v-if="syncMessage"
          :class="[
            'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
            syncMessage.type === 'success' 
              ? 'bg-green-500/10 text-green-400 border border-green-500/20' 
              : 'bg-error/10 text-error border border-error/20'
          ]"
        >
          <span class="material-symbols-outlined text-sm">
            {{ syncMessage.type === 'success' ? 'check_circle' : 'error' }}
          </span>
          {{ syncMessage.text }}
        </div>

        <!-- Date Filter Indicator -->
        <div
          v-if="selectedDate"
          class="flex items-center gap-2 px-3 py-1.5 bg-primary/10 rounded-lg border border-primary/20"
        >
          <span class="material-symbols-outlined text-sm text-primary">calendar_today</span>
          <span class="text-xs text-primary font-medium">{{ selectedDate }}</span>
          <button @click="clearDateFilter" class="text-primary hover:text-error ml-1">
            <span class="material-symbols-outlined text-sm">close</span>
          </button>
        </div>

        <!-- Results Count -->
        <div class="ml-auto">
          <span class="text-[10px] text-outline uppercase font-bold tracking-tighter">
            {{ filteredFindings.length }} findings in {{ fileGroups.length }} files
          </span>
        </div>
      </div>

      <!-- File Cards Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        <div
          v-for="group in fileGroups"
          :key="group.filePath"
          class="bg-surface-container-low p-6 rounded-xl border border-outline-variant/5 hover:border-primary/20 transition-all duration-300 cursor-pointer group relative"
          @click="openFile(group.filePath)"
        >
          <!-- File Path & Branch -->
          <div class="flex justify-between items-start mb-4">
            <div class="flex items-center gap-2 text-outline text-xs font-mono">
              <span class="material-symbols-outlined text-sm">description</span>
              {{ group.filePath.split('/').pop() }}
            </div>
            <span class="bg-surface-container-highest text-outline text-[10px] px-2 py-0.5 rounded font-medium">
              {{ group.branch.split('/').pop() }}
            </span>
          </div>

          <!-- Full path -->
          <p class="text-on-surface-variant text-xs font-mono mb-4 truncate">
            {{ group.filePath }}
          </p>

          <!-- Category Badges -->
          <div class="flex flex-wrap gap-2 mb-4">
            <span
              v-for="cat in group.categories"
              :key="cat"
              :class="['px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border', getCategoryClass(cat)]"
            >
              {{ formatCategory(cat) }}
            </span>
          </div>

          <!-- Finding Count -->
          <div class="flex items-center justify-between mt-auto">
            <div class="flex items-center gap-2">
              <span class="text-2xl font-black text-primary">{{ group.findings.length }}</span>
              <span class="text-xs text-outline">{{ group.findings.length === 1 ? 'finding' : 'findings' }}</span>
            </div>
            <div class="flex -space-x-2">
              <div
                v-for="author in group.authors.slice(0, 3)"
                :key="author"
                class="w-6 h-6 rounded-full bg-surface-container-highest flex items-center justify-center text-[10px] font-bold text-primary border-2 border-surface-container-low"
              >
                {{ author?.charAt(0).toUpperCase() }}
              </div>
            </div>
          </div>

          <!-- View Details -->
          <div class="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 transition-opacity">
            <span class="text-primary text-xs font-bold flex items-center gap-1">
              Review File
              <span class="material-symbols-outlined text-sm">arrow_forward</span>
            </span>
          </div>
        </div>

        <!-- Empty State -->
        <div
          v-if="fileGroups.length === 0 && !findingsStore.loading"
          class="col-span-full flex flex-col items-center justify-center py-16"
        >
          <span class="material-symbols-outlined text-6xl text-outline mb-4">inbox</span>
          <p class="text-on-surface-variant text-lg">No findings match your filters</p>
        </div>

        <!-- Loading State -->
        <div
          v-if="findingsStore.loading"
          class="col-span-full flex items-center justify-center py-16"
        >
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <footer class="flex justify-between items-center w-full px-8 py-4 mt-auto bg-background border-t border-outline-variant/15">
      <span class="text-xs uppercase tracking-widest text-outline">© 2024 ReviewHub</span>
      <div class="flex gap-6">
        <a href="#" class="text-xs uppercase tracking-widest text-outline hover:text-primary transition-opacity">Documentation</a>
        <a href="#" class="text-xs uppercase tracking-widest text-outline hover:text-primary transition-opacity">System Status</a>
        <a href="#" class="text-xs uppercase tracking-widest text-outline hover:text-primary transition-opacity">Privacy</a>
      </div>
    </footer>
  </AppShell>
</template>
