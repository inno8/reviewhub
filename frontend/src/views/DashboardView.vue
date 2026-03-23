<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import FindingCard from '@/components/findings/FindingCard.vue';
import Dropdown from '@/components/common/Dropdown.vue';
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

        <section class="surface-card p-4">
          <div class="grid gap-3 md:grid-cols-4">
            <div>
              <label class="field-label">Date</label>
              <input
                v-model="filters.date"
                type="date"
                class="h-10 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm text-text-primary outline-none transition focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label class="field-label">Category</label>
              <Dropdown v-model="filters.category">
                <option value="">All categories</option>
                <option value="SECURITY">Security</option>
                <option value="PERFORMANCE">Performance</option>
                <option value="CODE_STYLE">Code Style</option>
                <option value="TESTING">Testing</option>
                <option value="ARCHITECTURE">Architecture</option>
                <option value="DOCUMENTATION">Documentation</option>
              </Dropdown>
            </div>
            <div>
              <label class="field-label">Difficulty</label>
              <Dropdown v-model="filters.difficulty">
                <option value="">All levels</option>
                <option value="BEGINNER">Beginner</option>
                <option value="INTERMEDIATE">Intermediate</option>
                <option value="ADVANCED">Advanced</option>
              </Dropdown>
            </div>
            <div>
              <label class="field-label">Author</label>
              <input
                v-model="filters.author"
                type="text"
                placeholder="e.g. alice"
                class="h-10 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm text-text-primary outline-none transition focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>
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
