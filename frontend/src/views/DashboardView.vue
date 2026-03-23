<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import FindingCard from '@/components/findings/FindingCard.vue';
import { useFindingsStore } from '@/stores/findings';
import { useProjectsStore } from '@/stores/projects';

const findingsStore = useFindingsStore();
const projectsStore = useProjectsStore();

const filters = reactive({
  date: '',
  category: '',
  difficulty: '',
  author: '',
});

const hasFindings = computed(() => findingsStore.findings.length > 0);

async function loadFindings(page = 1) {
  if (!projectsStore.selectedProjectId) {
    findingsStore.findings = [];
    return;
  }

  await findingsStore.fetchFindings({
    projectId: projectsStore.selectedProjectId,
    date: filters.date || undefined,
    category: filters.category || undefined,
    difficulty: filters.difficulty || undefined,
    author: filters.author || undefined,
    page,
    limit: findingsStore.limit,
  });
}

onMounted(async () => {
  await projectsStore.fetchProjects();
  await loadFindings(1);
});

watch(
  () => projectsStore.selectedProjectId,
  async () => {
    await loadFindings(1);
  },
);

watch(
  () => [filters.date, filters.category, filters.difficulty, filters.author],
  async () => {
    await loadFindings(1);
  },
);
</script>

<template>
  <div class="app-shell flex">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="flex-1 space-y-5 p-6">
        <section>
          <h2 class="text-2xl font-semibold">Monday, March 23, 2026</h2>
          <p class="mt-1 text-sm text-text-secondary">
            {{ findingsStore.total }} pending reviews across {{ projectsStore.projects.length }} active projects
          </p>
        </section>

        <!-- Filter bar - Stitch style -->
        <section class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <!-- Category filter -->
            <div class="filter-button">
              <svg class="h-4 w-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              <select v-model="filters.category" class="filter-select">
                <option value="">Category: All</option>
                <option value="SECURITY">Security</option>
                <option value="PERFORMANCE">Performance</option>
                <option value="CODE_STYLE">Code Style</option>
                <option value="TESTING">Testing</option>
                <option value="ARCHITECTURE">Architecture</option>
                <option value="DOCUMENTATION">Documentation</option>
              </select>
              <svg class="h-4 w-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            <!-- Difficulty filter -->
            <div class="filter-button">
              <svg class="h-4 w-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <select v-model="filters.difficulty" class="filter-select">
                <option value="">Difficulty: All</option>
                <option value="BEGINNER">Beginner</option>
                <option value="INTERMEDIATE">Intermediate</option>
                <option value="ADVANCED">Advanced</option>
              </select>
              <svg class="h-4 w-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            <!-- Author filter -->
            <div class="filter-button">
              <svg class="h-4 w-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              <select v-model="filters.author" class="filter-select">
                <option value="">Author: All</option>
                <option value="alice">alice</option>
                <option value="bob">bob</option>
              </select>
              <svg class="h-4 w-4 text-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          <!-- Results count -->
          <span class="text-xs uppercase tracking-wider text-text-secondary">
            Showing {{ findingsStore.findings.length }} of {{ findingsStore.total }} findings
          </span>
        </section>

        <section class="space-y-4">
          <h3 class="text-lg font-semibold">Findings</h3>
          <div v-if="findingsStore.loading" class="grid gap-4">
            <div v-for="index in 3" :key="index" class="h-32 animate-pulse rounded-lg border border-border bg-bg-card" />
          </div>
          <p v-else-if="!hasFindings" class="rounded-lg border border-border bg-bg-card p-4 text-sm text-text-secondary">
            No findings for the selected filters.
          </p>
          <div v-else class="grid gap-4 xl:grid-cols-2">
            <FindingCard v-for="finding in findingsStore.findings" :key="finding.id" :finding="finding" />
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              class="rounded-md border border-border px-3 py-1 text-sm text-text-secondary transition hover:border-primary hover:text-primary disabled:opacity-50"
              :disabled="findingsStore.page <= 1 || findingsStore.loading"
              @click="loadFindings(findingsStore.page - 1)"
            >
              Prev
            </button>
            <span class="text-xs text-text-secondary">Page {{ findingsStore.page }} / {{ findingsStore.totalPages }}</span>
            <button
              class="rounded-md border border-border px-3 py-1 text-sm text-text-secondary transition hover:border-primary hover:text-primary disabled:opacity-50"
              :disabled="findingsStore.page >= findingsStore.totalPages || findingsStore.loading"
              @click="loadFindings(findingsStore.page + 1)"
            >
              Next
            </button>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>
