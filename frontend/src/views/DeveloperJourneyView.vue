<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip as ChartTooltip,
  Legend,
} from 'chart.js';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, ChartTooltip, Legend);

const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const loading = ref(false);
const journey = ref<any>(null);

// Admin user selection
const adminUsers = ref<any[]>([]);
const adminLoading = ref(false);
const selectedUserId = ref<number | null>(null);
const showUserList = computed(() => authStore.isAdmin && !selectedUserId.value);

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (!authStore.isAdmin) {
    selectedUserId.value = authStore.user?.id ?? null;
  } else {
    await loadAdminUsers();
  }
  if (selectedUserId.value) await loadJourney();
});

watch(() => projectsStore.selectedProjectId, async () => {
  if (selectedUserId.value) await loadJourney();
});

async function loadAdminUsers() {
  adminLoading.value = true;
  try {
    const res = await api.users.adminStats({});
    adminUsers.value = res.data;
  } catch { /* ignore */ } finally { adminLoading.value = false; }
}

function selectUser(userId: number) {
  selectedUserId.value = userId;
  loadJourney();
}

async function loadJourney() {
  if (!selectedUserId.value) return;
  loading.value = true;
  try {
    const res = await api.skills.journey(selectedUserId.value, projectsStore.selectedProjectId);
    journey.value = res.data;
  } catch (e) {
    console.error('Failed to load journey:', e);
  } finally {
    loading.value = false;
  }
}

// ── Computed chart data ────────────────────────────────────────────────

const scoreChartData = computed(() => {
  if (!journey.value?.timeline?.length) return null;
  const entries = journey.value.timeline.filter((t: any) => t.score !== null);
  if (!entries.length) return null;

  // Moving average (window of 3)
  const raw = entries.map((t: any) => t.score);
  const smoothed = raw.map((_: number, i: number) => {
    const start = Math.max(0, i - 1);
    const end = Math.min(raw.length, i + 2);
    const slice = raw.slice(start, end);
    return Math.round(slice.reduce((a: number, b: number) => a + b, 0) / slice.length * 10) / 10;
  });

  return {
    labels: entries.map((t: any) => {
      const d = new Date(t.date);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }),
    datasets: [
      {
        label: 'Score',
        data: raw,
        borderColor: 'rgba(148, 163, 184, 0.3)',
        backgroundColor: 'transparent',
        pointBackgroundColor: entries.map((t: any) => {
          if (t.score >= 80) return 'rgba(74, 222, 128, 1)';
          if (t.score >= 60) return 'rgba(96, 165, 250, 1)';
          if (t.score >= 40) return 'rgba(250, 204, 21, 1)';
          return 'rgba(248, 113, 113, 1)';
        }),
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 1,
        tension: 0,
      },
      {
        label: 'Trend',
        data: smoothed,
        borderColor: 'rgba(96, 165, 250, 0.9)',
        backgroundColor: 'rgba(96, 165, 250, 0.08)',
        fill: true,
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.4,
      },
    ],
  };
});

const scoreChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      ticks: { color: 'rgba(148, 163, 184, 0.6)', font: { size: 10 } },
      grid: { color: 'rgba(148, 163, 184, 0.06)' },
    },
    x: {
      ticks: { color: 'rgba(148, 163, 184, 0.6)', font: { size: 9 }, maxRotation: 45 },
      grid: { display: false },
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
        title: (items: any) => {
          const idx = items[0]?.dataIndex;
          const entries = journey.value.timeline.filter((t: any) => t.score !== null);
          const t = entries[idx];
          return t ? `${t.commitSha} — ${t.message}` : '';
        },
        label: (ctx: any) => {
          if (ctx.datasetIndex === 0) return `Score: ${ctx.parsed.y}/100`;
          return `Trend: ${ctx.parsed.y}/100`;
        },
      },
    },
  },
}));

// ── Skill evolution chart ──────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  'Code Quality': 'rgba(96, 165, 250, 0.9)',
  'Design Patterns': 'rgba(168, 85, 247, 0.9)',
  'Logic & Algorithms': 'rgba(74, 222, 128, 0.9)',
  'Security': 'rgba(248, 113, 113, 0.9)',
  'Testing': 'rgba(250, 204, 21, 0.9)',
  'Frontend': 'rgba(251, 146, 60, 0.9)',
  'Backend': 'rgba(45, 212, 191, 0.9)',
  'Devops': 'rgba(244, 114, 182, 0.9)',
};

