<script setup lang="ts">
/**
 * Ops Dashboard — platform metrics surface (super admin only).
 *
 * Redesigned as a demo-grade SaaS metrics dashboard:
 *   - KPI cards row (totals for the selected period)
 *   - Sessions over time (line chart, started + sent)
 *   - LLM cost over time (line chart, EUR/day)
 *   - Per-org breakdown (horizontal bar chart, top 10)
 *   - Per-cohort table (sortable)
 *
 * Backed by GET /api/grading/ops/metrics/weekly/?granularity=daily
 * (weekly rollup endpoint called separately for cohort rows).
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Line, Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  Tooltip as ChartTooltip,
  Legend,
} from 'chart.js';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Filler, ChartTooltip, Legend,
);

const router = useRouter();
const auth = useAuthStore();

// ── state ───────────────────────────────────────────────────────────────────
const loading = ref(true);
const error = ref<string | null>(null);
const rangeDays = ref(7);  // 7 | 30 | 90
const generatedAt = ref<Date | null>(null);

type Day = {
  date: string;
  sessions_started: number;
  sessions_sent: number;
  llm_cost_eur: number;
  findings_total: number;
  teachers_active: number;
};

type OrgRow = {
  org_id: number;
  org_name: string;
  sessions_started: number;
  sessions_sent: number;
  llm_cost_eur: number;
};

type CohortRow = {
  org_id: number;
  org_name: string;
  cohort_id: number | null;
  cohort_name: string;
  teachers_active: number;
  sessions_started: number;
  sessions_sent: number;
  send_rate: number;
  llm_cost_eur: number;
  template_hit_rate: number;
};

const days = ref<Day[]>([]);
const perOrg = ref<OrgRow[]>([]);
const grandTotals = ref<Record<string, number>>({});
const cohortRows = ref<CohortRow[]>([]);
const period = ref<{ start: string; end: string }>({ start: '', end: '' });

// Previous period snapshot (for KPI delta)
const prevGrandTotals = ref<Record<string, number>>({});
const prevDays = ref<Day[]>([]);

// Sort state for cohort table
const cohortSortKey = ref<keyof CohortRow>('sessions_started');
const cohortSortDir = ref<'asc' | 'desc'>('desc');

// ── auth guard (router already gates; belt-and-braces) ──────────────────────
onMounted(async () => {
  if (!auth.isSuperuser) {
    router.replace({ name: 'dashboard' });
    return;
  }
  await load();
});

watch(rangeDays, () => load());

// ── helpers ─────────────────────────────────────────────────────────────────
function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatEur(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(Number(n))) return '0.00';
  return Number(n).toFixed(digits);
}

function formatPct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${(Number(n) * 100).toFixed(0)}%`;
}

function shortDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ── data load ───────────────────────────────────────────────────────────────
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (rangeDays.value - 1));
    const prevEnd = new Date(start);
    prevEnd.setDate(prevEnd.getDate() - 1);
    const prevStart = new Date(prevEnd);
    prevStart.setDate(prevStart.getDate() - (rangeDays.value - 1));

    // Current period: daily granularity
    const [currentResp, prevResp, weeklyResp] = await Promise.all([
      api.grading.ops.metrics.weekly({
        granularity: 'daily',
        start: isoDate(start), end: isoDate(end),
      }),
      api.grading.ops.metrics.weekly({
        granularity: 'daily',
        start: isoDate(prevStart), end: isoDate(prevEnd),
      }).catch(() => ({ data: { grand_totals: {}, days: [], per_org: [] } })),
      // Weekly rollup has the per-cohort breakdown for the table
      api.grading.ops.metrics.weekly({
        start: isoDate(start), end: isoDate(end),
      }).catch(() => ({ data: { orgs: [] } })),
    ]);

    days.value = currentResp.data.days || [];
    perOrg.value = currentResp.data.per_org || [];
    grandTotals.value = currentResp.data.grand_totals || {};
    period.value = currentResp.data.period || { start: '', end: '' };

    prevGrandTotals.value = prevResp.data.grand_totals || {};
    prevDays.value = prevResp.data.days || [];

    // Flatten weekly orgs[].cohorts[] into a single table
    const flat: CohortRow[] = [];
    for (const o of (weeklyResp.data.orgs || [])) {
      for (const c of (o.cohorts || [])) {
        flat.push({
          org_id: o.org_id,
          org_name: o.org_name,
          cohort_id: c.cohort_id,
          cohort_name: c.cohort_name,
          teachers_active: c.teachers_active,
          sessions_started: c.sessions_started,
          sessions_sent: c.sessions_sent,
          send_rate: c.send_rate,
          llm_cost_eur: c.llm_cost_eur,
          template_hit_rate: c.template_hit_rate,
        });
      }
    }
    cohortRows.value = flat;
    generatedAt.value = new Date();
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to load metrics.';
  } finally {
    loading.value = false;
  }
}

// ── KPIs ────────────────────────────────────────────────────────────────────
const activeOrgs = computed(() => perOrg.value.filter(o => o.sessions_started > 0).length);
const activeCohorts = computed(() =>
  new Set(cohortRows.value.filter(c => c.sessions_started > 0).map(c => `${c.org_id}::${c.cohort_id}`)).size,
);

const sendRatePct = computed(() => {
  const started = grandTotals.value.sessions_started || 0;
  const sent = grandTotals.value.sessions_sent || 0;
  if (!started) return 0;
  return (sent / started);
});

const avgReviewMinutes = computed(() => {
  // Weighted avg of cohort avg_review_time across cohorts with data.
  let sumMin = 0, weight = 0;
  for (const c of cohortRows.value) {
    const rt = (c as any).avg_review_time_minutes;
    if (rt != null && c.sessions_sent > 0) {
      sumMin += rt * c.sessions_sent;
      weight += c.sessions_sent;
    }
  }
  if (!weight) return null;
  return sumMin / weight;
});

function delta(curr: number | undefined, prev: number | undefined): { val: number | null; up: boolean | null } {
  if (curr == null || prev == null) return { val: null, up: null };
  if (!prev && !curr) return { val: 0, up: null };
  if (!prev) return { val: null, up: null };
  const pct = ((curr - prev) / prev) * 100;
  return { val: Math.round(pct), up: pct >= 0 };
}

const kpis = computed(() => [
  {
    label: 'Sessions this period',
    value: grandTotals.value.sessions_started ?? 0,
    sub: `${grandTotals.value.sessions_sent ?? 0} sent`,
    delta: delta(grandTotals.value.sessions_started, prevGrandTotals.value.sessions_started),
  },
  {
    label: 'LLM cost',
    value: `€${formatEur(grandTotals.value.llm_cost_eur)}`,
    sub: 'Total across platform',
    delta: delta(grandTotals.value.llm_cost_eur, prevGrandTotals.value.llm_cost_eur),
  },
  {
    label: 'Active orgs',
    value: activeOrgs.value,
    sub: `${perOrg.value.length} total`,
    delta: null,
  },
  {
    label: 'Active cohorts',
    value: activeCohorts.value,
    sub: `${cohortRows.value.length} total`,
    delta: null,
  },
  {
    label: 'Send rate',
    value: formatPct(sendRatePct.value),
    sub: 'Drafted → posted',
    delta: null,
  },
  {
    label: 'Avg review time',
    value: avgReviewMinutes.value != null ? `${avgReviewMinutes.value.toFixed(1)}m` : '—',
    sub: 'Weighted by sessions',
    delta: null,
  },
]);

// ── chart configs ───────────────────────────────────────────────────────────
const STITCH_PRIMARY = '#6366f1';    // indigo-500
const STITCH_SECONDARY = '#10b981';  // emerald-500
const STITCH_TERTIARY = '#f59e0b';   // amber-500

const sessionsChart = computed(() => ({
  data: {
    labels: days.value.map(d => shortDate(d.date)),
    datasets: [
      {
        label: 'Started',
        data: days.value.map(d => d.sessions_started),
        borderColor: STITCH_PRIMARY,
        backgroundColor: 'rgba(99, 102, 241, 0.12)',
        tension: 0.35,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: STITCH_PRIMARY,
      },
      {
        label: 'Sent',
        data: days.value.map(d => d.sessions_sent),
        borderColor: STITCH_SECONDARY,
        backgroundColor: 'rgba(16, 185, 129, 0.08)',
        tension: 0.35,
        fill: false,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: STITCH_SECONDARY,
      },
    ],
  },
  options: lineOptions(),
}));

const costChart = computed(() => ({
  data: {
    labels: days.value.map(d => shortDate(d.date)),
    datasets: [
      {
        label: 'LLM cost (EUR)',
        data: days.value.map(d => d.llm_cost_eur),
        borderColor: STITCH_TERTIARY,
        backgroundColor: 'rgba(245, 158, 11, 0.14)',
        tension: 0.35,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 6,
        pointBackgroundColor: STITCH_TERTIARY,
      },
    ],
  },
  options: lineOptions({ prefix: '€' }),
}));

function lineOptions(opts: { prefix?: string } = {}): any {
  const prefix = opts.prefix || '';
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(255,255,255,0.05)' },
        ticks: {
          color: 'rgba(255,255,255,0.4)',
          font: { size: 11 },
          callback: (v: number) => `${prefix}${v}`,
        },
      },
      x: {
        grid: { display: false },
        ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 11 } },
      },
    },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        align: 'end',
        labels: {
          color: 'rgba(255,255,255,0.6)',
          font: { size: 11 },
          boxWidth: 10,
          boxHeight: 10,
          usePointStyle: true,
        },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        padding: 10,
        titleColor: 'rgba(255,255,255,0.8)',
        bodyColor: 'rgba(255,255,255,0.8)',
        callbacks: prefix === '€'
          ? { label: (ctx: any) => ` ${prefix}${Number(ctx.parsed.y).toFixed(2)}` }
          : undefined,
      },
    },
  };
}

const topOrgsChart = computed(() => {
  const top = [...perOrg.value].slice(0, 10);
  return {
    data: {
      labels: top.map(o => o.org_name),
      datasets: [
        {
          label: 'Sessions started',
          data: top.map(o => o.sessions_started),
          backgroundColor: 'rgba(99, 102, 241, 0.65)',
          borderColor: STITCH_PRIMARY,
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 11 } },
        },
        y: {
          grid: { display: false },
          ticks: { color: 'rgba(255,255,255,0.7)', font: { size: 12 } },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          padding: 10,
          titleColor: 'rgba(255,255,255,0.8)',
          bodyColor: 'rgba(255,255,255,0.8)',
          callbacks: {
            afterLabel: (ctx: any) => {
              const row = top[ctx.dataIndex];
              if (!row) return '';
              const sendRate = row.sessions_started
                ? ((row.sessions_sent / row.sessions_started) * 100).toFixed(0) + '%'
                : '—';
              return [`Sent: ${row.sessions_sent}`, `Cost: €${formatEur(row.llm_cost_eur)}`, `Send rate: ${sendRate}`];
            },
          },
        },
      },
    },
  };
});

// ── cohort table sorting ────────────────────────────────────────────────────
const sortedCohorts = computed(() => {
  const arr = [...cohortRows.value];
  const k = cohortSortKey.value;
  const dir = cohortSortDir.value === 'asc' ? 1 : -1;
  arr.sort((a: any, b: any) => {
    const av = a[k] ?? 0, bv = b[k] ?? 0;
    if (typeof av === 'string') return av.localeCompare(bv) * dir;
    return (av - bv) * dir;
  });
  return arr;
});

function sortBy(k: keyof CohortRow) {
  if (cohortSortKey.value === k) {
    cohortSortDir.value = cohortSortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    cohortSortKey.value = k;
    cohortSortDir.value = 'desc';
  }
}

const hasAnyActivity = computed(() =>
  (grandTotals.value.sessions_started ?? 0) > 0
  || (grandTotals.value.sessions_sent ?? 0) > 0
  || (grandTotals.value.llm_cost_eur ?? 0) > 0,
);

const rawJsonHref = computed(() => {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (rangeDays.value - 1));
  const params = new URLSearchParams({
    granularity: 'daily',
    start: isoDate(start),
    end: isoDate(end),
  });
  return `/api/grading/ops/metrics/weekly/?${params.toString()}`;
});
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Header -->
      <section class="flex flex-col md:flex-row items-start md:items-end justify-between gap-6 mb-10">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Platform Operations</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">Ops Dashboard</h1>
          <p class="text-outline text-sm">
            Live platform metrics across every organization, cohort, and teacher.
            <span v-if="period.start" class="ml-1 text-outline/70">
              ({{ shortDate(period.start) }} – {{ shortDate(period.end) }})
            </span>
          </p>
        </div>

        <!-- Date range selector -->
        <div class="flex items-center gap-2 bg-surface-container rounded-xl border border-outline-variant/20 p-1">
          <button
            v-for="r in [7, 30, 90]"
            :key="r"
            @click="rangeDays = r"
            :class="[
              'px-4 py-2 rounded-lg text-sm font-medium transition-all',
              rangeDays === r
                ? 'bg-primary/15 text-primary'
                : 'text-outline hover:text-on-surface',
            ]"
          >
            {{ r }}d
          </button>
        </div>
      </section>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-24 gap-3 text-outline">
        <span class="material-symbols-outlined animate-spin text-3xl">progress_activity</span>
        Loading ops metrics…
      </div>

      <!-- Error -->
      <div v-else-if="error"
        class="bg-error/10 border border-error/30 text-error rounded-2xl p-6 flex items-start gap-3">
        <span class="material-symbols-outlined">error</span>
        <div>
          <p class="font-semibold">Couldn't load metrics</p>
          <p class="text-sm opacity-80 mt-1">{{ error }}</p>
          <button @click="load"
            class="mt-3 px-3 py-1.5 rounded-lg bg-error/15 border border-error/30 text-xs font-medium hover:bg-error/25 transition-colors">
            Retry
          </button>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!hasAnyActivity"
        class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-16 flex flex-col items-center gap-4 text-center">
        <span class="material-symbols-outlined text-6xl text-outline">monitoring</span>
        <h3 class="text-xl font-bold text-on-surface">No activity yet</h3>
        <p class="text-outline text-sm max-w-md">
          Start grading PRs with the Nakijken Copilot to see sessions, costs, and
          per-org rollups appear here in real time.
        </p>
      </div>

      <!-- Main content -->
      <template v-else>
        <!-- KPI cards -->
        <section class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <div
            v-for="k in kpis"
            :key="k.label"
            class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-4"
          >
            <p class="text-[10px] text-outline uppercase tracking-wider mb-2">{{ k.label }}</p>
            <p class="text-3xl font-black text-on-surface tabular-nums">{{ k.value }}</p>
            <div class="flex items-center justify-between mt-1.5">
              <p class="text-[11px] text-outline/80">{{ k.sub }}</p>
              <span
                v-if="k.delta && k.delta.val != null"
                class="flex items-center gap-0.5 text-[10px] font-bold"
                :class="k.delta.up ? 'text-emerald-500' : 'text-error'"
              >
                <span class="material-symbols-outlined" style="font-size: 12px">
                  {{ k.delta.up ? 'trending_up' : 'trending_down' }}
                </span>
                {{ k.delta.val > 0 ? '+' : '' }}{{ k.delta.val }}%
              </span>
            </div>
          </div>
        </section>

        <!-- Charts row: sessions + cost -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-8">
          <div class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h2 class="text-base font-bold text-on-surface">Sessions over time</h2>
                <p class="text-xs text-outline">Daily drafts started vs posted</p>
              </div>
            </div>
            <div class="h-[280px] relative">
              <Line :data="sessionsChart.data" :options="sessionsChart.options" />
            </div>
          </div>

          <div class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h2 class="text-base font-bold text-on-surface">LLM cost over time</h2>
                <p class="text-xs text-outline">Daily spend in EUR</p>
              </div>
            </div>
            <div class="h-[280px] relative">
              <Line :data="costChart.data" :options="costChart.options" />
            </div>
          </div>
        </section>

        <!-- Per-org bar chart -->
        <section class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6 mb-8">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-base font-bold text-on-surface">Top organizations</h2>
              <p class="text-xs text-outline">Ranked by sessions started · hover for cost + send rate</p>
            </div>
            <span class="text-xs text-outline">Top {{ Math.min(perOrg.length, 10) }} of {{ perOrg.length }}</span>
          </div>
          <div v-if="perOrg.length" :style="{ height: Math.max(200, perOrg.slice(0, 10).length * 36) + 40 + 'px' }" class="relative">
            <Bar :data="topOrgsChart.data" :options="topOrgsChart.options" />
          </div>
          <div v-else class="text-outline text-sm py-8 text-center">No orgs with activity in this period.</div>
        </section>

        <!-- Per-cohort table -->
        <section class="bg-surface-container-low rounded-2xl border border-outline-variant/10 overflow-hidden mb-8">
          <div class="p-6 pb-4 flex items-center justify-between">
            <div>
              <h2 class="text-base font-bold text-on-surface">Cohort breakdown</h2>
              <p class="text-xs text-outline">Every org × cohort combination with activity</p>
            </div>
            <span class="text-xs text-outline">{{ cohortRows.length }} row{{ cohortRows.length === 1 ? '' : 's' }}</span>
          </div>

          <div v-if="!cohortRows.length" class="px-6 pb-8 text-outline text-sm">
            No cohort activity in this period.
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-surface-container">
                <tr class="text-left text-outline uppercase text-[10px] tracking-wider">
                  <th class="px-6 py-3 font-semibold cursor-pointer hover:text-on-surface" @click="sortBy('org_name')">
                    Org
                  </th>
                  <th class="px-4 py-3 font-semibold cursor-pointer hover:text-on-surface" @click="sortBy('cohort_name')">
                    Cohort
                  </th>
                  <th class="px-4 py-3 font-semibold cursor-pointer hover:text-on-surface text-right" @click="sortBy('teachers_active')">
                    Teachers
                  </th>
                  <th class="px-4 py-3 font-semibold cursor-pointer hover:text-on-surface text-right" @click="sortBy('sessions_started')">
                    Started
                  </th>
                  <th class="px-4 py-3 font-semibold cursor-pointer hover:text-on-surface text-right" @click="sortBy('sessions_sent')">
                    Sent
                  </th>
                  <th class="px-4 py-3 font-semibold cursor-pointer hover:text-on-surface text-right" @click="sortBy('send_rate')">
                    Send rate
                  </th>
                  <th class="px-4 py-3 font-semibold cursor-pointer hover:text-on-surface text-right" @click="sortBy('llm_cost_eur')">
                    Cost
                  </th>
                  <th class="px-6 py-3 font-semibold cursor-pointer hover:text-on-surface text-right" @click="sortBy('template_hit_rate')">
                    Template hit
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/10">
                <tr
                  v-for="c in sortedCohorts"
                  :key="`${c.org_id}::${c.cohort_id}`"
                  class="hover:bg-surface-container/50 transition-colors"
                >
                  <td class="px-6 py-3 text-on-surface font-medium">{{ c.org_name }}</td>
                  <td class="px-4 py-3 text-on-surface-variant">{{ c.cohort_name }}</td>
                  <td class="px-4 py-3 text-right tabular-nums text-on-surface-variant">{{ c.teachers_active }}</td>
                  <td class="px-4 py-3 text-right tabular-nums text-on-surface font-semibold">{{ c.sessions_started }}</td>
                  <td class="px-4 py-3 text-right tabular-nums text-on-surface-variant">{{ c.sessions_sent }}</td>
                  <td class="px-4 py-3 text-right tabular-nums"
                    :class="c.send_rate >= 0.8 ? 'text-emerald-500' : c.send_rate >= 0.5 ? 'text-yellow-500' : 'text-outline'">
                    {{ formatPct(c.send_rate) }}
                  </td>
                  <td class="px-4 py-3 text-right tabular-nums text-on-surface-variant">€{{ formatEur(c.llm_cost_eur) }}</td>
                  <td class="px-6 py-3 text-right tabular-nums text-on-surface-variant">{{ formatPct(c.template_hit_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Footer -->
        <footer class="flex items-center justify-between text-xs text-outline py-4">
          <span>
            Last updated:
            <span v-if="generatedAt" class="text-on-surface-variant">
              {{ generatedAt.toLocaleTimeString() }}
            </span>
          </span>
          <a
            :href="rawJsonHref"
            target="_blank"
            rel="noopener"
            class="flex items-center gap-1 text-primary hover:text-primary/80 transition-colors"
          >
            <span class="material-symbols-outlined text-sm">data_object</span>
            Raw JSON
          </a>
        </footer>
      </template>
    </div>
  </AppShell>
</template>
