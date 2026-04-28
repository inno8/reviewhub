<script setup lang="ts">
/**
 * CohortOverviewView — /grading/cohorts/:id/overview
 *
 * Teacher's answer to "what's happening in my klas this week?" — per-cohort
 * aggregation. Distinct from the grading inbox (per-PR) and the student
 * profile (one-student deep-dive).
 *
 * Wires to: GET /api/grading/cohorts/<id>/overview/
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'vue-chartjs';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, Tooltip, Legend);

// ── Types ──────────────────────────────────────────────────────────────
interface WeakestCriterion {
  skill_slug: string;
  display_name: string;
  kerntaak: string | null;
  avg_score: number;
  students_below_niveau: number;
  recurring_patterns_count: number;
  trend: 'up' | 'down' | 'stable';
}
interface CohortPattern {
  pattern_key: string;
  pattern_type: string;
  affected_student_count: number;
  total_frequency: number;
  last_seen_days_ago: number | null;
}
interface StudentRow {
  id: number;
  name: string;
  email: string;
  eindniveau: number | null;
  band: 'onvoldoende' | 'net-aan' | 'voldoende' | 'goed' | null;
  trend: 'up' | 'down' | 'stable';
  last_pr_days_ago: number | null;
  prs_waiting_feedback: number;
  strongest_criterion: { slug: string; score: number } | null;
  weakest_criterion: { slug: string; score: number } | null;
}
interface WeekBucket {
  week_start: string;
  pr_count: number;
  avg_score: number | null;
}
interface Overview {
  cohort: {
    id: number;
    name: string;
    course_name: string | null;
    student_count: number;
    org_slug: string | null;
  };
  activity: {
    prs_this_sprint: number;
    prs_waiting_feedback: number;
    prs_posted_this_sprint: number;
  };
  weakest_criteria: WeakestCriterion[];
  cohort_patterns: CohortPattern[];
  students: StudentRow[];
  weekly_activity: WeekBucket[];
}

// ── State ──────────────────────────────────────────────────────────────
const route = useRoute();
const router = useRouter();
const cohortId = computed(() => Number(route.params.id));

const data = ref<Overview | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

type SortKey = 'name' | 'score' | 'waiting' | 'activity';
const sortKey = ref<SortKey>('score');

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const res = await api.grading.cohorts.overview(cohortId.value);
    data.value = res.data;
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Kon klas-overzicht niet laden';
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(cohortId, load);

// ── Derived ─────────────────────────────────────────────────────────────
const sortedStudents = computed<StudentRow[]>(() => {
  const list = [...(data.value?.students ?? [])];
  list.sort((a, b) => {
    switch (sortKey.value) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'score':
        return (a.eindniveau ?? 99) - (b.eindniveau ?? 99);
      case 'waiting':
        return b.prs_waiting_feedback - a.prs_waiting_feedback;
      case 'activity':
        return (a.last_pr_days_ago ?? 9999) - (b.last_pr_days_ago ?? 9999);
    }
    return 0;
  });
  return list;
});

function bandClass(band: StudentRow['band']): string {
  switch (band) {
    case 'goed':
      return 'bg-primary/15 text-primary';
    case 'voldoende':
      return 'bg-secondary/15 text-secondary';
    case 'net-aan':
      return 'bg-tertiary/15 text-tertiary';
    case 'onvoldoende':
      return 'bg-error/15 text-error';
    default:
      return 'bg-surface-container-high text-on-surface-variant';
  }
}

function bandLabel(band: StudentRow['band']): string {
  if (!band) return '—';
  if (band === 'net-aan') return 'Net aan';
  return band.charAt(0).toUpperCase() + band.slice(1);
}

function trendIcon(trend: 'up' | 'down' | 'stable'): string {
  return trend === 'up' ? 'trending_up' : trend === 'down' ? 'trending_down' : 'trending_flat';
}
function trendColor(trend: 'up' | 'down' | 'stable'): string {
  return trend === 'up' ? 'text-primary' : trend === 'down' ? 'text-error' : 'text-on-surface-variant';
}

function severityIcon(c: WeakestCriterion): string {
  if (c.avg_score < 2) return '🔴';
  if (c.avg_score < 2.5) return '🟡';
  return '🟢';
}

function formatWeekLabel(d: string): string {
  return new Date(d + 'T00:00:00').toLocaleDateString('nl-NL', { month: 'short', day: 'numeric' });
}

function daysAgoLabel(n: number | null): string {
  if (n === null || n === undefined) return 'geen PR';
  if (n === 0) return 'vandaag';
  if (n === 1) return 'gisteren';
  return `${n} dagen geleden`;
}

function openStudent(s: StudentRow) {
  router.push({ name: 'grading-student-profile', params: { id: s.id } });
}

function goBack() {
  router.push({ name: 'grading-inbox' });
}

// ── Chart data ─────────────────────────────────────────────────────────
const chartData = computed(() => {
  const buckets = data.value?.weekly_activity ?? [];
  return {
    labels: buckets.map(b => formatWeekLabel(b.week_start)),
    datasets: [
      {
        type: 'bar' as const,
        label: "PR's per week",
        data: buckets.map(b => b.pr_count),
        backgroundColor: '#a2c9ff',
        borderRadius: 4,
        yAxisID: 'y',
      },
    ],
  };
});
const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#1c2026',
      titleColor: '#dfe2eb',
      bodyColor: '#c0c7d4',
      borderColor: '#414752',
      borderWidth: 1,
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#8b919d', font: { size: 11 } },
    },
    y: {
      beginAtZero: true,
      grid: { color: 'rgba(139, 145, 157, 0.1)' },
      ticks: { color: '#8b919d', font: { size: 11 }, stepSize: 1, precision: 0 },
    },
  },
}));

// Pre-resolve one-liners for the "Te bespreken in de les" block.
const discussionPoints = computed<string[]>(() => {
  const points: string[] = [];
  for (const c of data.value?.weakest_criteria ?? []) {
    if (c.students_below_niveau >= 1) {
      points.push(
        `${c.display_name}: ${c.students_below_niveau} studenten onder niveau — hernemen in de les.`,
      );
    }
  }
  if (!points.length && data.value?.weakest_criteria?.length) {
    points.push('De klas zit rond niveau op alle criteria. Goed bezig.');
  }
  return points.slice(0, 3);
});
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <header class="flex items-start gap-4 mb-8">
          <button
            class="text-sm text-on-surface-variant hover:text-on-surface transition-colors mt-1"
            @click="goBack"
          >
            ← Nakijken
          </button>
        </header>

        <div v-if="loading" class="p-12 text-center text-outline">
          <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
          <p class="mt-2 text-sm">Klas-overzicht laden…</p>
        </div>
        <div
          v-else-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >
          {{ error }}
        </div>

        <div v-else-if="data" class="space-y-6">
          <!-- Title block -->
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight m-0">
              {{ data.cohort.name }}
            </h1>
            <p class="text-on-surface-variant mt-2 text-base">
              <span v-if="data.cohort.course_name">{{ data.cohort.course_name }} · </span>
              {{ data.cohort.student_count }} studenten ·
              {{ data.activity.prs_this_sprint }} PR's deze sprint ·
              {{ data.activity.prs_waiting_feedback }} wachten op feedback
            </p>
          </div>

          <!-- ══════ Wat deze klas nu nodig heeft ══════ -->
          <section class="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
            <header class="flex items-baseline justify-between mb-4">
              <h2 class="text-xl font-bold text-on-surface m-0">Wat deze klas nu nodig heeft</h2>
              <span class="text-xs uppercase tracking-widest text-outline">Top 3 zwakste criteria</span>
            </header>
            <p class="text-xs text-on-surface-variant mb-4 m-0">
              Klas-gemiddelde over {{ data.cohort.student_count }} studenten in deze sprint.
              Score 1-4 vertaalt naar Bayesian-score &times;25.
            </p>

            <div v-if="!data.weakest_criteria.length" class="text-sm text-outline py-4">
              Nog geen rubric-data beschikbaar.
            </div>
            <ul v-else class="space-y-3">
              <li
                v-for="c in data.weakest_criteria"
                :key="c.skill_slug"
                class="flex items-start gap-3"
              >
                <span class="text-xl leading-none mt-0.5">{{ severityIcon(c) }}</span>
                <div class="flex-1 min-w-0">
                  <div class="flex items-baseline gap-3 flex-wrap">
                    <span class="font-bold text-on-surface">{{ c.display_name }}</span>
                    <span
                      v-if="c.kerntaak"
                      class="px-2 py-0.5 rounded-md text-[11px] font-mono bg-surface-container-high text-on-surface-variant"
                    >
                      {{ c.kerntaak }}
                    </span>
                    <span class="text-sm tabular-nums text-on-surface-variant">
                      gem. {{ c.avg_score.toFixed(1) }}/4
                    </span>
                    <span
                      class="material-symbols-outlined text-sm"
                      :class="trendColor(c.trend)"
                    >
                      {{ trendIcon(c.trend) }}
                    </span>
                  </div>
                  <p class="text-xs text-on-surface-variant mt-1 m-0">
                    {{ c.students_below_niveau }}/{{ data.cohort.student_count }} studenten onder niveau
                    <span v-if="c.recurring_patterns_count > 0">
                      · {{ c.recurring_patterns_count }} terugkerende patronen
                    </span>
                  </p>
                </div>
              </li>
            </ul>

            <div
              v-if="discussionPoints.length"
              class="mt-6 pt-5 border-t border-outline-variant/10"
            >
              <h3 class="text-xs uppercase tracking-widest text-outline font-bold mb-2">
                Te bespreken in de les
              </h3>
              <ul class="space-y-1.5">
                <li
                  v-for="p in discussionPoints"
                  :key="p"
                  class="text-sm text-on-surface-variant before:content-['—'] before:mr-2 before:text-outline"
                >
                  {{ p }}
                </li>
              </ul>
            </div>
          </section>

          <!-- ══════ Klas-brede patronen ══════ -->
          <section class="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
            <header class="flex items-baseline justify-between mb-4">
              <h2 class="text-xl font-bold text-on-surface m-0">Klas-brede patronen</h2>
              <span class="text-xs uppercase tracking-widest text-outline">
                Bij 2+ studenten deze periode
              </span>
            </header>

            <div
              v-if="!data.cohort_patterns.length"
              class="text-sm text-outline py-4"
            >
              Geen patronen die bij meerdere studenten voorkomen. Goed nieuws.
            </div>
            <ul v-else class="divide-y divide-outline-variant/10">
              <li
                v-for="p in data.cohort_patterns"
                :key="p.pattern_key"
                class="py-3 flex items-center gap-4"
              >
                <div class="flex-1 min-w-0">
                  <div class="flex items-baseline gap-3 flex-wrap">
                    <code class="text-sm font-mono text-on-surface">{{ p.pattern_key }}</code>
                    <span
                      class="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-bold bg-surface-container-high text-on-surface-variant"
                    >
                      {{ p.pattern_type }}
                    </span>
                  </div>
                </div>
                <div class="text-right shrink-0">
                  <p class="text-sm font-bold text-on-surface tabular-nums m-0">
                    {{ p.affected_student_count }} studenten
                  </p>
                  <p class="text-xs text-outline tabular-nums m-0">
                    {{ p.total_frequency }}x · {{ p.last_seen_days_ago ?? '—' }} d
                  </p>
                </div>
              </li>
            </ul>
          </section>

          <!-- ══════ Studenten ══════ -->
          <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <header class="flex items-baseline justify-between px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-xl font-bold text-on-surface m-0">Studenten</h2>
              <div class="flex items-center gap-2 text-xs">
                <span class="text-outline">Sorteer op:</span>
                <button
                  v-for="opt in ([
                    { k: 'score', label: 'Score' },
                    { k: 'waiting', label: 'Wachten' },
                    { k: 'activity', label: 'Activiteit' },
                    { k: 'name', label: 'Naam' },
                  ] as { k: SortKey; label: string }[])"
                  :key="opt.k"
                  class="px-2.5 py-1 rounded-md transition-colors"
                  :class="sortKey === opt.k ? 'bg-surface-container-high text-primary font-bold' : 'text-on-surface-variant hover:text-on-surface'"
                  @click="sortKey = opt.k"
                >
                  {{ opt.label }}
                </button>
              </div>
            </header>

            <div v-if="!sortedStudents.length" class="p-8 text-sm text-outline text-center">
              Deze klas heeft nog geen studenten.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                    <th class="px-6 py-3">Student</th>
                    <th class="px-4 py-3">Eindniveau</th>
                    <th class="px-4 py-3">Trend</th>
                    <th class="px-4 py-3">Laatste PR</th>
                    <th class="px-4 py-3">Wachten</th>
                    <th class="px-4 py-3">Sterkste</th>
                    <th class="px-4 py-3">Zwakste</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/5">
                  <tr
                    v-for="s in sortedStudents"
                    :key="s.id"
                    class="hover:bg-surface-container-high/40 transition-colors cursor-pointer"
                    @click="openStudent(s)"
                  >
                    <td class="px-6 py-3">
                      <div class="flex items-center gap-3">
                        <span
                          class="w-8 h-8 rounded-full bg-primary/15 flex items-center justify-center text-primary text-xs font-bold shrink-0"
                        >
                          {{ s.name ? s.name[0].toUpperCase() : '?' }}
                        </span>
                        <div class="min-w-0">
                          <p class="text-sm font-bold text-on-surface leading-tight m-0 truncate">{{ s.name }}</p>
                          <p class="text-xs text-outline leading-tight m-0 truncate">{{ s.email }}</p>
                        </div>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2">
                        <span class="text-sm font-bold tabular-nums text-on-surface">
                          {{ s.eindniveau !== null ? s.eindniveau.toFixed(1) : '—' }}
                        </span>
                        <span
                          v-if="s.band"
                          class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider"
                          :class="bandClass(s.band)"
                        >
                          {{ bandLabel(s.band) }}
                        </span>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="material-symbols-outlined text-base"
                        :class="trendColor(s.trend)"
                      >
                        {{ trendIcon(s.trend) }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-xs text-on-surface-variant tabular-nums">
                      {{ daysAgoLabel(s.last_pr_days_ago) }}
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold tabular-nums"
                        :class="s.prs_waiting_feedback > 0 ? 'bg-tertiary/15 text-tertiary' : 'text-on-surface-variant'"
                      >
                        {{ s.prs_waiting_feedback }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-xs text-on-surface-variant">
                      <span v-if="s.strongest_criterion">
                        {{ s.strongest_criterion.slug.replace(/_/g, ' ') }}
                        <span class="tabular-nums ml-1 text-outline">{{ s.strongest_criterion.score.toFixed(1) }}</span>
                      </span>
                      <span v-else>—</span>
                    </td>
                    <td class="px-4 py-3 text-xs text-on-surface-variant">
                      <span v-if="s.weakest_criterion">
                        {{ s.weakest_criterion.slug.replace(/_/g, ' ') }}
                        <span class="tabular-nums ml-1 text-outline">{{ s.weakest_criterion.score.toFixed(1) }}</span>
                      </span>
                      <span v-else>—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- ══════ Activiteit deze periode ══════ -->
          <section class="bg-surface-container rounded-xl border border-outline-variant/10 p-6">
            <header class="flex items-baseline justify-between mb-4">
              <h2 class="text-xl font-bold text-on-surface m-0">Activiteit deze periode</h2>
              <span class="text-xs uppercase tracking-widest text-outline">Laatste 8 weken</span>
            </header>
            <div class="h-48">
              <Bar :data="chartData" :options="chartOptions" />
            </div>
          </section>
        </div>
      </div>
    </div>
  </AppShell>
</template>
