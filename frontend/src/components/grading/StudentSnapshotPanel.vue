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
</script>

<template>
  <aside class="snapshot-panel" data-testid="student-snapshot">
    <header class="panel-header">
      <h3>Student snapshot</h3>
      <router-link
        v-if="profileLink && data?.student.id"
        :to="{ name: 'grading-student-profile', params: { id: data.student.id } }"
        class="link"
        data-testid="snapshot-profile-link"
      >
        Full profile →
      </router-link>
    </header>

    <div v-if="loading" class="loading">Loading snapshot…</div>
    <div v-else-if="error" class="error-banner">{{ error }}</div>
    <div v-else-if="data" class="panel-body">
      <!-- Student + cohort -->
      <div class="student-meta">
        <div class="student-name">{{ data.student.name }}</div>
        <div class="student-sub">
          <span v-if="data.student.cohort" class="cohort-pill">
            {{ data.student.cohort.name }}
          </span>
          <span class="muted">{{ data.student.email }}</span>
        </div>
      </div>

      <!-- Radar -->
      <section v-if="data.skill_radar.length >= 3" class="radar-section">
        <div class="radar-wrap">
          <Radar :data="radarData" :options="radarOptions" />
        </div>
      </section>
      <section v-else-if="data.skill_radar.length > 0" class="radar-fallback">
        <div v-for="s in data.skill_radar" :key="s.category" class="bar-row">
          <div class="bar-label">
            <span>{{ s.category }}</span>
            <span class="muted">{{ Math.round(s.score) }}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: s.score + '%' }"></div>
          </div>
        </div>
      </section>
      <section v-else class="empty-block">
        <p class="muted">No skill data yet.</p>
      </section>

      <!-- Recent activity -->
      <section class="activity">
        <div class="stat">
          <div class="stat-value">{{ data.recent_activity.prs_last_30d }}</div>
          <div class="stat-label">PRs (30d)</div>
        </div>
        <div class="stat">
          <div class="stat-value">{{ Math.round(data.recent_activity.avg_bayesian_score) }}</div>
          <div class="stat-label">Avg skill</div>
        </div>
      </section>

      <!-- Trending -->
      <section v-if="data.trending_up.length || data.trending_down.length" class="trending">
        <div v-if="data.trending_up.length" class="trend-col">
          <h4 class="trend-title trend-up">Trending up</h4>
          <ul>
            <li v-for="s in data.trending_up" :key="'u-' + s">{{ s }}</li>
          </ul>
        </div>
        <div v-if="data.trending_down.length" class="trend-col">
          <h4 class="trend-title trend-down">Trending down</h4>
          <ul>
            <li v-for="s in data.trending_down" :key="'d-' + s">{{ s }}</li>
          </ul>
        </div>
      </section>

      <!-- Recurring patterns -->
      <section class="patterns">
        <h4>Recurring patterns</h4>
        <ul v-if="data.recurring_patterns.length" class="pattern-list">
          <li
            v-for="p in data.recurring_patterns"
            :key="p.pattern_key"
            class="pattern-item"
            :class="severityClass(p.severity)"
            data-testid="pattern-item"
          >
            <div class="pattern-head">
              <span class="pattern-name">{{ formatPatternKey(p.pattern_key) }}</span>
              <span class="pattern-count">×{{ p.frequency }}</span>
            </div>
            <div class="pattern-meta">
              <span class="muted">{{ p.pattern_type }}</span>
              <span v-if="p.last_seen_days_ago !== null" class="muted">
                · {{ p.last_seen_days_ago }}d ago
              </span>
            </div>
          </li>
        </ul>
        <p v-else class="muted">No recurring issues. Nice work.</p>
      </section>

      <!-- Categories w/ trend (table) -->
      <section v-if="data.skill_radar.length" class="category-table">
        <h4>Skill categories</h4>
        <ul>
          <li v-for="s in data.skill_radar" :key="'c-' + s.category">
            <span class="cat-name">{{ s.category }}</span>
            <span class="cat-level muted">{{ s.level_label || '—' }}</span>
            <span class="cat-trend" :class="trendClass(s.trend)">{{ trendIcon(s.trend) }}</span>
            <span class="cat-score">{{ Math.round(s.score) }}</span>
          </li>
        </ul>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.snapshot-panel {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem 1.2rem;
  color: rgb(226 232 240);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1px solid rgb(30 41 59);
  padding-bottom: 0.6rem;
}
.panel-header h3 {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}
.link {
  color: rgb(147 197 253);
  font-size: 0.8rem;
  text-decoration: none;
}
.link:hover { text-decoration: underline; }

