<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const route = useRoute();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const evaluations = ref<any[]>([]);
const loading = ref(false);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const searchQuery = ref('');
const dateFilter = ref<string | null>(null);

// Admin user selector
const adminUsers = ref<any[]>([]);
const selectedAuthorId = ref<number | null>(null);

async function loadAdminUsers() {
  if (!authStore.isAdmin) return;
  try {
    const { data } = await api.users.adminStats({});
    adminUsers.value = data;
  } catch { adminUsers.value = []; }
}

const totalPages = computed(() => Math.ceil(total.value / pageSize));

function scoreColor(score: number | null): string {
  if (score == null) return 'text-outline';
  if (score >= 70) return 'text-emerald-500';
  if (score >= 50) return 'text-yellow-500';
  return 'text-error';
}

function scoreBg(score: number | null): string {
  if (score == null) return 'bg-outline/10';
  if (score >= 70) return 'bg-emerald-500/15';
  if (score >= 50) return 'bg-yellow-500/15';
  return 'bg-error/15';
}

function complexityColor(complexity: string): string {
  if (complexity === 'complex') return 'bg-error/15 text-error';
  if (complexity === 'medium') return 'bg-yellow-500/15 text-yellow-500';
  return 'bg-primary/10 text-primary';
}

function formatDate(dt: string): string {
  const d = new Date(dt);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function shortSha(sha: string): string {
  return sha ? sha.substring(0, 7) : '—';
}

const filteredEvaluations = computed(() => {
  if (!searchQuery.value.trim()) return evaluations.value;
  const q = searchQuery.value.toLowerCase();
  return evaluations.value.filter(
    e =>
      (e.commit_message || '').toLowerCase().includes(q) ||
      (e.commit_sha || '').toLowerCase().includes(q) ||
      (e.branch || '').toLowerCase().includes(q),
  );
});

async function load() {
  loading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId;
    const { data } = await api.evaluations.list({
      ...(projectId != null ? { projectId } : {}),
      ...(selectedAuthorId.value ? { author: selectedAuthorId.value } : {}),
      ...(dateFilter.value ? { date: dateFilter.value } : {}),
      limit: pageSize,
      page: page.value,
    });
    const items = data.results ?? data ?? [];
    evaluations.value = items;
    total.value = data.count ?? items.length;
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (authStore.isAdmin) await loadAdminUsers();
  // Read date filter from query param
  if (route.query.date) {
    dateFilter.value = String(route.query.date);
  }
  await load();
});

// Watch for route query changes (e.g. calendar click while already on timeline)
watch(() => route.query.date, (newDate) => {
  dateFilter.value = newDate ? String(newDate) : null;
  page.value = 1;
  load();
});

watch(selectedAuthorId, () => { page.value = 1; load(); });

watch(() => projectsStore.selectedProjectId, () => {
  page.value = 1;
  load();
});

watch(page, () => load());

function openEvaluation(ev: any) {
  if (!ev.findings?.length && !ev.finding_count) return;
  router.push({ name: 'file-review', query: { evaluationId: ev.id } });
}

