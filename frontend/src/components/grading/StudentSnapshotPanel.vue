<script setup lang="ts">
/**
 * StudentSnapshotPanel — teacher-facing intelligence panel shown on the
 * grading session detail view. Wires to GET /api/grading/students/<id>/snapshot/.
 *
 * Shows:
 *   - Skill radar (by category, with confidence + trend)
 *   - Recurring patterns (unresolved anti-patterns)
 *   - Trending up / down skills
 *   - Recent activity (PRs in last 30d, avg bayesian score)
 *
 * Workstream E of Nakijken Copilot v1 Scope B1.
 */
import { ref, computed, watch, onMounted } from 'vue';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  type ChartOptions,
} from 'chart.js';
import { Radar } from 'vue-chartjs';
import { api } from '@/composables/useApi';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

interface SkillRadarItem {
  category: string;
  score: number;
  confidence: number;
  level_label: string | null;
  trend: 'up' | 'down' | 'stable';
}
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
interface RecurringPattern {
  pattern_key: string;
  pattern_type: string;
  frequency: number;
  last_seen_days_ago: number | null;
  severity: 'warning' | 'info' | string;
}
interface RecentActivity {
  prs_last_30d: number;
  avg_bayesian_score: number;
}
interface Snapshot {
  student: { id: number; name: string; email: string; cohort: { id: number; name: string } | null };
  skill_radar: SkillRadarItem[];
  per_skill?: PerSkillItem[];
  recurring_patterns: RecurringPattern[];
  trending_up: string[];
  trending_down: string[];
  recent_activity: RecentActivity;
  suggested_interventions: Array<Record<string, unknown>>;
}

const props = defineProps<{
  studentId: number | null;
  /** Optional — open the full profile page. */
  profileLink?: boolean;
}>();

const loading = ref(false);
const error = ref<string | null>(null);
const data = ref<Snapshot | null>(null);

async function load() {
  if (!props.studentId) return;
  loading.value = true;
  error.value = null;
  try {
    const { data: resp } = await api.grading.students.snapshot(props.studentId);
    data.value = resp;
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load snapshot';
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => props.studentId, load);

const radarData = computed(() => {
  const items = data.value?.skill_radar || [];
  return {
    labels: items.map(i => i.category),
    datasets: [
      {
        label: 'Skill score',
        data: items.map(i => i.score),
        backgroundColor: 'rgba(96, 165, 250, 0.15)',
        borderColor: 'rgba(96, 165, 250, 0.9)',
        borderWidth: 2,
        pointBackgroundColor: items.map(i => scoreColor(i.score)),
        pointBorderColor: 'transparent',
        pointRadius: 4,
        pointHoverRadius: 6,
      },
    ],
  };
});

const radarOptions = computed<ChartOptions<'radar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      ticks: {
        stepSize: 25,
        color: 'rgba(148, 163, 184, 0.5)',
        backdropColor: 'transparent',
        font: { size: 9 },
      },
      grid: { color: 'rgba(148, 163, 184, 0.12)' },
      angleLines: { color: 'rgba(148, 163, 184, 0.12)' },
      pointLabels: {
        color: '#cbd5e1',
        font: { size: 11, weight: 600 },
      },
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(148, 163, 184, 0.2)',
      borderWidth: 1,
      padding: 10,
      displayColors: false,
      callbacks: {
        label: (ctx) => `${ctx.label}: ${Math.round(ctx.parsed.r)}/100`,
      },
    },
  },
}));

function scoreColor(score: number): string {
  if (score >= 80) return 'rgba(96, 165, 250, 1)';
  if (score >= 60) return 'rgba(74, 222, 128, 1)';
  if (score >= 40) return 'rgba(250, 204, 21, 1)';
  return 'rgba(248, 113, 113, 1)';
}

function trendIcon(trend: string): string {
  if (trend === 'up') return '↑';
  if (trend === 'down') return '↓';
  return '→';
}
function trendClass(trend: string): string {
  if (trend === 'up') return 'trend-up';
  if (trend === 'down') return 'trend-down';
  return 'trend-flat';
}

function severityClass(sev: string): string {
  return sev === 'warning' ? 'sev-warning' : 'sev-info';
}

function formatPatternKey(key: string): string {
  return key.replace(/_/g, ' ');
}

// ── Per-criterion bar chart helpers ───────────────────────────────────
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

function formatDelta(delta: number): string {
  if (delta > 0) return `+${delta.toFixed(0)}`;
  if (delta < 0) return delta.toFixed(0);
  return '0';
}

const totalObservations = computed(() =>
  (data.value?.per_skill || []).reduce((s, r) => s + (r.observation_count || 0), 0),
);

