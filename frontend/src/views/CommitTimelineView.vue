<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip as ChartTooltip,
} from 'chart.js';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, ChartTooltip);

const router = useRouter();
const route = useRoute();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

// View toggle: 'list' | 'chart'
const viewMode = ref<'list' | 'chart'>('list');

const evaluations = ref<any[]>([]);
const loading = ref(false);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const searchQuery = ref('');
const dateFilter = ref<string | null>(null);

// Chart data
const chartData = ref<any[]>([]);
const chartLoading = ref(false);

// Chart date navigation — defaults to today
function localDateStr(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const chartDate = ref(localDateStr(new Date()));

function formatChartDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

function isToday(iso: string): boolean {
  return iso === localDateStr(new Date());
}

function chartPrevDay() {
  const d = new Date(chartDate.value + 'T00:00:00');
  d.setDate(d.getDate() - 1);
  chartDate.value = localDateStr(d);
}

function chartNextDay() {
  if (isToday(chartDate.value)) return;
  const d = new Date(chartDate.value + 'T00:00:00');
  d.setDate(d.getDate() + 1);
  chartDate.value = localDateStr(d);
}

function chartGoToday() {
  chartDate.value = localDateStr(new Date());
}

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

function deltaColor(delta: number | null): string {
  if (delta == null) return '';
  if (delta > 0) return 'text-emerald-500';
  if (delta < 0) return 'text-error';
  return 'text-outline';
}

function deltaBg(delta: number | null): string {
  if (delta == null) return '';
  if (delta > 0) return 'bg-emerald-500/10';
  if (delta < 0) return 'bg-error/10';
  return 'bg-outline/10';
}

function deltaIcon(delta: number | null): string {
  if (delta == null) return '';
  if (delta > 0) return 'trending_up';
  if (delta < 0) return 'trending_down';
  return 'trending_flat';
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

// Compute deltas for list view evaluations (sorted newest first)
const evaluationsWithDelta = computed(() => {
  const items = filteredEvaluations.value;
  return items.map((ev, i) => {
    // Items are newest-first, so next item in array is the previous commit
    const prev = items[i + 1];
    const delta = (ev.overall_score != null && prev?.overall_score != null)
      ? Math.round((ev.overall_score - prev.overall_score) * 10) / 10
      : null;
    return { ...ev, delta };
  });
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

async function loadChart() {
  chartLoading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId;
    const { data } = await api.evaluations.chart({
      ...(projectId != null ? { projectId } : {}),
      ...(selectedAuthorId.value ? { author: selectedAuthorId.value } : {}),
      date: chartDate.value,
    });
    chartData.value = data;
  } catch (e) {
    console.error(e);
  } finally {
    chartLoading.value = false;
  }
}

// Chart.js config
const chartConfig = computed(() => {
  const items = chartData.value;
  const labels = items.map((d: any) => {
    const dt = new Date(d.created_at);
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  });
  const scores = items.map((d: any) => d.overall_score);

  return {
    data: {
      labels,
      datasets: [
        {
          label: 'Score',
          data: scores,
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.08)',
          pointBackgroundColor: items.map((d: any) => {
            if (d.overall_score >= 70) return '#10b981';
            if (d.overall_score >= 50) return '#eab308';
            return '#ef4444';
          }),
          pointBorderColor: '#1e1e2e',
          pointBorderWidth: 2,
          pointRadius: 6,
          pointHoverRadius: 10,
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index' as const,
        intersect: false,
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 11 } },
        },
        x: {
          grid: { display: false },
          ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 11 }, maxRotation: 45 },
        },
      },
      plugins: {
        tooltip: {
          enabled: false,
          external: externalTooltip,
        },
      },
    },
  };
});

// Tooltip state
const tooltipData = ref<any>(null);
const tooltipPos = ref({ x: 0, y: 0 });

function externalTooltip(context: any) {
  const { tooltip } = context;
  if (tooltip.opacity === 0) {
    tooltipData.value = null;
    return;
  }
  const idx = tooltip.dataPoints?.[0]?.dataIndex;
  if (idx == null || !chartData.value[idx]) {
    tooltipData.value = null;
    return;
  }
  tooltipData.value = chartData.value[idx];
  const { chart } = context;
  const canvasRect = chart.canvas.getBoundingClientRect();
  tooltipPos.value = {
    x: canvasRect.left + tooltip.caretX,
    y: canvasRect.top + tooltip.caretY,
  };
}

