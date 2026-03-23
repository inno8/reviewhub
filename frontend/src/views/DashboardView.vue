<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import CalendarWidget from '@/components/calendar/CalendarWidget.vue';
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
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="grid flex-1 gap-6 p-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section class="space-y-4">
          <div class="flex flex-wrap items-end gap-3">
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Project</label>
              <select
                :value="projectsStore.selectedProjectId ?? ''"
                class="rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-sm"
                @change="projectsStore.setSelectedProject(($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null)"
              >
                <option disabled value="">Select project</option>
                <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
                  {{ project.displayName }}
                </option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Category</label>
              <select v-model="filters.category" class="rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-sm">
                <option value="">All</option>
                <option value="SECURITY">Security</option>
                <option value="PERFORMANCE">Performance</option>
                <option value="CODE_STYLE">Code Style</option>
                <option value="TESTING">Testing</option>
                <option value="ARCHITECTURE">Architecture</option>
                <option value="DOCUMENTATION">Documentation</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Difficulty</label>
              <select v-model="filters.difficulty" class="rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-sm">
                <option value="">All</option>
                <option value="BEGINNER">Beginner</option>
                <option value="INTERMEDIATE">Intermediate</option>
                <option value="ADVANCED">Advanced</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Author</label>
              <input
                v-model="filters.author"
                type="text"
                placeholder="e.g. alice"
                class="rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-sm"
              />
            </div>
          </div>
          <h2 class="text-lg font-semibold">Findings</h2>
          <div v-if="findingsStore.loading" class="grid gap-4">
            <div v-for="index in 3" :key="index" class="h-28 animate-pulse rounded-xl border border-dark-border bg-dark-card" />
          </div>
          <p v-else-if="!hasFindings" class="rounded-xl border border-dark-border bg-dark-card p-4 text-sm text-text-secondary">
            No findings for the selected filters.
          </p>
          <div v-else class="grid gap-4">
            <FindingCard v-for="finding in findingsStore.findings" :key="finding.id" :finding="finding" />
          </div>
          <div class="flex items-center justify-end gap-2">
            <button
              class="rounded border border-dark-border px-3 py-1 text-sm disabled:opacity-50"
              :disabled="findingsStore.page <= 1 || findingsStore.loading"
              @click="loadFindings(findingsStore.page - 1)"
            >
              Prev
            </button>
            <span class="text-xs text-text-secondary">Page {{ findingsStore.page }} / {{ findingsStore.totalPages }}</span>
            <button
              class="rounded border border-dark-border px-3 py-1 text-sm disabled:opacity-50"
              :disabled="findingsStore.page >= findingsStore.totalPages || findingsStore.loading"
              @click="loadFindings(findingsStore.page + 1)"
            >
              Next
            </button>
          </div>
        </section>
        <section class="space-y-4">
          <CalendarWidget
            :project-id="projectsStore.selectedProjectId"
            @select-date="(date) => { filters.date = date; }"
          />
        </section>
      </main>
    </div>
  </div>
</template>