const hasLearningProofData = computed(() =>
  (data.value?.per_skill || []).some(r => !!r.learning_proof_status),
);

interface ProofDot { emoji: string; tooltip: string; }
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
</script>

<template>
  <aside
    class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-5"
    data-testid="student-snapshot"
  >
    <header class="flex justify-between items-center border-b border-outline-variant/10 pb-4">
      <h3 class="text-base font-bold text-on-surface m-0">Student snapshot</h3>
      <router-link
        v-if="profileLink && data?.student.id"
        :to="{ name: 'grading-student-profile', params: { id: data.student.id } }"
        class="text-xs text-primary hover:underline"
        data-testid="snapshot-profile-link"
      >
        Full profile →
      </router-link>
    </header>

    <div v-if="loading" class="text-sm text-outline text-center py-4">Loading snapshot…</div>
    <div
      v-else-if="error"
      class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
    >
      {{ error }}
    </div>
    <div v-else-if="data" class="flex flex-col gap-5">
      <!-- Student + cohort -->
      <div>
        <div class="text-base font-bold text-on-surface">{{ data.student.name }}</div>
        <div class="flex gap-2 items-center text-xs mt-1">
          <span
            v-if="data.student.cohort"
            class="bg-primary/15 text-primary px-2 py-0.5 rounded-md font-semibold"
          >
            {{ data.student.cohort.name }}
          </span>
          <span class="text-on-surface-variant">{{ data.student.email }}</span>
        </div>
      </div>

      <!-- Radar -->
      <section v-if="data.skill_radar.length >= 3">
        <div class="h-[220px]">
          <Radar :data="radarData" :options="radarOptions" />
        </div>
      </section>
      <section v-else-if="data.skill_radar.length > 0" class="flex flex-col gap-2">
        <div v-for="s in data.skill_radar" :key="s.category">
          <div class="flex justify-between text-xs mb-1">
            <span class="text-on-surface">{{ s.category }}</span>
            <span class="text-on-surface-variant">{{ Math.round(s.score) }}</span>
          </div>
          <div class="bg-surface-container h-1.5 rounded overflow-hidden">
            <div class="bg-primary h-full" :style="{ width: s.score + '%' }"></div>
          </div>
        </div>
      </section>
      <section v-else class="py-4 text-center">
        <p class="text-on-surface-variant text-sm m-0">No skill data yet.</p>
      </section>

      <!-- Per criterium breakdown (6 Crebo criteria) -->
      <section v-if="data.per_skill && data.per_skill.length" data-testid="per-criterium">
        <div class="flex flex-col gap-1 mb-2">
          <h4 class="text-[11px] font-bold uppercase tracking-widest text-outline m-0">
            Per criterium
          </h4>
          <p class="text-[11px] text-on-surface-variant m-0">
            Bayesian-score 0-100, gebaseerd op {{ totalObservations }} observatie{{ totalObservations === 1 ? '' : 's' }}.
          </p>
        </div>
        <ul class="list-none p-0 m-0 flex flex-col gap-1.5">
          <li
            v-for="row in data.per_skill"
            :key="row.skill_slug"
            class="flex items-center gap-2 text-xs"
            :data-testid="`per-skill-${row.skill_slug}`"
          >
            <!-- Name + kerntaak pill -->
            <div class="flex items-center gap-1.5 min-w-[9rem] max-w-[9rem]">
              <span class="text-on-surface truncate" :title="row.display_name">
                {{ row.display_name }}
              </span>
              <span
                v-if="row.kerntaak"
                class="rounded-full bg-surface-container-high px-1.5 py-0.5 font-mono text-[9px] leading-none text-on-surface-variant shrink-0"
                :title="row.kerntaak"
              >{{ row.kerntaak }}</span>
            </div>

            <!-- Bar -->
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

            <!-- Score -->
            <span
              class="text-on-surface tabular-nums font-semibold min-w-[2rem] text-right"
              :class="row.bayesian_score === null ? 'text-outline font-normal' : ''"
            >
              {{ row.bayesian_score !== null ? Math.round(row.bayesian_score) : '—' }}
            </span>

            <!-- Learning-proof dot (hidden if no skill has one) -->
            <span
              v-if="hasLearningProofData"
              :title="learningProofDot(row).tooltip"
              class="text-[10px] leading-none w-3 text-center select-none"
            >{{ learningProofDot(row).emoji }}</span>

            <!-- Trend / delta -->
            <span
              v-if="row.observation_count < 3 && row.bayesian_score === null"
              class="text-outline text-[10px] min-w-[3rem] text-right"
            >— geen data</span>
            <span
              v-else-if="row.observation_count < 3"
              class="text-outline text-[10px] min-w-[3rem] text-right"
            >—</span>
            <span
              v-else
              class="min-w-[3rem] text-right text-[10px] tabular-nums flex items-center justify-end gap-1"
              :class="row.trend === 'up'
                ? 'text-[rgb(134,239,172)]'
                : row.trend === 'down' ? 'text-error' : 'text-on-surface-variant'"
            >
              <span class="font-bold">{{ trendIcon(row.trend) }}</span>
              <span>{{ formatDelta(row.trend_delta) }}</span>
            </span>
          </li>
        </ul>
      </section>

      <!-- Recent activity -->
      <section class="flex gap-3">
        <div class="flex-1 bg-surface-container rounded-lg px-4 py-3">
          <div class="text-xl font-bold text-on-surface">{{ data.recent_activity.prs_last_30d }}</div>
          <div class="text-[10px] text-outline uppercase tracking-wider font-semibold">PRs (30d)</div>
        </div>
        <div class="flex-1 bg-surface-container rounded-lg px-4 py-3">
          <div class="text-xl font-bold text-on-surface">
            {{ Math.round(data.recent_activity.avg_bayesian_score) }}
          </div>
          <div class="text-[10px] text-outline uppercase tracking-wider font-semibold">Avg skill</div>
        </div>
      </section>

      <!-- Trending -->
      <section
        v-if="data.trending_up.length || data.trending_down.length"
        class="grid grid-cols-2 gap-4 text-sm"
      >
        <div v-if="data.trending_up.length">
          <h4 class="text-[10px] font-bold uppercase tracking-widest mb-1" style="color: rgb(134 239 172);">
            Trending up
          </h4>
          <ul class="list-none p-0 m-0 text-on-surface-variant">
            <li v-for="s in data.trending_up" :key="'u-' + s" class="py-0.5">{{ s }}</li>
          </ul>
        </div>
        <div v-if="data.trending_down.length">
          <h4 class="text-[10px] font-bold uppercase tracking-widest mb-1 text-error">
            Trending down
          </h4>
          <ul class="list-none p-0 m-0 text-on-surface-variant">
            <li v-for="s in data.trending_down" :key="'d-' + s" class="py-0.5">{{ s }}</li>
          </ul>
        </div>
      </section>

      <!-- Recurring patterns -->
      <section>
        <h4 class="text-[11px] font-bold uppercase tracking-widest text-outline mb-2">
          Recurring patterns
        </h4>
        <ul v-if="data.recurring_patterns.length" class="list-none p-0 m-0 flex flex-col gap-1.5">
          <li
            v-for="p in data.recurring_patterns"
            :key="p.pattern_key"
            :class="[
              'px-3 py-2 rounded-lg border-l-2',
              severityClass(p.severity) === 'sev-warning'
                ? 'bg-tertiary/10 border-tertiary'
                : 'bg-surface-container border-primary',
            ]"
            data-testid="pattern-item"
          >
            <div class="flex justify-between text-sm text-on-surface">
              <span>{{ formatPatternKey(p.pattern_key) }}</span>
              <span class="font-bold">×{{ p.frequency }}</span>
            </div>
            <div class="text-[11px] mt-0.5 text-on-surface-variant">
              <span>{{ p.pattern_type }}</span>
              <span v-if="p.last_seen_days_ago !== null">
                · {{ p.last_seen_days_ago }}d ago
              </span>
            </div>
          </li>
        </ul>
        <p v-else class="text-on-surface-variant text-sm m-0">No recurring issues. Nice work.</p>
      </section>

      <!-- Categories w/ trend (table) -->
      <section v-if="data.skill_radar.length">
        <h4 class="text-[11px] font-bold uppercase tracking-widest text-outline mb-2">
          Skill categories
        </h4>
        <ul class="list-none p-0 m-0">
          <li
            v-for="s in data.skill_radar"
            :key="'c-' + s.category"
            class="grid grid-cols-[1fr_auto_auto_auto] gap-2 text-sm py-1.5 border-t border-outline-variant/5 items-center first:border-t-0"
          >
            <span class="text-on-surface">{{ s.category }}</span>
            <span class="text-[11px] text-on-surface-variant">{{ s.level_label || '—' }}</span>
            <span
              :class="[
                'font-bold text-sm',
                s.trend === 'up' ? 'text-[rgb(134,239,172)]' : s.trend === 'down' ? 'text-error' : 'text-on-surface-variant',
              ]"
            >
              {{ trendIcon(s.trend) }}
            </span>
            <span class="font-bold text-on-surface tabular-nums min-w-[2.2rem] text-right">
              {{ Math.round(s.score) }}
            </span>
          </li>
        </ul>
      </section>
    </div>
  </aside>
</template>