// Chart summary computed
const chartAvgScore = computed(() => {
  if (!chartData.value.length) return null;
  const sum = chartData.value.reduce((a: number, d: any) => a + d.overall_score, 0);
  return Math.round((sum / chartData.value.length) * 10) / 10;
});

const chartOverallDelta = computed(() => {
  if (chartData.value.length < 2) return null;
  const first = chartData.value[0].overall_score;
  const last = chartData.value[chartData.value.length - 1].overall_score;
  return Math.round((last - first) * 10) / 10;
});

const chartBest = computed(() => {
  if (!chartData.value.length) return '—';
  return Math.round(Math.max(...chartData.value.map((d: any) => d.overall_score)));
});

const chartTotalFindings = computed(() => {
  return chartData.value.reduce((a: number, d: any) => a + (d.finding_count || 0), 0);
});

const chartTopSkills = computed(() => {
  const counts: Record<string, number> = {};
  for (const d of chartData.value) {
    for (const sk of (d.top_skills || [])) {
      counts[sk.name] = (counts[sk.name] || 0) + sk.count;
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, count]) => ({ name, count }));
});

function toggleView() {
  viewMode.value = viewMode.value === 'list' ? 'chart' : 'list';
  if (viewMode.value === 'chart' && chartData.value.length === 0) {
    loadChart();
  }
}

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (authStore.isAdmin) await loadAdminUsers();
  if (route.query.date) {
    dateFilter.value = String(route.query.date);
  }
  await load();
});

watch(() => route.query.date, (newDate) => {
  dateFilter.value = newDate ? String(newDate) : null;
  page.value = 1;
  load();
});

watch(selectedAuthorId, () => {
  page.value = 1;
  load();
  if (viewMode.value === 'chart') loadChart();
});

watch(() => projectsStore.selectedProjectId, () => {
  page.value = 1;
  load();
  if (viewMode.value === 'chart') loadChart();
});

watch(page, () => load());

watch(chartDate, () => {
  if (viewMode.value === 'chart') loadChart();
});

function openEvaluation(ev: any) {
  if (!ev.findings?.length && !ev.finding_count) return;
  router.push({ name: 'file-review', query: { evaluationId: ev.id } });
}

