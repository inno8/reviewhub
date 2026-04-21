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
  <div class="teacher-profile">
    <header class="profile-header">
      <button @click="goBack" class="btn-ghost">← Back</button>
      <h1>Student profile</h1>
    </header>

    <div class="profile-grid">
      <!-- Left column: snapshot panel -->
      <div class="col-left">
        <StudentSnapshotPanel :student-id="studentId" />
      </div>

      <!-- Right column: trajectory + history -->
      <div class="col-right">
        <section class="card">
          <div class="card-head">
            <h2>Skill trajectory</h2>
            <span class="muted" v-if="trajectory">
              {{ trajectory.weeks.length }} weeks
            </span>
          </div>
          <div v-if="trajectoryLoading" class="loading">Loading trajectory…</div>
          <div v-else-if="trajectoryError" class="error-banner">{{ trajectoryError }}</div>
          <div v-else-if="trajectoryChart" class="chart-wrap">
            <Line :data="trajectoryChart" :options="trajectoryOptions" />
          </div>
          <div v-else class="empty">No trajectory data yet.</div>

          <!-- Milestones -->
          <div v-if="trajectory?.milestones?.length" class="milestones">
            <h3>Milestones</h3>
            <ul>
              <li v-for="(m, i) in trajectory.milestones" :key="i" class="milestone">
                <span class="milestone-date">{{ formatDate(m.date) }}</span>
                <span class="milestone-event">{{ m.event }}</span>
                <span v-if="m.skill" class="milestone-skill muted">· {{ m.skill }}</span>
              </li>
            </ul>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <h2>Recent PRs</h2>
            <span class="muted" v-if="history">
              {{ history.sessions.length }} entries
            </span>
          </div>
          <div v-if="historyLoading" class="loading">Loading PR history…</div>
          <div v-else-if="historyError" class="error-banner">{{ historyError }}</div>
          <div v-else-if="history?.sessions.length" class="table-wrap">
            <table class="pr-table">
              <thead>
                <tr>
                  <th>PR</th>
                  <th>Course</th>
                  <th>State</th>
                  <th class="num">Score</th>
                  <th class="num">Issues</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="entry in history.sessions"
                  :key="entry.id"
                  class="pr-row"
                  @click="router.push({ name: 'grading-session-detail', params: { id: entry.id } })"
                  data-testid="pr-history-row"
                >
                  <td class="pr-cell">
                    <div class="pr-title">{{ entry.pr_title || '#' + entry.pr_number }}</div>
                    <div class="muted tiny">{{ entry.repo_full_name }} · #{{ entry.pr_number }}</div>
                  </td>
                  <td>{{ entry.course_name || '—' }}</td>
                  <td><span :class="stateBadgeClass(entry.state)">{{ entry.state }}</span></td>
                  <td class="num">
                    {{ entry.rubric_score_avg !== null ? Math.round(entry.rubric_score_avg * 10) / 10 : '—' }}
                  </td>
                  <td class="num">{{ entry.findings_count }}</td>
                  <td>{{ formatDate(entry.submitted_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty">No graded PRs yet.</div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.teacher-profile {
  max-width: 1300px;
  margin: 0 auto;
  padding: 1.5rem;
  color: rgb(226 232 240);
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.profile-header h1 {
  font-size: 1.4rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}

.btn-ghost {
  background: transparent;
  border: none;
  color: rgb(148 163 184);
  cursor: pointer;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
}
.btn-ghost:hover { color: rgb(226 232 240); }

.profile-grid {
  display: grid;
  grid-template-columns: minmax(300px, 380px) 1fr;
  gap: 1.2rem;
  align-items: start;
}

@media (max-width: 900px) {
  .profile-grid { grid-template-columns: 1fr; }
}

.col-right {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.card {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem 1.2rem;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1px solid rgb(30 41 59);
  padding-bottom: 0.6rem;
  margin-bottom: 0.8rem;
}
.card-head h2 {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}

.muted { color: rgb(148 163 184); font-size: 0.8rem; }
.tiny { font-size: 0.7rem; }

.loading, .empty {
  padding: 1.5rem;
  text-align: center;
  color: rgb(148 163 184);
  font-size: 0.85rem;
}
.error-banner {
  background: rgb(239 68 68 / 0.08);
  border: 1px solid rgb(239 68 68 / 0.3);
  color: rgb(252 165 165);
  border-radius: 0.5rem;
  padding: 0.8rem 1rem;
  font-size: 0.85rem;
}

.chart-wrap { height: 320px; }

.milestones {
  margin-top: 1rem;
  padding-top: 0.8rem;
  border-top: 1px solid rgb(30 41 59);
}
.milestones h3 {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(148 163 184);
  margin: 0 0 0.4rem 0;
}
.milestones ul { list-style: none; padding: 0; margin: 0; }
.milestone {
  display: flex;
  gap: 0.6rem;
  font-size: 0.8rem;
  padding: 0.25rem 0;
  border-top: 1px solid rgb(30 41 59 / 0.5);
  align-items: baseline;
}
.milestone-date {
  font-variant-numeric: tabular-nums;
  color: rgb(148 163 184);
  min-width: 6rem;
}
.milestone-event { color: rgb(226 232 240); }

.table-wrap { overflow-x: auto; }
.pr-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.pr-table th {
  text-align: left;
  padding: 0.5rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(148 163 184);
  border-bottom: 1px solid rgb(30 41 59);
}
.pr-table th.num, .pr-table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.pr-table td {
  padding: 0.55rem 0.6rem;
  border-bottom: 1px solid rgb(30 41 59 / 0.5);
  color: rgb(203 213 225);
}
.pr-row { cursor: pointer; transition: background 0.1s; }
.pr-row:hover { background: rgb(30 41 59 / 0.3); }

.pr-cell .pr-title {
  color: rgb(226 232 240);
  font-weight: 500;
}

.state-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}
.state-badge.state-drafted { background: rgb(59 130 246 / 0.2); color: rgb(147 197 253); }
.state-badge.state-reviewing { background: rgb(234 179 8 / 0.2); color: rgb(253 224 71); }
.state-badge.state-posted { background: rgb(34 197 94 / 0.2); color: rgb(134 239 172); }
.state-badge.state-partial { background: rgb(249 115 22 / 0.2); color: rgb(253 186 116); }
.state-badge.state-failed { background: rgb(239 68 68 / 0.2); color: rgb(252 165 165); }
</style>
