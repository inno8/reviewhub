<script setup lang="ts">
/**
 * TeacherStudentProfileView — /grading/students/:id
 *
 * The teacher's 1:1 cockpit for a single student. Single source of truth
 * for "where is this student, what to do next." Composed of:
 *   1. Header (back link + StudentHeaderChip)
 *   2. Top cards — Eindniveau + Aanbevolen focus
 *   3. Per criterium breakdown (reuses StudentSnapshotPanel data shape)
 *   4. Trajectorie (12-week line chart per category)
 *   5. Terugkerende patronen
 *   6. PR geschiedenis (PRCard list + state filter tabs)
 *
 * Wires to:
 *   GET /api/grading/students/<id>/snapshot/
 *   GET /api/grading/students/<id>/trajectory/?weeks=12
 *   GET /api/grading/students/<id>/pr-history/?limit=20
 *
 * Rewrite: April 2026 (pre-pitch polish).
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
  type ChartOptions,
} from 'chart.js';
import { Line } from 'vue-chartjs';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';
import StudentHeaderChip from '@/components/grading/StudentHeaderChip.vue';
import PRCard from '@/components/grading/PRCard.vue';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

// ── Types ──────────────────────────────────────────────────────────────
type LearningProofStatus = 'taught' | 'pending' | 'proven' | 'reinforced' | 'relapsed';
interface PerSkillItem {
  skill_slug: string;
  display_name: string;
  kerntaak: string | null;
  bayesian_score: number | null;
  confidence: number;
  observation_count: number;
  trend: 'up' | 'down' | 'stable';
  trend_delta: number;
  level_label: string | null;
  learning_proof_status?: LearningProofStatus;
}
interface SkillRadarItem {
  category: string;
  score: number;
  confidence: number;
  level_label: string | null;
  trend: 'up' | 'down' | 'stable';
}
interface RecurringPattern {
  pattern_key: string;
  pattern_type: string;
  frequency: number;
  last_seen_days_ago: number | null;
  severity: string;
}
interface Snapshot {
  student: {
    id: number;
    name: string;
    email: string;
    cohort: { id: number; name: string } | null;
  };
  skill_radar: SkillRadarItem[];
  per_skill?: PerSkillItem[];
  recurring_patterns: RecurringPattern[];
  trending_up: string[];
  trending_down: string[];
  recent_activity: { prs_last_30d: number; avg_bayesian_score: number };
}
interface TrajectoryWeek {
  week_start: string;
  avg_score_per_category: Record<string, number>;
  prs_count: number;
  findings_count: number;
}
interface Trajectory {
  student: { id: number; name: string; email: string };
  weeks: TrajectoryWeek[];
  milestones: Array<{ date: string | null; event: string; skill: string }>;
}
interface PRHistoryEntry {
  id?: number;
  session_id?: number;
  submission_id?: number;
  pr_url?: string;
  pr_number: number | null;
  pr_title: string;
  repo_full_name: string | null;
  submitted_at: string | null;
  graded_at: string | null;
  state: string;
  rubric_score_avg: number | null;
  findings_count: number;
  course_name: string | null;
}
interface PRHistory {
  student: { id: number; name: string; email: string };
  sessions: PRHistoryEntry[];
}

// ── Route + state ──────────────────────────────────────────────────────
const route = useRoute();
const router = useRouter();
const studentId = computed(() => Number(route.params.id));

const snapshotLoading = ref(false);
const snapshotError = ref<string | null>(null);
const snapshot = ref<Snapshot | null>(null);

const trajectoryLoading = ref(false);
const trajectoryError = ref<string | null>(null);
const trajectory = ref<Trajectory | null>(null);

const historyLoading = ref(false);
const historyError = ref<string | null>(null);
const history = ref<PRHistory | null>(null);

const selectedPrState = ref<string | null>(null);

// ── Loaders (parallel) ─────────────────────────────────────────────────
async function loadSnapshot() {
  if (!studentId.value) return;
  snapshotLoading.value = true;
  snapshotError.value = null;
  try {
    const { data } = await api.grading.students.snapshot(studentId.value);
    snapshot.value = data;
  } catch (err: any) {
    snapshotError.value =
      err?.response?.data?.detail || err?.message || 'Kon snapshot niet laden';
    snapshot.value = null;
  } finally {
    snapshotLoading.value = false;
  }
}

async function loadTrajectory() {
  if (!studentId.value) return;
  trajectoryLoading.value = true;
  trajectoryError.value = null;
  try {
    const { data } = await api.grading.students.trajectory(studentId.value, 12);
    trajectory.value = data;
  } catch (err: any) {
    trajectoryError.value =
      err?.response?.data?.detail || err?.message || 'Kon trajectorie niet laden';
    trajectory.value = null;
  } finally {
    trajectoryLoading.value = false;
  }
}

async function loadHistory() {
  if (!studentId.value) return;
  historyLoading.value = true;
  historyError.value = null;
  try {
    const { data } = await api.grading.students.prHistory(studentId.value, 20);
    history.value = data;
  } catch (err: any) {
    historyError.value =
      err?.response?.data?.detail || err?.message || 'Kon PR-geschiedenis niet laden';
    history.value = null;
  } finally {
    historyLoading.value = false;
  }
}

function loadAll() {
  // Fire in parallel — each section handles its own loading/error state.
  loadSnapshot();
  loadTrajectory();
  loadHistory();
}

onMounted(loadAll);
watch(studentId, loadAll);

// ── Eindniveau (overall weighted score 0-4) ────────────────────────────
/**
 * Per_skill.bayesian_score is on 0-100. The rubric UI speaks 0-4 — so we
 * divide by 25 to get the teacher-facing scale. Only counts criteria that
 * have at least one observation (bayesian_score !== null).
 */