const skillEvolutionData = computed(() => {
  if (!journey.value?.skillEvolution?.length) return null;
  // Collect all unique dates
  const allDates = new Set<string>();
  journey.value.skillEvolution.forEach((cat: any) =>
    cat.dataPoints.forEach((dp: any) => allDates.add(dp.date))
  );
  const sortedDates = [...allDates].sort();
  if (!sortedDates.length) return null;

  return {
    labels: sortedDates.map((d: string) => {
      const date = new Date(d);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }),
    datasets: journey.value.skillEvolution.map((cat: any) => {
      const scoreByDate: Record<string, number> = {};
      cat.dataPoints.forEach((dp: any) => { scoreByDate[dp.date] = dp.avgScore; });
      return {
        label: cat.category,
        data: sortedDates.map((d: string) => scoreByDate[d] ?? null),
        borderColor: CATEGORY_COLORS[cat.category] || 'rgba(148, 163, 184, 0.9)',
        backgroundColor: 'transparent',
        pointRadius: 2,
        borderWidth: 2,
        tension: 0.3,
        spanGaps: true,
      };
    }),
  };
});

const skillEvolutionOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      ticks: { color: 'rgba(148, 163, 184, 0.6)', font: { size: 10 } },
      grid: { color: 'rgba(148, 163, 184, 0.06)' },
    },
    x: {
      ticks: { color: 'rgba(148, 163, 184, 0.6)', font: { size: 9 }, maxRotation: 45 },
      grid: { display: false },
    },
  },
  plugins: {
    legend: {
      display: true,
      position: 'bottom' as const,
      labels: { color: '#94a3b8', font: { size: 10 }, boxWidth: 12, padding: 12 },
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

// ── Helpers ────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function proofIcon(status: string): string {
  switch (status) {
    case 'proven': return 'verified';
    case 'reinforced': return 'military_tech';
    case 'relapsed': return 'replay';
    case 'pending': return 'hourglass_top';
    case 'taught': return 'school';
    default: return 'help';
  }
}

function proofColor(status: string): string {
  switch (status) {
    case 'proven': return 'text-green-400';
    case 'reinforced': return 'text-purple-400';
    case 'relapsed': return 'text-red-400';
    case 'pending': return 'text-yellow-400';
    case 'taught': return 'text-blue-400';
    default: return 'text-outline';
  }
}

function proofBg(status: string): string {
  switch (status) {
    case 'proven': return 'bg-green-500/10 border-green-500/20';
    case 'reinforced': return 'bg-purple-500/10 border-purple-500/20';
    case 'relapsed': return 'bg-red-500/10 border-red-500/20';
    case 'pending': return 'bg-yellow-500/10 border-yellow-500/20';
    case 'taught': return 'bg-blue-500/10 border-blue-500/20';
    default: return 'bg-surface-container border-outline-variant/10';
  }
}

function levelColor(level: string): string {
  const l = level?.toLowerCase() || '';
  if (l.includes('master')) return 'text-purple-400';
  if (l.includes('expert')) return 'text-primary';
  if (l.includes('proficient')) return 'text-green-400';
  if (l.includes('competent')) return 'text-yellow-400';
  if (l.includes('beginner')) return 'text-orange-400';
  return 'text-outline';
}

function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-blue-400';
  if (score >= 40) return 'text-yellow-400';
  return 'text-red-400';
}

function trendIcon(trend: string): string {
  if (trend === 'up') return 'trending_up';
  if (trend === 'down') return 'trending_down';
  return 'trending_flat';
}

function trendColor(trend: string): string {
  if (trend === 'up') return 'text-green-400';
  if (trend === 'down') return 'text-red-400';
  return 'text-outline';
}
</script>

