<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';

type PeriodType = 'DAILY' | 'WEEKLY' | 'MONTHLY';

interface UserOption {
  id: number;
  username: string;
  email: string;
}

interface PerformanceData {
  findingCount: number;
  commitCount: number;
  strengths: string[];
  growthAreas: string[];
  recommendations: Recommendation[];
  fixRate: number;
}

interface Recommendation {
  type: 'book' | 'article' | 'tutorial' | 'video';
  title: string;
  url: string;
  category: string;
  reason: string;
}

interface TrendData {
  weekStart: string;
  weekEnd: string;
  findingCount: number;
  categories: Record<string, number>;
  trend: 'improving' | 'stable' | 'declining';
}

const projectsStore = useProjectsStore();

const users = ref<UserOption[]>([]);
const selectedUserId = ref<number | null>(null);
const periodType = ref<PeriodType>('WEEKLY');
const loading = ref(false);
const performance = ref<PerformanceData | null>(null);
const trends = ref<TrendData[]>([]);

onMounted(async () => {
  await projectsStore.fetchProjects();
  await fetchProjectUsers();
});

watch(() => projectsStore.selectedProjectId, async () => {
  await fetchProjectUsers();
});

watch([() => selectedUserId.value, () => periodType.value], async () => {
  await loadPerformance();
});

watch([() => selectedUserId.value, () => projectsStore.selectedProjectId], async () => {
  await loadTrends();
});

async function fetchProjectUsers() {
  if (!projectsStore.selectedProjectId) return;
  try {
    const { data } = await api.users.list();
    users.value = data.users.filter((u: any) => u.role === 'INTERN');
    if (users.value.length > 0 && !selectedUserId.value) {
      selectedUserId.value = users.value[0].id;
    }
    await Promise.all([loadPerformance(), loadTrends()]);
  } catch (e) {
    console.error('Failed to fetch users', e);
  }
}

async function loadPerformance() {
  if (!selectedUserId.value || !projectsStore.selectedProjectId) return;
  loading.value = true;
  try {
    const { data } = await api.performance.get(selectedUserId.value, {
      projectId: projectsStore.selectedProjectId,
      periodType: periodType.value,
    });
    performance.value = data;
  } catch (e) {
    console.error('Failed to load performance', e);
    performance.value = null;
  } finally {
    loading.value = false;
  }
}

async function loadTrends() {
  if (!selectedUserId.value || !projectsStore.selectedProjectId) return;
  try {
    const { data } = await api.performance.trends(selectedUserId.value, {
      projectId: projectsStore.selectedProjectId,
      weeks: 8,
    });
    trends.value = data;
  } catch (e) {
    console.error('Failed to load trends', e);
    trends.value = [];
  }
}

const CRITICAL_CATEGORIES = ['SECURITY', 'ARCHITECTURE'];

function formatWeekLabel(dateStr: string): string {
  const date = new Date(dateStr);
  return `W${getWeekNumber(date)}`;
}

function getWeekNumber(date: Date): number {
  const firstDayOfYear = new Date(date.getFullYear(), 0, 1);
  const pastDaysOfYear = (date.getTime() - firstDayOfYear.getTime()) / 86400000;
  return Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
}

const criticalPoints = computed(() =>
  trends.value.map((t) => ({
    label: formatWeekLabel(t.weekStart),
    value: CRITICAL_CATEGORIES.reduce((sum, cat) => sum + (t.categories[cat] || 0), 0),
  })),
);

const minorPoints = computed(() =>
  trends.value.map((t) => ({
    label: formatWeekLabel(t.weekStart),
    value: Object.entries(t.categories)
      .filter(([cat]) => !CRITICAL_CATEGORIES.includes(cat))
      .reduce((sum, [, count]) => sum + count, 0),
  })),
);

const totalCritical = computed(() => criticalPoints.value.reduce((sum, p) => sum + p.value, 0));
const totalMinor = computed(() => minorPoints.value.reduce((sum, p) => sum + p.value, 0));

// Real % change badges from trends data
const commitChange = computed(() => {
  if (trends.value.length < 2) return null;
  const current = trends.value[trends.value.length - 1]?.findingCount || 0;
  const previous = trends.value[trends.value.length - 2]?.findingCount || 0;
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 100);
});