function openChartEvaluation(ev: any) {
  if (!ev.finding_count) return;
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
          <!-- View toggle (first) -->
          <button
            @click="toggleView"
            class="flex items-center gap-2 px-3 py-2 rounded-lg border transition-all"
            :class="viewMode === 'chart'
              ? 'bg-primary/15 border-primary/30 text-primary'
              : 'bg-surface-container border-outline-variant/20 text-outline hover:text-on-surface'"
            :title="viewMode === 'list' ? 'Switch to chart view' : 'Switch to list view'"
          >
            <span class="material-symbols-outlined text-sm">
              {{ viewMode === 'list' ? 'show_chart' : 'view_list' }}
            </span>
            <span class="text-sm font-medium hidden sm:inline">{{ viewMode === 'list' ? 'Chart' : 'List' }}</span>
          </button>

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

      <!-- ============ LIST VIEW ============ -->
      <template v-if="viewMode === 'list'">
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
              v-for="ev in evaluationsWithDelta"
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
                      <!-- Delta badge -->
                      <span
                        v-if="ev.delta != null && ev.delta !== 0"
                        class="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-bold"
                        :class="[deltaBg(ev.delta), deltaColor(ev.delta)]"
                      >
                        <span class="material-symbols-outlined" style="font-size: 12px">{{ deltaIcon(ev.delta) }}</span>
                        {{ ev.delta > 0 ? '+' : '' }}{{ ev.delta }}
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

                    <!-- Delta column -->
                    <div v-if="ev.delta != null" class="text-center hidden sm:block">
                      <p class="text-[10px] text-outline uppercase tracking-wider">Trend</p>
                      <p class="text-lg font-black flex items-center justify-center gap-0.5" :class="deltaColor(ev.delta)">
                        <span class="material-symbols-outlined text-sm">{{ deltaIcon(ev.delta) }}</span>
                        {{ ev.delta > 0 ? '+' : '' }}{{ ev.delta }}
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

                <!-- Files changed bar -->
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
      </template>

      <!-- ============ CHART VIEW ============ -->
      <template v-if="viewMode === 'chart'">
        <div v-if="chartLoading" class="flex items-center justify-center py-24 gap-3 text-outline">
          <span class="material-symbols-outlined animate-spin text-3xl">progress_activity</span>
          Loading chart data…
        </div>

        <div v-else-if="!chartData.length" class="flex flex-col items-center py-24 gap-4">
          <span class="material-symbols-outlined text-6xl text-outline">show_chart</span>
          <h3 class="text-xl font-bold">No commits on {{ formatChartDate(chartDate) }}</h3>
          <p class="text-outline text-sm">Try navigating to a different day or push code to see your score progression.</p>
          <div class="flex items-center gap-2 mt-2">
            <button @click="chartPrevDay"
              class="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-outline hover:text-on-surface transition-all">
              <span class="material-symbols-outlined text-sm">chevron_left</span>
              Previous day
            </button>
            <button v-if="!isToday(chartDate)" @click="chartGoToday"
              class="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary/15 border border-primary/30 text-sm text-primary transition-all">
              <span class="material-symbols-outlined text-sm">today</span>
              Go to today
            </button>
            <button @click="chartNextDay" :disabled="isToday(chartDate)"
              class="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/20 text-sm text-outline hover:text-on-surface transition-all disabled:opacity-30">
              Next day
              <span class="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </div>
        </div>

        <div v-else>
          <!-- Chart area -->
          <div class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6 mb-8">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h2 class="text-lg font-bold text-on-surface">Score Progression</h2>
                <p class="text-xs text-outline">{{ chartData.length }} evaluated commit{{ chartData.length !== 1 ? 's' : '' }} on {{ formatChartDate(chartDate) }}</p>
              </div>

              <!-- Day navigation -->
              <div class="flex items-center gap-2">
                <button @click="chartPrevDay"
                  class="flex items-center justify-center w-8 h-8 rounded-lg bg-surface-container border border-outline-variant/20 text-outline hover:text-on-surface hover:border-primary/30 transition-all"
                  title="Previous day">
                  <span class="material-symbols-outlined text-sm">chevron_left</span>
                </button>

                <button @click="chartGoToday"
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all"
                  :class="isToday(chartDate)
                    ? 'bg-primary/15 border-primary/30 text-primary'
                    : 'bg-surface-container border-outline-variant/20 text-outline hover:text-on-surface hover:border-primary/30'"
                  title="Go to today">
                  <span class="material-symbols-outlined text-sm">today</span>
                  Today
                </button>

                <button @click="chartNextDay"
                  :disabled="isToday(chartDate)"
                  class="flex items-center justify-center w-8 h-8 rounded-lg bg-surface-container border border-outline-variant/20 text-outline hover:text-on-surface hover:border-primary/30 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Next day">
                  <span class="material-symbols-outlined text-sm">chevron_right</span>
                </button>
              </div>

              <!-- Legend -->
              <div class="flex items-center gap-4 text-xs text-outline">
                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-emerald-500"></span> Good (70+)</span>
                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-yellow-500"></span> OK (50-69)</span>
                <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-error"></span> Needs work (&lt;50)</span>
              </div>
            </div>
            <div class="relative h-[500px]">
              <Line :data="chartConfig.data" :options="chartConfig.options" />

              <!-- Custom tooltip overlay -->
              <Teleport to="body">
                <div
                  v-if="tooltipData"
                  class="fixed z-[9999] pointer-events-none"
                  :style="{ left: tooltipPos.x + 'px', top: (tooltipPos.y - 10) + 'px', transform: 'translate(-50%, -100%)' }"
                >
                  <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-xl shadow-2xl p-4 min-w-[280px] max-w-[340px]">
                    <!-- Header -->
                    <div class="flex items-center justify-between mb-3">
                      <code class="px-2 py-0.5 bg-primary/10 rounded text-xs text-primary font-mono">
                        {{ shortSha(tooltipData.commit_sha) }}
                      </code>
                      <div class="flex items-center gap-2">
                        <span class="text-2xl font-black" :class="scoreColor(tooltipData.overall_score)">
                          {{ tooltipData.overall_score }}
                        </span>
                        <span
                          v-if="tooltipData.delta != null && tooltipData.delta !== 0"
                          class="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-xs font-bold"
                          :class="[deltaBg(tooltipData.delta), deltaColor(tooltipData.delta)]"
                        >
                          <span class="material-symbols-outlined" style="font-size: 14px">{{ deltaIcon(tooltipData.delta) }}</span>
                          {{ tooltipData.delta > 0 ? '+' : '' }}{{ tooltipData.delta }}
                        </span>
                      </div>
                    </div>

                    <!-- Commit message -->
                    <p class="text-sm text-on-surface font-medium line-clamp-2 mb-3">
                      {{ tooltipData.commit_message || '(no message)' }}
                    </p>

                    <!-- Stats row -->
                    <div class="flex items-center gap-3 text-xs text-outline mb-3">
                      <span>{{ formatDate(tooltipData.created_at) }}</span>
                      <span>·</span>
                      <span>{{ tooltipData.finding_count }} finding{{ tooltipData.finding_count !== 1 ? 's' : '' }}</span>
                      <span v-if="tooltipData.fixed_count">· {{ tooltipData.fixed_count }} fixed</span>
                    </div>

                    <!-- Severity breakdown -->
                    <div v-if="Object.keys(tooltipData.severities || {}).length" class="flex items-center gap-2 mb-3 flex-wrap">
                      <span
                        v-for="(count, sev) in tooltipData.severities"
                        :key="sev"
                        class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                        :class="{
                          'bg-error/15 text-error': sev === 'critical' || sev === 'error',
                          'bg-yellow-500/15 text-yellow-500': sev === 'warning',
                          'bg-primary/10 text-primary': sev === 'info' || sev === 'suggestion',
                        }"
                      >
                        {{ count }} {{ sev }}
                      </span>
                    </div>

                    <!-- Skills affected -->
                    <div v-if="tooltipData.top_skills?.length">
                      <p class="text-[10px] text-outline uppercase tracking-wider mb-1.5">Skills affected</p>
                      <div class="flex flex-wrap gap-1.5">
                        <span
                          v-for="sk in tooltipData.top_skills"
                          :key="sk.name"
                          class="px-2 py-0.5 bg-surface-container rounded-full text-xs text-on-surface-variant"
                        >
                          {{ sk.name }} <span class="text-outline">({{ sk.count }})</span>
                        </span>
                      </div>
                    </div>

                    <!-- Improvement indicator -->
                    <div v-if="tooltipData.delta != null" class="mt-3 pt-3 border-t border-outline-variant/10">
                      <div class="flex items-center gap-2 text-xs" :class="deltaColor(tooltipData.delta)">
                        <span class="material-symbols-outlined text-sm">{{ deltaIcon(tooltipData.delta) }}</span>
                        <span v-if="tooltipData.delta > 0" class="font-medium">
                          This commit improved the score by {{ tooltipData.delta }} points
                        </span>
                        <span v-else-if="tooltipData.delta < 0" class="font-medium">
                          Score dropped by {{ Math.abs(tooltipData.delta) }} points vs previous commit
                        </span>
                        <span v-else class="font-medium text-outline">Score unchanged from previous commit</span>
                      </div>
                    </div>
                  </div>
                </div>
              </Teleport>
            </div>
          </div>

          <!-- Summary cards below chart -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-4 text-center">
              <p class="text-[10px] text-outline uppercase tracking-wider mb-1">Avg Score</p>
              <p class="text-2xl font-black" :class="scoreColor(chartAvgScore)">
                {{ chartAvgScore != null ? Math.round(chartAvgScore) : '—' }}
              </p>
            </div>
            <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-4 text-center">
              <p class="text-[10px] text-outline uppercase tracking-wider mb-1">Overall Trend</p>
              <p class="text-2xl font-black" :class="deltaColor(chartOverallDelta)">
                <span class="material-symbols-outlined text-lg align-middle">{{ deltaIcon(chartOverallDelta) }}</span>
                {{ chartOverallDelta != null ? (chartOverallDelta > 0 ? '+' : '') + chartOverallDelta : '—' }}
              </p>
            </div>
            <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-4 text-center">
              <p class="text-[10px] text-outline uppercase tracking-wider mb-1">Best Score</p>
              <p class="text-2xl font-black text-emerald-500">{{ chartBest }}</p>
            </div>
            <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-4 text-center">
              <p class="text-[10px] text-outline uppercase tracking-wider mb-1">Total Findings</p>
              <p class="text-2xl font-black text-error">{{ chartTotalFindings }}</p>
            </div>
          </div>

          <!-- Top affected skills across all chart data -->
          <div v-if="chartTopSkills.length" class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
            <h3 class="text-sm font-bold text-on-surface mb-4">Most Affected Skills</h3>
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              <div
                v-for="sk in chartTopSkills"
                :key="sk.name"
                class="bg-surface-container rounded-xl p-3 text-center"
              >
                <p class="text-lg font-black text-on-surface">{{ sk.count }}</p>
                <p class="text-xs text-outline mt-1">{{ sk.name }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </AppShell>
</template>
