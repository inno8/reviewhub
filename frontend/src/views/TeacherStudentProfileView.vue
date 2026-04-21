<script setup lang="ts">
/**
 * TeacherStudentProfileView — /grading/students/:id
 *
 * Teacher-facing full profile for one student. Combines:
 *   - Snapshot panel (skill radar, recurring patterns, activity)
 *   - Trajectory chart (weekly avg scores by category)
 *   - PR history table (last N grading sessions)
 *
 * Wires to:
 *   GET /api/grading/students/<id>/snapshot/
 *   GET /api/grading/students/<id>/trajectory/
 *   GET /api/grading/students/<id>/pr-history/
 *
 * Permissioning: handled server-side (can_view_student). Route is admin/teacher
 * only via router meta.admin gate.
 *
 * Workstream E3 of Nakijken Copilot v1 Scope B1.
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
import StudentSnapshotPanel from '@/components/grading/StudentSnapshotPanel.vue';
import AppShell from '@/components/layout/AppShell.vue';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

interface TrajectoryWeek {
  week_start: string;
  avg_score_per_category: Record<string, number>;
  prs_count: number;
  findings_count: number;
}
interface TrajectoryMilestone {
  date: string | null;
  event: string;
  skill: string;
}
interface Trajectory {
  student: { id: number; name: string; email: string };
  weeks: TrajectoryWeek[];
  milestones: TrajectoryMilestone[];
}
interface PRHistoryEntry {
  id: number;
  pr_url: string;
  pr_number: number;
  pr_title: string;
  repo_full_name: string;
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

const route = useRoute();
const router = useRouter();
const studentId = computed(() => Number(route.params.id));

const trajectoryLoading = ref(false);
const trajectoryError = ref<string | null>(null);
const trajectory = ref<Trajectory | null>(null);

const historyLoading = ref(false);
const historyError = ref<string | null>(null);
const history = ref<PRHistory | null>(null);

async function loadTrajectory() {
  if (!studentId.value) return;
  trajectoryLoading.value = true;
  trajectoryError.value = null;
  try {
    const { data } = await api.grading.students.trajectory(studentId.value);
    trajectory.value = data;
  } catch (err: any) {
    trajectoryError.value = err?.response?.data?.detail || err?.message || 'Failed to load trajectory';
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
    const { data } = await api.grading.students.prHistory(studentId.value);
    history.value = data;
  } catch (err: any) {
    historyError.value = err?.response?.data?.detail || err?.message || 'Failed to load PR history';
    history.value = null;
  } finally {
    historyLoading.value = false;
  }
}

onMounted(() => {
  loadTrajectory();
  loadHistory();
});
watch(studentId, () => {
  loadTrajectory();
  loadHistory();
});

const categoryColors = [
  'rgba(96, 165, 250, 0.9)',   // blue
  'rgba(74, 222, 128, 0.9)',   // green
  'rgba(250, 204, 21, 0.9)',   // yellow
  'rgba(248, 113, 113, 0.9)',  // red
  'rgba(167, 139, 250, 0.9)',  // purple
  'rgba(56, 189, 248, 0.9)',   // cyan
];

const trajectoryChart = computed(() => {
  const weeks = trajectory.value?.weeks || [];
  if (weeks.length === 0) return null;

  // Collect all categories seen across the window
  const catSet = new Set<string>();
  for (const w of weeks) {
    for (const k of Object.keys(w.avg_score_per_category || {})) catSet.add(k);
  }
  const categories = [...catSet];

  return {
    labels: weeks.map(w => w.week_start),
    datasets: categories.map((cat, i) => ({
      label: cat,
      data: weeks.map(w => w.avg_score_per_category?.[cat] ?? null),
      borderColor: categoryColors[i % categoryColors.length],
      backgroundColor: categoryColors[i % categoryColors.length].replace(/0\.9\)/, '0.1)'),
      tension: 0.3,
      spanGaps: true,
      pointRadius: 3,
      pointHoverRadius: 5,
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
      ticks: { color: 'rgba(148, 163, 184, 0.7)', font: { size: 10 } },
    },
  },
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { color: '#cbd5e1', font: { size: 11 }, padding: 12, usePointStyle: true },
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

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch { return iso; }
}

function stateBadgeClass(state: string): string {
  return `state-badge state-${state}`;
}

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push({ name: 'grading-inbox' });
}
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-7xl mx-auto">
        <header class="flex items-center gap-4 mb-8">
          <button
            @click="goBack"
            class="text-sm text-on-surface-variant hover:text-on-surface transition-colors"
          >
            ← Back
          </button>
          <h1 class="text-4xl font-extrabold text-on-surface tracking-tight m-0">
            Student profile
          </h1>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-[minmax(300px,380px)_1fr] gap-6 items-start">
          <!-- Left column: snapshot panel -->
          <div>
            <StudentSnapshotPanel :student-id="studentId" />
          </div>

          <!-- Right column: trajectory + history -->
          <div class="flex flex-col gap-6">
            <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
              <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
                <h2 class="text-base font-bold text-on-surface m-0">Skill trajectory</h2>
                <span class="text-xs text-on-surface-variant" v-if="trajectory">
                  {{ trajectory.weeks.length }} weeks
                </span>
              </div>
              <div class="p-6">
                <div v-if="trajectoryLoading" class="p-6 text-center text-outline text-sm">
                  Loading trajectory…
                </div>
                <div
                  v-else-if="trajectoryError"
                  class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
                >
                  {{ trajectoryError }}
                </div>
                <div v-else-if="trajectoryChart" class="h-[320px]">
                  <Line :data="trajectoryChart" :options="trajectoryOptions" />
                </div>
                <div v-else class="p-6 text-center text-outline text-sm">No trajectory data yet.</div>

                <!-- Milestones -->
                <div
                  v-if="trajectory?.milestones?.length"
                  class="mt-6 pt-4 border-t border-outline-variant/10"
                >
                  <h3 class="text-[11px] font-bold uppercase tracking-widest text-outline mb-2">
                    Milestones
                  </h3>
                  <ul class="list-none p-0 m-0">
                    <li
                      v-for="(m, i) in trajectory.milestones"
                      :key="i"
                      class="flex gap-2 text-sm py-1 border-t border-outline-variant/5 items-baseline first:border-t-0"
                    >
                      <span class="tabular-nums text-on-surface-variant min-w-[6rem]">
                        {{ formatDate(m.date) }}
                      </span>
                      <span class="text-on-surface">{{ m.event }}</span>
                      <span v-if="m.skill" class="text-on-surface-variant">· {{ m.skill }}</span>
                    </li>
                  </ul>
                </div>
              </div>
            </section>

            <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
              <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
                <h2 class="text-base font-bold text-on-surface m-0">Recent PRs</h2>
                <span class="text-xs text-on-surface-variant" v-if="history">
                  {{ history.sessions.length }} entries
                </span>
              </div>
              <div v-if="historyLoading" class="p-6 text-center text-outline text-sm">
                Loading PR history…
              </div>
              <div
                v-else-if="historyError"
                class="m-6 bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
              >
                {{ historyError }}
              </div>
              <div v-else-if="history?.sessions.length" class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                  <thead>
                    <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                      <th class="px-6 py-3">PR</th>
                      <th class="px-6 py-3">Course</th>
                      <th class="px-6 py-3">State</th>
                      <th class="px-6 py-3 text-right">Score</th>
                      <th class="px-6 py-3 text-right">Issues</th>
                      <th class="px-6 py-3">Submitted</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-outline-variant/5">
                    <tr
                      v-for="entry in history.sessions"
                      :key="entry.id"
                      class="cursor-pointer hover:bg-surface-container-high/40 transition-colors"
                      @click="router.push({ name: 'grading-session-detail', params: { id: entry.id } })"
                      data-testid="pr-history-row"
                    >
                      <td class="px-6 py-4">
                        <div class="text-sm font-semibold text-on-surface">
                          {{ entry.pr_title || '#' + entry.pr_number }}
                        </div>
                        <div class="text-[11px] text-on-surface-variant">
                          {{ entry.repo_full_name }} · #{{ entry.pr_number }}
                        </div>
                      </td>
                      <td class="px-6 py-4 text-sm text-on-surface-variant">
                        {{ entry.course_name || '—' }}
                      </td>
                      <td class="px-6 py-4">
                        <span :class="stateBadgeClass(entry.state)">{{ entry.state }}</span>
                      </td>
                      <td class="px-6 py-4 text-sm text-on-surface text-right tabular-nums">
                        {{ entry.rubric_score_avg !== null ? Math.round(entry.rubric_score_avg * 10) / 10 : '—' }}
                      </td>
                      <td class="px-6 py-4 text-sm text-on-surface-variant text-right tabular-nums">
                        {{ entry.findings_count }}
                      </td>
                      <td class="px-6 py-4 text-xs text-on-surface-variant">
                        {{ formatDate(entry.submitted_at) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else class="p-6 text-center text-outline text-sm">No graded PRs yet.</div>
            </section>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
/* State badges — dynamic class names via stateBadgeClass(), so kept as scoped CSS.
   Tokens map to Stitch palette via direct color values (no Tailwind runtime here). */
.state-badge {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: #262a31;
  color: #c0c7d4;
}
.state-badge.state-drafted { background: rgba(162, 201, 255, 0.15); color: #a2c9ff; }
.state-badge.state-reviewing { background: rgba(255, 186, 66, 0.15); color: #ffba42; }
.state-badge.state-posted { background: rgba(134, 239, 172, 0.15); color: rgb(134 239 172); }
.state-badge.state-partial { background: rgba(255, 186, 66, 0.15); color: #ffba42; }
.state-badge.state-failed { background: rgba(255, 180, 171, 0.15); color: #ffb4ab; }
</style>