const eindniveauScore = computed(() => {
  const rows = snapshot.value?.per_skill || [];
  const usable = rows.filter(r => r.bayesian_score !== null);
  if (usable.length === 0) return null;
  const sum = usable.reduce((s, r) => s + (r.bayesian_score as number), 0);
  return sum / usable.length / 25;
});

interface Band {
  label: string;
  text: string;
  pill: string;
  bar: string;
}
const BAND_NONE: Band = {
  label: 'Geen data',
  text: 'text-on-surface-variant',
  pill: 'bg-surface-container text-on-surface-variant',
  bar: 'bg-outline-variant',
};
function bandFor(score: number | null): Band {
  if (score == null) return BAND_NONE;
  if (score < 2) {
    return {
      label: 'Onvoldoende',
      text: 'text-error',
      pill: 'bg-error/20 text-error',
      bar: 'bg-error',
    };
  }
  if (score < 3) {
    return {
      label: 'Net aan',
      text: 'text-tertiary',
      pill: 'bg-tertiary/20 text-tertiary',
      bar: 'bg-tertiary',
    };
  }
  if (score < 3.5) {
    return {
      label: 'Voldoende',
      text: 'text-primary',
      pill: 'bg-primary/20 text-primary',
      bar: 'bg-primary',
    };
  }
  return {
    label: 'Goed',
    text: 'text-emerald-300',
    pill: 'bg-emerald-900/40 text-emerald-300',
    bar: 'bg-emerald-400',
  };
}

const eindniveauBand = computed(() => bandFor(eindniveauScore.value));

// ── Aanbevolen focus ───────────────────────────────────────────────────
interface Focus {
  criterion: string | null;
  sentence: string;
}

const focus = computed<Focus>(() => {
  const rows = (snapshot.value?.per_skill || []).filter(
    r => r.bayesian_score !== null && r.observation_count >= 2,
  );
  if (rows.length === 0) {
    return {
      criterion: null,
      sentence: 'Geen duidelijke zwakke plek — blijf koers houden.',
    };
  }
  // Find weakest; tie-break on trending down first, then lower confidence.
  const sorted = [...rows].sort((a, b) => {
    const sa = a.bayesian_score as number;
    const sb = b.bayesian_score as number;
    if (sa !== sb) return sa - sb;
    const trendRank = (t: string) => (t === 'down' ? 0 : t === 'stable' ? 1 : 2);
    if (trendRank(a.trend) !== trendRank(b.trend)) {
      return trendRank(a.trend) - trendRank(b.trend);
    }
    return a.confidence - b.confidence;
  });
  const pick = sorted[0];
  const scoreOf4 = (pick.bayesian_score as number) / 25;
  const trendLabel =
    pick.trend === 'up' ? 'stijgend' : pick.trend === 'down' ? 'dalend' : 'stabiel';
  const relapsed = pick.learning_proof_status === 'relapsed';
  const suggestion = relapsed
    ? 'terugvalpreventie — plan gericht gesprek en een fix-and-learn herhaaloefening'
    : pick.trend === 'down'
      ? 'onderzoek waarom de score daalt en kies een concrete oefening voor de volgende PR'
      : 'herhaalde, concrete feedback op dit criterium in de eerstvolgende PRs';
  return {
    criterion: pick.display_name,
    sentence: `Score ${scoreOf4.toFixed(1)}/4, trend ${trendLabel}, ${pick.observation_count} observatie${pick.observation_count === 1 ? '' : 's'}. Focus op ${suggestion}.`,
  };
});