<template>
  <AppShell>
    <div class="flex-1 p-6 max-w-7xl mx-auto w-full space-y-6">
      <!-- Header -->
      <div>
        <p class="text-xs text-primary font-semibold tracking-wider mb-1">DEVELOPER JOURNEY</p>
        <h2 class="text-2xl font-bold">
          <template v-if="journey">{{ journey.userName }}'s Growth Story</template>
          <template v-else>Developer Journey</template>
        </h2>
        <p class="text-sm text-outline mt-1">Track progression from first commit to current level</p>
      </div>

      <!-- Admin: user picker -->
      <div v-if="showUserList" class="space-y-3">
        <p class="text-sm text-outline">Select a developer to view their journey:</p>
        <div v-if="adminLoading" class="flex items-center gap-2 text-outline text-sm py-8">
          <span class="material-symbols-outlined animate-spin text-sm">progress_activity</span>
          Loading users...
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div
            v-for="u in adminUsers"
            :key="u.id"
            class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 cursor-pointer hover:border-primary/30 transition-colors"
            @click="selectUser(u.id)"
          >
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-primary/15 flex items-center justify-center text-sm font-bold text-primary">
                {{ (u.display_name || u.username || 'U').substring(0, 2).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <p class="font-semibold text-sm truncate">{{ u.display_name || u.username }}</p>
                <p class="text-xs text-outline truncate">{{ u.email }}</p>
              </div>
            </div>
            <div class="mt-3 flex gap-4 text-xs text-outline">
              <span>{{ u.total_evaluations }} evals</span>
              <span>{{ u.total_findings }} findings</span>
              <span>{{ Math.round(u.avg_score || 0) }}% avg</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-else-if="loading" class="flex items-center justify-center py-20">
        <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
      </div>

      <!-- Journey Content -->
      <template v-else-if="journey">
        <!-- Back button for admin -->
        <button
          v-if="authStore.isAdmin"
          class="flex items-center gap-1 text-sm text-outline hover:text-on-surface transition-colors mb-2"
          @click="selectedUserId = null; journey = null;"
        >
          <span class="material-symbols-outlined text-base">arrow_back</span>
          All Users
        </button>

        <!-- Stats Overview -->
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <div class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 text-center">
            <p class="text-xs text-outline">LEVEL</p>
            <p class="text-lg font-black mt-1" :class="levelColor(journey.stats.level)">
              {{ journey.stats.level }}
            </p>
          </div>
          <div class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 text-center">
            <p class="text-xs text-outline">EVALUATIONS</p>
            <p class="text-lg font-black mt-1">{{ journey.stats.totalEvaluations }}</p>
          </div>
          <div class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 text-center">
            <p class="text-xs text-outline">SCORE GROWTH</p>
            <p class="text-lg font-black mt-1" :class="journey.stats.scoreGrowth >= 0 ? 'text-green-400' : 'text-red-400'">
              {{ journey.stats.scoreGrowth >= 0 ? '+' : '' }}{{ journey.stats.scoreGrowth }}%
            </p>
            <p class="text-[10px] text-outline mt-0.5">{{ journey.stats.firstAvgScore }}% &rarr; {{ journey.stats.lastAvgScore }}%</p>
          </div>
          <div class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 text-center">
            <p class="text-xs text-outline">CONCEPTS PROVEN</p>
            <p class="text-lg font-black mt-1 text-green-400">{{ journey.proofStats.proven }}</p>
          </div>
          <div class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 text-center">
            <p class="text-xs text-outline">REINFORCED</p>
            <p class="text-lg font-black mt-1 text-purple-400">{{ journey.proofStats.reinforced }}</p>
          </div>
          <div class="bg-surface-container-low rounded-lg border border-outline-variant/10 p-4 text-center">
            <p class="text-xs text-outline">PENDING PROOF</p>
            <p class="text-lg font-black mt-1 text-yellow-400">{{ journey.proofStats.pending }}</p>
          </div>
        </div>

        <!-- Score Timeline -->
        <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="font-bold text-base">Score Timeline</h3>
              <p class="text-xs text-outline mt-0.5">
                Every commit scored, with trend line showing growth trajectory
              </p>
            </div>
            <div v-if="journey.stats.firstEvaluation" class="text-right text-xs text-outline">
              {{ formatDate(journey.stats.firstEvaluation) }} &mdash; {{ formatDate(journey.stats.lastEvaluation) }}
            </div>
          </div>
          <div v-if="scoreChartData" class="h-[280px]">
            <Line :data="scoreChartData" :options="scoreChartOptions" />
          </div>
          <div v-else class="py-12 text-center text-outline text-sm">
            <span class="material-symbols-outlined text-xl">timeline</span>
            <p class="mt-2">No evaluation data yet. Push some commits to start tracking!</p>
          </div>
        </div>

        <!-- Skill Evolution -->
        <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
          <div class="mb-4">
            <h3 class="font-bold text-base">Skill Evolution</h3>
            <p class="text-xs text-outline mt-0.5">
              How each skill category score has changed over time
            </p>
          </div>
          <div v-if="skillEvolutionData" class="h-[300px]">
            <Line :data="skillEvolutionData" :options="skillEvolutionOptions" />
          </div>
          <div v-else class="py-12 text-center text-outline text-sm">
            <span class="material-symbols-outlined text-xl">insights</span>
            <p class="mt-2">Skill evolution data will appear after Bayesian observations are recorded</p>
          </div>
        </div>

        <!-- Current Skill Snapshot + Learning Milestones side by side -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Current Skills -->
          <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
            <h3 class="font-bold text-base mb-4">Current Skill Snapshot</h3>
            <div v-if="journey.currentSkills.length" class="space-y-4">
              <div v-for="cat in journey.currentSkills" :key="cat.category">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-semibold">{{ cat.category }}</span>
                  <span class="text-sm font-bold" :class="scoreColor(cat.avgScore)">{{ cat.avgScore }}%</span>
                </div>
                <div class="space-y-1">
                  <div
                    v-for="skill in cat.skills"
                    :key="skill.name"
                    class="flex items-center justify-between text-xs px-2 py-1.5 rounded hover:bg-surface-container-lowest transition-colors"
                  >
                    <span class="text-on-surface-variant truncate mr-2">{{ skill.name }}</span>
                    <div class="flex items-center gap-2 shrink-0">
                      <span
                        v-if="skill.trend"
                        class="material-symbols-outlined text-xs"
                        :class="trendColor(skill.trend)"
                      >{{ trendIcon(skill.trend) }}</span>
                      <span v-if="skill.provenConcepts" class="text-green-400 text-[10px]">
                        {{ skill.provenConcepts }} proven
                      </span>
                      <span
                        class="text-[10px] font-bold"
                        :class="levelColor(skill.levelLabel || '')"
                      >{{ skill.levelLabel || '' }}</span>
                      <span class="text-outline w-8 text-right font-medium">{{ skill.score }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="py-8 text-center text-outline text-sm">
              <span class="material-symbols-outlined text-xl">school</span>
              <p class="mt-2">No skill data yet</p>
            </div>
          </div>

          <!-- Learning Milestones -->
          <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
            <h3 class="font-bold text-base mb-1">Learning Milestones</h3>
            <p class="text-xs text-outline mb-4">
              Concepts taught through Fix & Learn, tracked for behavioral proof in future commits
            </p>
            <div v-if="journey.milestones.length" class="space-y-3 max-h-[400px] overflow-y-auto">
              <div
                v-for="(m, i) in journey.milestones"
                :key="i"
                class="rounded-lg border p-3"
                :class="proofBg(m.type)"
              >
                <div class="flex items-start gap-2">
                  <span
                    class="material-symbols-outlined text-lg mt-0.5"
                    :class="proofColor(m.type)"
                  >{{ proofIcon(m.type) }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="text-xs font-bold uppercase" :class="proofColor(m.type)">
                        {{ m.type }}
                      </span>
                      <span class="text-xs text-outline">{{ m.skill }}</span>
                    </div>
                    <p class="text-sm mt-1">{{ m.issueType.replace(/_/g, ' ') }}</p>
                    <p v-if="m.conceptSummary" class="text-xs text-outline mt-1 line-clamp-2">
                      {{ m.conceptSummary }}
                    </p>
                    <div class="flex gap-3 mt-2 text-[10px] text-outline">
                      <span v-if="m.taughtAt">Taught {{ formatDate(m.taughtAt) }}</span>
                      <span v-if="m.provenAt" class="text-green-400">
                        Proven {{ formatDate(m.provenAt) }} ({{ m.proofCommit }})
                      </span>
                      <span v-if="m.relapsedAt" class="text-red-400">
                        Relapsed {{ formatDate(m.relapsedAt) }} ({{ m.relapseCommit }})
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="py-8 text-center text-outline text-sm">
              <span class="material-symbols-outlined text-xl">lightbulb</span>
              <p class="mt-2">No milestones yet</p>
              <p class="text-xs mt-1">Complete Fix & Learn exercises to create learning milestones</p>
            </div>
          </div>
        </div>

        <!-- Commit History -->
        <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
          <h3 class="font-bold text-base mb-1">Commit History</h3>
          <p class="text-xs text-outline mb-4">
            {{ journey.timeline.length }} commits evaluated
          </p>
          <div v-if="journey.timeline.length" class="space-y-1 max-h-[400px] overflow-y-auto">
            <div
              v-for="(commit, i) in [...journey.timeline].reverse()"
              :key="i"
              class="flex items-center gap-3 px-3 py-2 rounded hover:bg-surface-container-lowest transition-colors text-xs"
            >
              <span class="text-outline w-6 text-right shrink-0">#{{ commit.index }}</span>
              <code class="text-primary font-mono shrink-0">{{ commit.commitSha }}</code>
              <span class="truncate flex-1 text-on-surface-variant">{{ commit.message }}</span>
              <div class="flex items-center gap-3 shrink-0">
                <span class="text-outline">{{ commit.filesChanged }}F</span>
                <span v-if="commit.findingCount" class="text-yellow-400">
                  {{ commit.findingCount }} issues
                </span>
                <span
                  v-if="commit.score !== null"
                  class="font-bold w-10 text-right"
                  :class="scoreColor(commit.score)"
                >{{ commit.score }}%</span>
              </div>
              <span class="text-outline text-[10px] w-16 text-right shrink-0">
                {{ formatDate(commit.date) }}
              </span>
            </div>
          </div>
        </div>
      </template>

      <!-- No data at all -->
      <div v-else-if="!loading && !showUserList" class="py-20 text-center text-outline">
        <span class="material-symbols-outlined text-4xl">explore</span>
        <p class="mt-3 text-base">No journey data available</p>
        <p class="text-sm mt-1">Push commits to start building your developer journey</p>
      </div>
    </div>
  </AppShell>
</template>