function prevPage() { if (page.value > 1) page.value--; }
function nextPage() { if (page.value < totalPages.value) page.value++; }
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Header -->
      <section class="flex flex-col md:flex-row items-start md:items-end justify-between gap-6 mb-10">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Commit History</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">Commit Timeline</h1>
          <p class="text-outline text-sm">Chronological view of all evaluated commits with scores and findings</p>
        </div>

        <div class="flex items-center gap-3">
          <!-- Admin: developer filter -->
          <div v-if="authStore.isAdmin && adminUsers.length" class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
            <span class="material-symbols-outlined text-sm text-outline">person</span>
            <select v-model="selectedAuthorId"
              class="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer p-0">
              <option :value="null">All Developers</option>
              <option v-for="u in adminUsers" :key="u.id" :value="u.id">{{ u.display_name || u.username }}</option>
            </select>
          </div>

          <div v-if="projectsStore.projects.length > 1" class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
            <span class="material-symbols-outlined text-sm text-outline">folder</span>
            <select
              :value="projectsStore.selectedProjectId"
              @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
              class="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer p-0"
            >
              <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
            </select>
          </div>

          <!-- Date filter badge -->
          <div v-if="dateFilter"
            class="flex items-center gap-2 px-3 py-2 bg-primary/10 rounded-lg border border-primary/20">
            <span class="material-symbols-outlined text-sm text-primary">calendar_today</span>
            <span class="text-sm text-primary font-medium">{{ dateFilter }}</span>
            <button @click="dateFilter = null; router.replace({ query: {} }); page = 1; load();"
              class="text-primary hover:text-error transition-colors">
              <span class="material-symbols-outlined text-sm">close</span>
            </button>
          </div>

          <div class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
            <span class="material-symbols-outlined text-sm text-outline">search</span>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search commits…"
              class="bg-transparent border-none text-sm text-on-surface focus:ring-0 outline-none w-44"
            />
          </div>
        </div>
      </section>

      <!-- Summary badge -->
      <div v-if="total" class="mb-6 flex items-center gap-2 text-sm text-outline">
        <span class="material-symbols-outlined text-sm">analytics</span>
        {{ total }} evaluated commit{{ total !== 1 ? 's' : '' }} found
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-24 gap-3 text-outline">
        <span class="material-symbols-outlined animate-spin text-3xl">progress_activity</span>
        Loading commits…
      </div>

      <!-- Empty state -->
      <div v-else-if="!filteredEvaluations.length" class="flex flex-col items-center py-24 gap-4">
        <span class="material-symbols-outlined text-6xl text-outline">commit</span>
        <h3 class="text-xl font-bold">No commits yet</h3>
        <p class="text-outline text-sm">Push code or run batch analysis to see your commit timeline.</p>
      </div>

      <!-- Timeline list -->
      <div v-else class="relative">
        <!-- Vertical track -->
        <div class="absolute left-[22px] top-0 bottom-0 w-0.5 bg-outline-variant/15 rounded-full" />

        <div class="space-y-4">
          <article
            v-for="ev in filteredEvaluations"
            :key="ev.id"
            class="relative flex gap-6 group"
          >
            <!-- Dot on track -->
            <div class="relative z-10 flex-shrink-0 mt-3">
              <div
                class="w-11 h-11 rounded-full border-2 border-outline-variant/20 bg-surface-container-low flex items-center justify-center text-xs font-black transition-all"
                :class="[scoreBg(ev.overall_score), scoreColor(ev.overall_score)]"
              >
                {{ ev.overall_score != null ? Math.round(ev.overall_score) : '?' }}
              </div>
            </div>

            <!-- Card -->
            <div
              class="flex-1 bg-surface-container-low rounded-2xl border border-outline-variant/10 p-5 hover:border-primary/20 transition-all cursor-pointer"
              @click="openEvaluation(ev)"
            >
              <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                <!-- Left: commit info -->
                <div class="flex-1 min-w-0">
                  <div class="flex flex-wrap items-center gap-2 mb-2">
                    <code class="px-2 py-0.5 bg-surface-container-lowest rounded-md text-xs text-primary font-mono border border-outline-variant/15">
                      {{ shortSha(ev.commit_sha) }}
                    </code>
                    <span
                      v-if="ev.commit_complexity"
                      class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                      :class="complexityColor(ev.commit_complexity)"
                    >
                      {{ ev.commit_complexity }}
                    </span>
                    <span class="px-2 py-0.5 bg-surface-container rounded-full text-[10px] text-outline font-medium">
                      {{ ev.branch || 'main' }}
                    </span>
                  </div>
                  <p class="text-sm font-semibold text-on-surface line-clamp-2 mb-1">
                    {{ ev.commit_message || '(no message)' }}
                  </p>
                  <p class="text-xs text-outline">
                    {{ formatDate(ev.created_at) }}
                    <span v-if="ev.author?.display_name"> · {{ ev.author.display_name }}</span>
                  </p>
                </div>

                <!-- Right: stats -->
                <div class="flex items-center gap-4 flex-shrink-0">
                  <div class="text-center">
                    <p class="text-[10px] text-outline uppercase tracking-wider">Score</p>
                    <p class="text-2xl font-black" :class="scoreColor(ev.overall_score)">
                      {{ ev.overall_score != null ? Math.round(ev.overall_score) : '—' }}
                    </p>
                  </div>

                  <div class="text-center">
                    <p class="text-[10px] text-outline uppercase tracking-wider">Findings</p>
                    <p class="text-2xl font-black" :class="(ev.finding_count || 0) > 0 ? 'text-error' : 'text-emerald-500'">
                      {{ ev.finding_count || 0 }}
                    </p>
                  </div>

                  <div class="text-center hidden sm:block">
                    <p class="text-[10px] text-outline uppercase tracking-wider">Changed</p>
                    <p class="text-sm font-bold text-on-surface-variant">
                      +{{ ev.lines_added || 0 }} / -{{ ev.lines_removed || 0 }}
                    </p>
                  </div>

                  <span class="material-symbols-outlined text-outline group-hover:text-primary transition-colors">
                    chevron_right
                  </span>
                </div>
              </div>

              <!-- Files changed bar (optional visual) -->
              <div v-if="ev.files_changed" class="mt-3 flex items-center gap-2 text-xs text-outline">
                <span class="material-symbols-outlined text-xs">description</span>
                {{ ev.files_changed }} file{{ ev.files_changed !== 1 ? 's' : '' }} changed
                <span v-if="ev.complexity_score != null" class="ml-1">
                  · complexity {{ ev.complexity_score.toFixed(1) }}
                </span>
              </div>
            </div>
          </article>
        </div>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-4 mt-10">
          <button
            :disabled="page === 1"
            class="flex items-center gap-2 px-4 py-2 rounded-xl border border-outline-variant/20 text-sm disabled:opacity-40 hover:border-primary/40 transition-colors"
            @click="prevPage"
          >
            <span class="material-symbols-outlined text-sm">arrow_back</span>
            Previous
          </button>
          <span class="text-sm text-outline">Page {{ page }} of {{ totalPages }}</span>
          <button
            :disabled="page === totalPages"
            class="flex items-center gap-2 px-4 py-2 rounded-xl border border-outline-variant/20 text-sm disabled:opacity-40 hover:border-primary/40 transition-colors"
            @click="nextPage"
          >
            Next
            <span class="material-symbols-outlined text-sm">arrow_forward</span>
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>