// ── Per criterium helpers (same shape as StudentSnapshotPanel) ─────────
function scoreBandClass(score: number | null): string {
  if (score === null) return 'bg-surface-container';
  if (score >= 80) return 'bg-emerald-400';
  if (score >= 60) return 'bg-sky-400';
  if (score >= 40) return 'bg-amber-400';
  return 'bg-red-400';
}
function confidenceOpacity(confidence: number): number {
  if (confidence < 0.15) return 0.4;
  if (confidence < 0.4) return 0.7;
  return 1.0;
}
function trendIcon(trend: string): string {
  if (trend === 'up') return '↑';
  if (trend === 'down') return '↓';
  return '→';
}
function formatDelta(delta: number): string {
  if (delta > 0) return `+${delta.toFixed(0)}`;
  if (delta < 0) return delta.toFixed(0);
  return '0';
}
const totalObservations = computed(() =>
  (snapshot.value?.per_skill || []).reduce((s, r) => s + (r.observation_count || 0), 0),
);
const prsLast30d = computed(() =>
  snapshot.value?.recent_activity?.prs_last_30d ?? 0,
);
const hasLearningProofData = computed(() =>
  (snapshot.value?.per_skill || []).some(r => !!r.learning_proof_status),
);
interface ProofDot {
  emoji: string;
  tooltip: string;
}
function learningProofDot(item: PerSkillItem): ProofDot {
  const s = item.learning_proof_status;
  if (!s) return { emoji: '⚪', tooltip: 'Nog geen les-status' };
  switch (s) {
    case 'taught':
      return { emoji: '⚪', tooltip: 'Uitgelegd, bewijs in afwachting' };
    case 'pending':
      return { emoji: '🟡', tooltip: 'Gedeeltelijk bewezen' };
    case 'proven':
      return { emoji: '🟢', tooltip: 'Bewezen' };
    case 'reinforced':
      return { emoji: '🔵', tooltip: 'Volledig geïnternaliseerd' };
    case 'relapsed':
      return { emoji: '🔴', tooltip: 'Terugval gedetecteerd' };
    default:
      return { emoji: '⚪', tooltip: 'Nog geen les-status' };
  }
}

// ── Trajectory chart ───────────────────────────────────────────────────
const CATEGORY_COLORS = [
  'rgba(96, 165, 250, 0.9)', // blue
  'rgba(74, 222, 128, 0.9)', // green
  'rgba(250, 204, 21, 0.9)', // yellow
  'rgba(248, 113, 113, 0.9)', // red
  'rgba(167, 139, 250, 0.9)', // purple
  'rgba(56, 189, 248, 0.9)', // cyan
];

function formatWeekLabel(iso: string): string {
  // Dutch week-number label: "wk 12"
  const d = new Date(iso + 'T00:00:00');
  if (isNaN(d.getTime())) return iso;
  // ISO week number (Thursday-based).
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = tmp.getUTCDay() || 7;
  tmp.setUTCDate(tmp.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
  return `wk ${weekNo}`;
}

const trajectoryHasData = computed(() => {
  const weeks = trajectory.value?.weeks || [];
  return weeks.some(w => Object.keys(w.avg_score_per_category || {}).length > 0);
});

const trajectoryChart = computed(() => {
  const weeks = trajectory.value?.weeks || [];
  if (weeks.length === 0) return null;
  const catSet = new Set<string>();
  for (const w of weeks) {
    for (const k of Object.keys(w.avg_score_per_category || {})) catSet.add(k);
  }
  const categories = [...catSet].sort();
  return {
    labels: weeks.map(w => formatWeekLabel(w.week_start)),
    datasets: categories.map((cat, i) => ({
      label: cat,
      data: weeks.map(w =>
        w.avg_score_per_category?.[cat] !== undefined
          ? w.avg_score_per_category[cat]
          : null,
      ),
      borderColor: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
      backgroundColor: CATEGORY_COLORS[i % CATEGORY_COLORS.length].replace(
        /0\.9\)/,
        '0.1)',
      ),
      tension: 0.3,
      spanGaps: true,
      pointRadius: 3,
      pointHoverRadius: 5,
      borderWidth: 2,
    })),
  };
});

const trajectoryOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  scales: {
    x: {
      grid: { color: 'rgba(148, 163, 184, 0.08)' },
      ticks: { color: 'rgba(148, 163, 184, 0.7)', font: { size: 10 } },
    },
    y: {
      beginAtZero: true,
      max: 100,
      grid: { color: 'rgba(148, 163, 184, 0.08)' },
      ticks: {
        color: 'rgba(148, 163, 184, 0.7)',
        font: { size: 10 },
        stepSize: 25,
      },
    },
  },
  plugins: {
    legend: {
      position: 'top' as const,
      align: 'end' as const,
      labels: {
        color: '#cbd5e1',
        font: { size: 11 },
        padding: 14,
        usePointStyle: true,
        boxWidth: 8,
      },
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(148, 163, 184, 0.2)',
      borderWidth: 1,
    },
  },
}));

// ── Recurring patterns helpers ─────────────────────────────────────────
function formatPatternKey(key: string): string {
  return key.replace(/_/g, ' ');
}
function severityIcon(severity: string): string {
  return severity === 'warning' ? 'warning' : 'info';
}
function severityClasses(severity: string): string {
  return severity === 'warning'
    ? 'bg-tertiary/10 border-tertiary text-tertiary'
    : 'bg-primary/10 border-primary text-primary';
}

// Map a pattern_type (proxy for skill category) to a LearningProof dot
// from per_skill. Best-effort string match; shows nothing if no hit.
function proofPillForPattern(p: RecurringPattern): ProofDot | null {
  const rows = snapshot.value?.per_skill || [];
  const hay = `${p.pattern_key} ${p.pattern_type}`.toLowerCase();
  for (const r of rows) {
    if (!r.learning_proof_status) continue;
    if (hay.includes(r.skill_slug.replace(/_/g, ' '))) {
      return learningProofDot(r);
    }
  }
  return null;
}

// ── PR history helpers ─────────────────────────────────────────────────
const STATE_CHIPS: Array<{ label: string; value: string | null }> = [
  { label: 'Alles', value: null },
  { label: 'Klaar voor review', value: 'drafted' },
  { label: 'In review', value: 'reviewing' },
  { label: 'Verstuurd', value: 'posted' },
];

const filteredSessions = computed(() => {
  const rows = history.value?.sessions || [];
  if (!selectedPrState.value) return rows;
  return rows.filter(s => s.state === selectedPrState.value);
});

function sessionIdOf(s: PRHistoryEntry): number {
  return (s.session_id ?? s.id ?? 0) as number;
}

function openSession(id: number) {
  if (!id) return;
  router.push({ name: 'grading-session-detail', params: { id } });
}

function goBack() {
  router.push({ name: 'grading-inbox' });
}

// ── Student chip data ──────────────────────────────────────────────────
const studentName = computed(() =>
  snapshot.value?.student.name
    || trajectory.value?.student.name
    || history.value?.student.name
    || '',
);
const studentEmail = computed(() =>
  snapshot.value?.student.email
    || trajectory.value?.student.email
    || history.value?.student.email
    || '',
);
const studentCohortName = computed(() => snapshot.value?.student.cohort?.name || null);