.loading, .error-banner {
  padding: 1rem;
  font-size: 0.85rem;
  color: rgb(148 163 184);
  text-align: center;
}
.error-banner {
  background: rgb(239 68 68 / 0.08);
  border: 1px solid rgb(239 68 68 / 0.3);
  color: rgb(252 165 165);
  border-radius: 0.5rem;
}

.student-meta .student-name {
  font-size: 1rem;
  font-weight: 600;
  color: rgb(241 245 249);
}
.student-sub {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.75rem;
  margin-top: 0.2rem;
}
.cohort-pill {
  background: rgb(59 130 246 / 0.15);
  color: rgb(147 197 253);
  padding: 0.15rem 0.5rem;
  border-radius: 0.35rem;
  font-weight: 500;
}
.muted { color: rgb(148 163 184); }

.radar-section .radar-wrap {
  height: 220px;
}
.radar-fallback .bar-row { margin-bottom: 0.5rem; }
.bar-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  margin-bottom: 0.25rem;
}
.bar-track {
  background: rgb(30 41 59);
  height: 0.4rem;
  border-radius: 0.2rem;
  overflow: hidden;
}
.bar-fill {
  background: rgb(96 165 250);
  height: 100%;
}

.activity {
  display: flex;
  gap: 1rem;
}
.stat {
  background: rgb(30 41 59 / 0.5);
  flex: 1;
  padding: 0.6rem 0.8rem;
  border-radius: 0.5rem;
}
.stat-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: rgb(241 245 249);
}
.stat-label {
  font-size: 0.7rem;
  color: rgb(148 163 184);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.trending {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.8rem;
  font-size: 0.8rem;
}
.trend-title {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.3rem;
}
.trend-title.trend-up { color: rgb(134 239 172); }
.trend-title.trend-down { color: rgb(252 165 165); }
.trending ul { list-style: none; padding: 0; margin: 0; }
.trending li {
  padding: 0.15rem 0;
  color: rgb(203 213 225);
}

.patterns h4, .category-table h4 {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(148 163 184);
  margin: 0 0 0.4rem 0;
}
.pattern-list { list-style: none; padding: 0; margin: 0; }
.pattern-item {
  padding: 0.45rem 0.6rem;
  border-radius: 0.4rem;
  margin-bottom: 0.4rem;
  background: rgb(30 41 59 / 0.5);
  border-left: 3px solid rgb(148 163 184);
}
.pattern-item.sev-warning {
  border-left-color: rgb(249 115 22);
  background: rgb(249 115 22 / 0.08);
}
.pattern-item.sev-info {
  border-left-color: rgb(59 130 246);
}
.pattern-head {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
  color: rgb(226 232 240);
}
.pattern-count { font-weight: 700; color: rgb(241 245 249); }
.pattern-meta { font-size: 0.7rem; margin-top: 0.1rem; }

.category-table ul { list-style: none; padding: 0; margin: 0; }
.category-table li {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 0.5rem;
  font-size: 0.8rem;
  padding: 0.25rem 0;
  border-top: 1px solid rgb(30 41 59 / 0.5);
  align-items: center;
}
.cat-name { color: rgb(226 232 240); }
.cat-level { font-size: 0.7rem; }
.cat-trend { font-weight: 700; }
.trend-up { color: rgb(134 239 172); }
.trend-down { color: rgb(252 165 165); }
.trend-flat { color: rgb(148 163 184); }
.cat-score {
  font-weight: 700;
  color: rgb(241 245 249);
  font-variant-numeric: tabular-nums;
  min-width: 2.2rem;
  text-align: right;
}

.empty-block { padding: 1rem 0; text-align: center; }
</style>