const findingChange = computed(() => {
  if (trends.value.length < 2) return null;
  const current = trends.value[trends.value.length - 1]?.findingCount || 0;
  const previous = trends.value[trends.value.length - 2]?.findingCount || 0;
  if (previous === 0) return null;
  return Math.round(((current - previous) / previous) * 100);
});

const recommendations = computed(() => performance.value?.recommendations || []);

function getRecommendationIcon(type: string): string {
  switch (type) {
    case 'book': return 'menu_book';
    case 'article': return 'article';
    case 'tutorial': return 'school';
    case 'video': return 'play_circle';
    default: return 'link';
  }
}

const RECOMMENDATION_COLORS = ['primary', 'tertiary', 'primary-container'] as const;

function formatCategory(category: string) {
  return category
    .split('_')
    .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
    .join(' ');
}

const selectedUser = computed(() => users.value.find(u => u.id === selectedUserId.value));
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Editorial Header Section -->
      <section class="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Analytics Overview</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">Performance Insights</h1>
        </div>
        <div class="flex flex-wrap items-center gap-4 bg-surface-container-low p-1.5 rounded-xl">
          <!-- Project Selector -->
          <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
            <span class="material-symbols-outlined text-sm text-outline">folder</span>
            <select
              :value="projectsStore.selectedProjectId"
              @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
              class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
            >
              <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
                {{ project.displayName }}
              </option>
            </select>
          </div>

          <!-- Developer Selector -->
          <div class="flex items-center gap-3 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
            <div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center text-xs font-bold text-primary">
              {{ selectedUser?.username?.charAt(0).toUpperCase() || 'U' }}
            </div>
            <select
              v-model="selectedUserId"
              class="bg-transparent border-none text-sm font-semibold text-on-surface focus:ring-0 cursor-pointer"
            >
              <option v-for="user in users" :key="user.id" :value="user.id">
                {{ user.username }}
              </option>
            </select>
          </div>

          <!-- Time Period Tabs -->
          <div class="flex bg-surface-container-lowest p-1 rounded-lg">
            <button
              v-for="period in (['DAILY', 'WEEKLY', 'MONTHLY'] as PeriodType[])"
              :key="period"
              :class="[
                'px-4 py-1.5 text-xs font-bold rounded-md transition-all',
                periodType === period
                  ? 'bg-surface-container text-primary shadow-sm'
                  : 'text-outline hover:text-on-surface'
              ]"
              @click="periodType = period"
            >
              {{ period.charAt(0) + period.slice(1).toLowerCase() }}
            </button>
          </div>
        </div>
      </section>

      <!-- Stats Grid -->
      <section v-if="performance" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Total Commits</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ performance.commitCount }}</h3>
            <span v-if="commitChange !== null" :class="[
              'flex items-center text-xs font-bold px-2 py-1 rounded-full',
              commitChange >= 0 ? 'text-primary bg-primary/10' : 'text-error bg-error/10'
            ]">
              <span class="material-symbols-outlined text-xs mr-1">{{ commitChange >= 0 ? 'trending_up' : 'trending_down' }}</span>
              {{ Math.abs(commitChange) }}%
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-tertiary">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Total Findings</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ performance.findingCount }}</h3>
            <span v-if="findingChange !== null" :class="[
              'flex items-center text-xs font-bold px-2 py-1 rounded-full',
              findingChange <= 0 ? 'text-primary bg-primary/10' : 'text-error bg-error/10'
            ]">
              <span class="material-symbols-outlined text-xs mr-1">{{ findingChange <= 0 ? 'trending_down' : 'trending_up' }}</span>
              {{ Math.abs(findingChange) }}%
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary-container">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Fix Rate %</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ performance.fixRate }}%</h3>
            <span class="flex items-center text-primary-container text-xs font-bold bg-primary-container/10 px-2 py-1 rounded-full">
              <span class="material-symbols-outlined text-xs mr-1">check_circle</span>
              {{ performance.fixRate >= 50 ? 'Good' : 'Needs work' }}
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-outline">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Review Velocity</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ trends.length }}w</h3>
            <span class="text-outline text-xs font-bold">tracked</span>
          </div>
        </div>
      </section>
      <section v-else-if="!loading" class="mb-12">
        <div class="bg-surface-container-low p-8 rounded-xl text-center">
          <span class="material-symbols-outlined text-4xl text-outline mb-2">analytics</span>
          <p class="text-outline">No performance data available. Select a user and project to get started.</p>
        </div>
      </section>

      <!-- Analysis Section: Strengths & Growth -->
      <section v-if="performance" class="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-12">
        <!-- Strengths -->
        <div class="space-y-6">
          <h4 class="text-xl font-bold flex items-center gap-2">
            <span class="w-8 h-1 bg-primary rounded-full"></span>
            Strengths
          </h4>
          <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
            <div
              v-for="strength in performance.strengths"
              :key="`strength-${strength}`"
              class="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10"
            >
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                  <span class="material-symbols-outlined">check_circle</span>
                </div>
                <div>
                  <p class="font-bold">{{ formatCategory(strength) }}</p>
                  <p class="text-xs text-outline">Consistent quality</p>
                </div>
              </div>
              <span class="material-symbols-outlined text-primary" style="font-variation-settings: 'FILL' 1;">verified</span>
            </div>
            <p v-if="!performance.strengths.length" class="text-sm text-outline text-center py-4">No strengths identified yet</p>
          </div>
        </div>

        <!-- Growth Areas -->
        <div class="space-y-6">
          <h4 class="text-xl font-bold flex items-center gap-2">
            <span class="w-8 h-1 bg-tertiary rounded-full"></span>
            Growth Areas
          </h4>
          <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
            <div
              v-for="area in performance.growthAreas"
              :key="`growth-${area}`"
              class="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10"
            >
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-lg bg-tertiary/10 flex items-center justify-center text-tertiary">
                  <span class="material-symbols-outlined">trending_up</span>
                </div>
                <div>
                  <p class="font-bold">{{ formatCategory(area) }}</p>
                  <p class="text-xs text-outline">Focus on improvement</p>
                </div>
              </div>
              <span class="material-symbols-outlined text-tertiary">arrow_upward</span>
            </div>
            <p v-if="!performance.growthAreas.length" class="text-sm text-outline text-center py-4">No growth areas identified yet</p>
          </div>
        </div>
      </section>

      <!-- Chart Section -->
      <section class="mb-12">
        <div class="bg-surface-container-low rounded-3xl p-8 border border-outline-variant/10 overflow-hidden relative">
          <div class="flex justify-between items-center mb-4">
            <div>
              <h4 class="text-xl font-bold">Finding Trends</h4>
              <p class="text-sm text-outline">Issue frequency over the last 8 weeks</p>
            </div>
            <div class="flex gap-4">
              <div class="flex items-center gap-2 text-xs font-bold">
                <span class="w-3 h-3 rounded-full bg-primary"></span>
                Critical ({{ totalCritical }})
              </div>
              <div class="flex items-center gap-2 text-xs font-bold">
                <span class="w-3 h-3 rounded-full" style="background-color: #F78166"></span>
                Minor ({{ totalMinor }})
              </div>
            </div>
          </div>
          <TrendChart
            title=""
            :points="criticalPoints"
            :secondary-points="minorPoints"
            :width="800"
            :height="300"
          />
        </div>
      </section>

      <!-- Recommendations (from API) -->
      <section v-if="recommendations.length" class="space-y-6 mb-12">
        <h4 class="text-2xl font-black tracking-tight">Recommended Learning</h4>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div
            v-for="(rec, index) in recommendations.slice(0, 3)"
            :key="rec.url"
            class="glass-panel p-6 rounded-2xl border border-outline-variant/10 group hover:border-primary/30 transition-all duration-300"
          >
            <div class="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="material-symbols-outlined" :class="`text-${RECOMMENDATION_COLORS[index % 3]}`">{{ getRecommendationIcon(rec.type) }}</span>
            </div>
            <h5 class="font-bold text-lg mb-2">{{ rec.title }}</h5>
            <p class="text-sm text-outline mb-6">{{ rec.reason }}</p>
            <a :href="rec.url" target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 text-primary font-bold text-sm group/link">
              View Resource
              <span class="material-symbols-outlined text-sm group-hover/link:translate-x-1 transition-transform">arrow_forward</span>
            </a>
          </div>
        </div>
      </section>

      <p v-if="loading" class="text-sm text-outline mt-8">Loading performance insights...</p>
    </div>
  </AppShell>
</template>