const anyLoading = computed(
  () => snapshotLoading.value || trajectoryLoading.value || historyLoading.value,
);
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-[1200px] mx-auto flex flex-col gap-6">
        <!-- 1. Header -->
        <div class="flex flex-col gap-4">
          <button
            type="button"
            @click="goBack"
            class="self-start inline-flex items-center gap-1 text-sm text-on-surface-variant hover:text-on-surface transition-colors"
            data-testid="back-btn"
          >
            <span class="material-symbols-outlined text-base">arrow_back</span>
            <span>Terug naar overzicht</span>
          </button>

          <div class="flex items-center justify-between gap-4 flex-wrap">
            <div class="flex-1 min-w-[280px]">
              <StudentHeaderChip
                :name="studentName"
                :email="studentEmail"
                :student-id="studentId"
                :cohort-name="studentCohortName"
              />
            </div>
            <span
              class="text-[10px] font-semibold uppercase tracking-widest px-2.5 py-1 rounded-md bg-primary/15 text-primary whitespace-nowrap"
            >
              Volledig profiel actief
            </span>
          </div>
        </div>

        <!-- 2. Top cards: Eindniveau + Aanbevolen focus -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <!-- Eindniveau -->
          <section
            class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-4"
            data-testid="eindniveau-card"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex flex-col gap-1 min-w-0">
                <span class="text-[11px] uppercase tracking-widest font-semibold text-on-surface-variant">
                  Eindniveau
                </span>
                <div v-if="snapshotLoading && !snapshot" class="h-12 w-32 rounded bg-surface-container animate-pulse mt-1"></div>
                <div v-else class="flex items-baseline gap-1">
                  <span
                    class="text-5xl font-bold tabular-nums"
                    :class="eindniveauBand.text"
                    data-testid="eindniveau-score"
                  >{{ eindniveauScore !== null ? eindniveauScore.toFixed(1) : '—' }}</span>
                  <span class="text-xl text-outline tabular-nums">/ 4.0</span>
                </div>
              </div>
              <span
                :class="[
                  'shrink-0 rounded-full px-3 py-1 text-[11px] uppercase tracking-widest font-bold',
                  eindniveauBand.pill,
                ]"
                data-testid="eindniveau-band"
              >{{ eindniveauBand.label }}</span>
            </div>
            <div class="h-2 w-full rounded-full bg-surface-container overflow-hidden">
              <div
                :class="['h-full rounded-full transition-all', eindniveauBand.bar]"
                :style="{
                  width:
                    eindniveauScore !== null
                      ? Math.min(100, (eindniveauScore / 4) * 100) + '%'
                      : '0%',
                }"
              ></div>
            </div>
            <p class="text-xs text-on-surface-variant m-0">
              Bayesian-aggregaat over alle observaties van deze student.
              Gebaseerd op {{ totalObservations }} observatie{{ totalObservations === 1 ? '' : 's' }}
              uit {{ prsLast30d }} PR{{ prsLast30d === 1 ? '' : 's' }}.
            </p>
          </section>

          <!-- Aanbevolen focus -->
          <section
            class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-3"
            data-testid="focus-card"
          >
            <span class="text-[11px] uppercase tracking-widest font-semibold text-on-surface-variant">
              Aanbevolen focus
            </span>
            <div v-if="snapshotLoading && !snapshot" class="flex flex-col gap-2">
              <div class="h-7 w-64 rounded bg-surface-container animate-pulse"></div>
              <div class="h-4 w-full rounded bg-surface-container animate-pulse"></div>
            </div>
            <template v-else>
              <div class="text-lg font-bold text-on-surface leading-snug">
                Volgende 1:1:
                <span class="text-primary">{{ focus.criterion || 'Geen zwakke plek' }}</span>
              </div>
              <p class="text-sm text-on-surface-variant leading-relaxed m-0">
                {{ focus.sentence }}
              </p>
            </template>
          </section>
        </div>

        <!-- 3. Per criterium -->
        <section
          class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-4"
          data-testid="per-criterium-section"
        >
          <div class="flex items-baseline justify-between gap-4 flex-wrap">
            <div class="flex flex-col gap-1">
              <h2 class="text-base font-bold text-on-surface m-0">Per criterium</h2>
              <p class="text-xs text-on-surface-variant m-0">
                Bayesian-score 0-100, gebaseerd op {{ totalObservations }} observatie{{ totalObservations === 1 ? '' : 's' }}.
              </p>
            </div>
          </div>

          <div v-if="snapshotLoading && !snapshot" class="flex flex-col gap-2">
            <div v-for="n in 6" :key="n" class="h-6 rounded bg-surface-container animate-pulse"></div>
          </div>
          <div
            v-else-if="snapshotError"
            class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
          >
            {{ snapshotError }}
          </div>
          <ul
            v-else-if="snapshot?.per_skill?.length"
            class="list-none p-0 m-0 flex flex-col gap-2"
          >
            <li
              v-for="row in snapshot.per_skill"
              :key="row.skill_slug"
              class="flex items-center gap-3 text-xs"
              :data-testid="`per-skill-${row.skill_slug}`"
            >
              <div class="flex items-center gap-1.5 min-w-[11rem] max-w-[11rem]">
                <span class="text-on-surface truncate" :title="row.display_name">
                  {{ row.display_name }}
                </span>
                <span
                  v-if="row.kerntaak"
                  class="rounded-full bg-surface-container-high px-1.5 py-0.5 font-mono text-[9px] leading-none text-on-surface-variant shrink-0"
                  :title="row.kerntaak"
                >{{ row.kerntaak }}</span>
              </div>

              <div class="flex-1 h-2 rounded-full overflow-hidden bg-surface-container">
                <div
                  v-if="row.bayesian_score !== null"
                  :class="scoreBandClass(row.bayesian_score)"
                  class="h-full rounded-full transition-all"
                  :style="{
                    width: row.bayesian_score + '%',
                    opacity: confidenceOpacity(row.confidence),
                  }"
                ></div>
              </div>

              <span
                class="text-on-surface tabular-nums font-semibold min-w-[2rem] text-right"
                :class="row.bayesian_score === null ? 'text-outline font-normal' : ''"
              >
                {{ row.bayesian_score !== null ? Math.round(row.bayesian_score) : '—' }}
              </span>

              <span
                v-if="hasLearningProofData"
                :title="learningProofDot(row).tooltip"
                class="text-[11px] leading-none w-4 text-center select-none"
              >{{ learningProofDot(row).emoji }}</span>

              <span
                v-if="row.observation_count < 3"
                class="text-outline text-[10px] min-w-[3.5rem] text-right"
              >—</span>
              <span
                v-else
                class="min-w-[3.5rem] text-right text-[10px] tabular-nums flex items-center justify-end gap-1"
                :class="
                  row.trend === 'up'
                    ? 'text-[rgb(134,239,172)]'
                    : row.trend === 'down'
                      ? 'text-error'
                      : 'text-on-surface-variant'
                "
              >
                <span class="font-bold">{{ trendIcon(row.trend) }}</span>
                <span>{{ formatDelta(row.trend_delta) }}</span>
              </span>
            </li>
          </ul>
          <p v-else class="text-on-surface-variant text-sm m-0">Nog geen criterium-data.</p>
        </section>

        <!-- 4. Trajectorie -->
        <section
          class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-4"
          data-testid="trajectory-section"
        >
          <div class="flex items-baseline justify-between gap-4 flex-wrap">
            <div class="flex flex-col gap-1">
              <h2 class="text-base font-bold text-on-surface m-0">Trajectorie</h2>
              <p class="text-xs text-on-surface-variant m-0">
                Weekgemiddelde per categorie over de laatste 12 weken.
              </p>
            </div>
            <span
              v-if="trajectory && trajectory.weeks.length"
              class="text-[10px] font-semibold uppercase tracking-widest text-on-surface-variant"
            >
              {{ trajectory.weeks.length }} weken
            </span>
          </div>

          <div v-if="trajectoryLoading && !trajectory" class="h-[320px] rounded-lg bg-surface-container animate-pulse"></div>
          <div
            v-else-if="trajectoryError"
            class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
          >
            {{ trajectoryError }}
          </div>
          <div v-else-if="trajectoryChart && trajectoryHasData" class="h-[320px]">
            <Line :data="trajectoryChart" :options="trajectoryOptions" />
          </div>
          <p v-else class="text-on-surface-variant text-sm m-0">
            Nog te weinig data voor een trajectorie — minimaal 3 weken nodig.
          </p>
        </section>

        <!-- 5. Terugkerende patronen -->
        <section
          class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-4"
          data-testid="patterns-section"
        >
          <div class="flex flex-col gap-1">
            <h2 class="text-base font-bold text-on-surface m-0">Terugkerende patronen</h2>
            <p class="text-xs text-on-surface-variant m-0">
              Onopgeloste patronen die over meerdere PRs terugkomen.
            </p>
          </div>

          <div v-if="snapshotLoading && !snapshot" class="flex flex-col gap-2">
            <div v-for="n in 3" :key="n" class="h-14 rounded-lg bg-surface-container animate-pulse"></div>
          </div>
          <ul
            v-else-if="snapshot?.recurring_patterns?.length"
            class="list-none p-0 m-0 flex flex-col gap-2"
          >
            <li
              v-for="p in snapshot.recurring_patterns"
              :key="p.pattern_key"
              :class="[
                'px-4 py-3 rounded-lg border-l-2 flex items-start gap-3',
                severityClasses(p.severity),
              ]"
              data-testid="pattern-card"
            >
              <span
                class="material-symbols-outlined text-xl mt-0.5 shrink-0"
                :class="
                  p.severity === 'warning' ? 'text-tertiary' : 'text-primary'
                "
              >{{ severityIcon(p.severity) }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between gap-2 flex-wrap">
                  <span class="text-sm font-semibold text-on-surface">
                    {{ formatPatternKey(p.pattern_key) }}
                  </span>
                  <span
                    v-if="proofPillForPattern(p)"
                    class="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant whitespace-nowrap"
                    :title="proofPillForPattern(p)!.tooltip"
                  >
                    {{ proofPillForPattern(p)!.emoji }}
                    {{ proofPillForPattern(p)!.tooltip }}
                  </span>
                </div>
                <div class="text-[11px] mt-0.5 text-on-surface-variant">
                  <span>{{ p.frequency }} keer voorgekomen</span>
                  <span v-if="p.last_seen_days_ago !== null">
                    · laatst {{ p.last_seen_days_ago }} {{ p.last_seen_days_ago === 1 ? 'dag' : 'dagen' }} geleden
                  </span>
                  <span v-if="p.pattern_type"> · {{ p.pattern_type }}</span>
                </div>
              </div>
            </li>
          </ul>
          <p v-else class="text-on-surface-variant text-sm m-0">
            Geen terugkerende patronen — goed bezig.
          </p>
        </section>

        <!-- 6. PR geschiedenis -->
        <section
          class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-4"
          data-testid="pr-history-section"
        >
          <div class="flex items-baseline justify-between gap-4 flex-wrap">
            <div class="flex flex-col gap-1">
              <h2 class="text-base font-bold text-on-surface m-0">PR geschiedenis</h2>
              <p class="text-xs text-on-surface-variant m-0">
                Laatste {{ (history?.sessions || []).length }} PR{{ (history?.sessions || []).length === 1 ? '' : 's' }}.
              </p>
            </div>
            <div class="flex flex-wrap gap-1.5" data-testid="pr-state-chips">
              <button
                v-for="chip in STATE_CHIPS"
                :key="chip.value || 'all'"
                type="button"
                @click="selectedPrState = chip.value"
                :class="[
                  'text-[11px] font-semibold uppercase tracking-widest px-3 py-1.5 rounded-md transition-colors',
                  selectedPrState === chip.value
                    ? 'bg-primary/15 text-primary'
                    : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high',
                ]"
                :data-testid="`pr-chip-${chip.value || 'all'}`"
              >
                {{ chip.label }}
              </button>
            </div>
          </div>

          <div v-if="historyLoading && !history" class="flex flex-col gap-3">
            <div v-for="n in 3" :key="n" class="h-24 rounded-xl bg-surface-container animate-pulse"></div>
          </div>
          <div
            v-else-if="historyError"
            class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
          >
            {{ historyError }}
          </div>
          <div v-else-if="filteredSessions.length" class="flex flex-col gap-3" data-testid="pr-list">
            <div
              v-for="s in filteredSessions"
              :key="sessionIdOf(s)"
              @click="openSession(sessionIdOf(s))"
              :data-testid="`pr-card-${sessionIdOf(s)}`"
            >
              <PRCard
                :pr-number="s.pr_number"
                :pr-title="s.pr_title"
                :repo-full-name="s.repo_full_name"
                :state="s.state"
                :submitted-at="s.submitted_at"
                :graded-at="s.graded_at"
                :rubric-score-avg="s.rubric_score_avg"
                :course-name="s.course_name"
              />
            </div>
          </div>
          <p v-else-if="selectedPrState" class="text-on-surface-variant text-sm m-0">
            Geen PRs in deze status.
          </p>
          <p v-else class="text-on-surface-variant text-sm m-0">
            Deze student heeft nog geen PRs.
          </p>
        </section>

        <!-- Loading sentinel (invisible, used only by tests) -->
        <span v-if="anyLoading" data-testid="any-loading" class="sr-only">loading</span>
      </div>
    </div>
  </AppShell>
</template>
