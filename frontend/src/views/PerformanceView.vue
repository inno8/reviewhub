<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

type PeriodType = 'DAILY' | 'WEEKLY' | 'MONTHLY';

interface UserOption {
  id: number;
  username: string;
}

interface Recommendation {
  type: 'book' | 'article' | 'tutorial' | 'video';
  title: string;
  url: string;
  category: string;
  reason: string;
}

interface PerformanceData {
  userId: number;
  projectId: number;
  periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  periodStart: string;
  periodEnd: string;
  findingCount: number;
  commitCount: number;
  findingsByCategory: Record<string, number>;
  strengths: string[];
  growthAreas: string[];
  recommendations: Recommendation[];
  fixRate: number;
}

interface CodeProgression {
  weekStart: string;
  weekEnd: string;
  findingCount: number;
  categories: Record<string, number>;
  trend: 'improving' | 'stable' | 'declining';
}

const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const users = ref<UserOption[]>([]);
const selectedUserId = ref<number | null>(null);
const periodType = ref<PeriodType>('WEEKLY');
const loading = ref(false);
const performance = ref<PerformanceData | null>(null);
const trends = ref<CodeProgression[]>([]);
const groupedRecommendations = ref<Record<string, Recommendation[]>>({});

const trendDirection = computed<'up' | 'down' | 'flat'>(() => {
  if (trends.value.length < 2) return 'flat';
  const previous = trends.value[trends.value.length - 2]?.findingCount ?? 0;
  const current = trends.value[trends.value.length - 1]?.findingCount ?? 0;
  if (current < previous) return 'down';
  if (current > previous) return 'up';
  return 'flat';
});

function formatCategory(category: string) {
  return category
    .split('_')
    .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
    .join(' ');
}

function iconForRecommendation(type: Recommendation['type']) {
  if (type === 'book') return 'menu_book';
  if (type === 'video') return 'video_library';
  if (type === 'tutorial') return 'developer_board';
  return 'article';
}

async function fetchUsers() {
  const { data } = await api.users.list();
  users.value = data.users.map((user: any) => ({ id: user.id, username: user.username }));
  if (!selectedUserId.value) {
    selectedUserId.value = users.value[0]?.id || authStore.user?.id || null;
  }
}

async function loadPerformance() {
  if (!selectedUserId.value || !projectsStore.selectedProjectId) return;
  loading.value = true;
  try {
    const [performanceResponse, trendsResponse, recommendationResponse] = await Promise.all([
      api.performance.get(selectedUserId.value, {
        projectId: projectsStore.selectedProjectId,
        periodType: periodType.value,
      }),
      api.performance.trends(selectedUserId.value, {
        projectId: projectsStore.selectedProjectId,
        weeks: 8,
      }),
      api.performance.recommendations(selectedUserId.value, {
        projectId: projectsStore.selectedProjectId,
      }),
    ]);

    performance.value = performanceResponse.data;
    trends.value = trendsResponse.data;
    groupedRecommendations.value = recommendationResponse.data.groupedByCategory || {};
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await Promise.all([projectsStore.fetchProjects(), fetchUsers()]);
  await loadPerformance();
});

watch(
  () => [selectedUserId.value, projectsStore.selectedProjectId, periodType.value],
  async () => {
    await loadPerformance();
  },
);
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
          <!-- Developer Selector -->
          <div class="relative group">
            <button class="flex items-center gap-3 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20 hover:border-primary/50 transition-colors">
              <div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center text-xs font-bold text-primary">
                {{ users.find(u => u.id === selectedUserId)?.username?.charAt(0).toUpperCase() || 'U' }}
              </div>
              <span class="text-sm font-semibold">{{ users.find(u => u.id === selectedUserId)?.username || 'Select' }}</span>
              <span class="material-symbols-outlined text-sm">expand_more</span>
            </button>
          </div>
          <!-- Time Period Tabs -->
          <div class="flex bg-surface-container-lowest p-1 rounded-lg">
            <button
              v-for="period in ['DAILY', 'WEEKLY', 'MONTHLY']"
              :key="period"
              :class="[
                'px-4 py-1.5 text-xs font-bold rounded-md transition-all',
                periodType === period
                  ? 'bg-surface-container text-primary shadow-sm'
                  : 'text-outline hover:text-on-surface'
              ]"
              @click="periodType = period as PeriodType"
            >
              {{ period.charAt(0) + period.slice(1).toLowerCase() }}
            </button>
          </div>
        </div>
      </section>

      <!-- Stats Grid -->
      <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Total Commits</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ performance?.commitCount ?? 0 }}</h3>
            <span class="flex items-center text-primary text-xs font-bold bg-primary/10 px-2 py-1 rounded-full">
              <span class="material-symbols-outlined text-xs mr-1">trending_up</span>
              12%
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-tertiary">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Total Findings</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ performance?.findingCount ?? 0 }}</h3>
            <span class="flex items-center text-tertiary text-xs font-bold bg-tertiary/10 px-2 py-1 rounded-full">
              <span class="material-symbols-outlined text-xs mr-1">trending_down</span>
              8%
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary-container">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Fix Rate %</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">{{ performance?.fixRate ?? 0 }}%</h3>
            <span class="flex items-center text-primary-container text-xs font-bold bg-primary-container/10 px-2 py-1 rounded-full">
              <span class="material-symbols-outlined text-xs mr-1">check_circle</span>
              High
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-outline">
          <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Review Velocity</p>
          <div class="flex items-end justify-between">
            <h3 class="text-3xl font-black">1.4d</h3>
            <span class="text-outline text-xs font-bold">avg/PR</span>
          </div>
        </div>
      </section>

      <!-- Analysis Section: Strengths & Growth -->
      <section class="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-12">
        <!-- Strengths -->
        <div class="space-y-6">
          <h4 class="text-xl font-bold flex items-center gap-2">
            <span class="w-8 h-1 bg-primary rounded-full"></span>
            Strengths
          </h4>
          <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
            <div
              v-for="category in (performance?.strengths || ['API Design', 'Runtime Performance'])"
              :key="`strength-${category}`"
              class="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10"
            >
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                  <span class="material-symbols-outlined">api</span>
                </div>
                <div>
                  <p class="font-bold">{{ formatCategory(category) }}</p>
                  <p class="text-xs text-outline">Exceptional consistency</p>
                </div>
              </div>
              <span class="material-symbols-outlined text-primary" style="font-variation-settings: 'FILL' 1;">check_circle</span>
            </div>
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
              v-for="category in (performance?.growthAreas || ['Security', 'Testing Coverage'])"
              :key="`growth-${category}`"
              class="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/10"
            >
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-lg bg-tertiary/10 flex items-center justify-center text-tertiary">
                  <span class="material-symbols-outlined">security</span>
                </div>
                <div>
                  <p class="font-bold">{{ formatCategory(category) }}</p>
                  <p class="text-xs text-outline">Focus on improvement</p>
                </div>
              </div>
              <span class="material-symbols-outlined text-tertiary">arrow_upward</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Chart Section -->
      <section class="mb-12">
        <div class="bg-surface-container-low rounded-3xl p-8 border border-outline-variant/10 overflow-hidden relative">
          <div class="flex justify-between items-center mb-10">
            <div>
              <h4 class="text-xl font-bold">Finding Trends</h4>
              <p class="text-sm text-outline">Frequency of detected issues over last 30 days</p>
            </div>
            <div class="flex gap-2">
              <div class="flex items-center gap-2 text-xs font-bold">
                <span class="w-3 h-3 rounded-full bg-primary"></span> Critical
              </div>
              <div class="flex items-center gap-2 text-xs font-bold ml-4">
                <span class="w-3 h-3 rounded-full bg-tertiary"></span> Minor
              </div>
            </div>
          </div>
          <!-- Simulated Chart -->
          <div class="h-64 w-full flex items-end gap-1 relative">
            <div class="absolute inset-0 flex flex-col justify-between pointer-events-none">
              <div class="w-full h-[1px] bg-outline-variant/10"></div>
              <div class="w-full h-[1px] bg-outline-variant/10"></div>
              <div class="w-full h-[1px] bg-outline-variant/10"></div>
              <div class="w-full h-[1px] bg-outline-variant/10"></div>
            </div>
            <svg class="absolute inset-0 w-full h-full overflow-visible" preserveAspectRatio="none">
              <path d="M0 180 Q 100 150, 200 190 T 400 120 T 600 160 T 800 80 T 1000 140" fill="none" stroke="#a2c9ff" stroke-linecap="round" stroke-width="4"></path>
              <path d="M0 180 Q 100 150, 200 190 T 400 120 T 600 160 T 800 80 T 1000 140 V 256 H 0 Z" fill="url(#grad1)" opacity="0.1"></path>
              <defs>
                <linearGradient id="grad1" x1="0%" x2="0%" y1="0%" y2="100%">
                  <stop offset="0%" style="stop-color:#a2c9ff;stop-opacity:1"></stop>
                  <stop offset="100%" style="stop-color:#a2c9ff;stop-opacity:0"></stop>
                </linearGradient>
              </defs>
            </svg>
            <div class="flex-1 h-full flex items-end justify-around z-10">
              <div class="w-2 h-2 rounded-full bg-primary ring-4 ring-background"></div>
              <div class="w-2 h-2 rounded-full bg-primary ring-4 ring-background"></div>
              <div class="w-2 h-2 rounded-full bg-primary ring-4 ring-background"></div>
              <div class="w-2 h-2 rounded-full bg-primary ring-4 ring-background"></div>
              <div class="w-2 h-2 rounded-full bg-primary ring-4 ring-background"></div>
            </div>
          </div>
          <div class="flex justify-between mt-4 px-2 text-[10px] font-bold text-outline uppercase tracking-widest">
            <span>Week 01</span>
            <span>Week 02</span>
            <span>Week 03</span>
            <span>Week 04</span>
          </div>
        </div>
      </section>

      <!-- Recommendations -->
      <section class="space-y-6">
        <h4 class="text-2xl font-black tracking-tight">Recommended Learning</h4>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div
            v-for="(items, category) in groupedRecommendations"
            :key="`rec-${category}`"
            class="glass-panel p-6 rounded-2xl border border-outline-variant/10 group hover:border-primary/30 transition-all duration-300"
          >
            <div class="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <span class="material-symbols-outlined text-primary">menu_book</span>
            </div>
            <h5 class="font-bold text-lg mb-2">{{ formatCategory(category) }}</h5>
            <p class="text-sm text-outline mb-6">{{ items[0]?.reason || 'Improve your skills in this area.' }}</p>
            <a
              v-if="items[0]"
              :href="items[0].url"
              target="_blank"
              class="flex items-center gap-2 text-primary font-bold text-sm group/link"
            >
              View Resource
              <span class="material-symbols-outlined text-sm group-hover/link:translate-x-1 transition-transform">arrow_forward</span>
            </a>
          </div>
          <!-- Default cards if no recommendations -->
          <template v-if="!Object.keys(groupedRecommendations).length">
            <div class="glass-panel p-6 rounded-2xl border border-outline-variant/10 group hover:border-primary/30 transition-all duration-300">
              <div class="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <span class="material-symbols-outlined text-primary">menu_book</span>
              </div>
              <h5 class="font-bold text-lg mb-2">Advanced Security Patterns</h5>
              <p class="text-sm text-outline mb-6">Master OWASP Top 10 mitigation strategies for modern web applications.</p>
              <a href="#" class="flex items-center gap-2 text-primary font-bold text-sm group/link">
                View Resource
                <span class="material-symbols-outlined text-sm group-hover/link:translate-x-1 transition-transform">arrow_forward</span>
              </a>
            </div>
            <div class="glass-panel p-6 rounded-2xl border border-outline-variant/10 group hover:border-tertiary/30 transition-all duration-300">
              <div class="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <span class="material-symbols-outlined text-tertiary">video_library</span>
              </div>
              <h5 class="font-bold text-lg mb-2">Refactoring Legacy Code</h5>
              <p class="text-sm text-outline mb-6">Expert video series on decomposing monoliths into maintainable services.</p>
              <a href="#" class="flex items-center gap-2 text-tertiary font-bold text-sm group/link">
                View Resource
                <span class="material-symbols-outlined text-sm group-hover/link:translate-x-1 transition-transform">arrow_forward</span>
              </a>
            </div>
            <div class="glass-panel p-6 rounded-2xl border border-outline-variant/10 group hover:border-primary-container/30 transition-all duration-300">
              <div class="w-12 h-12 rounded-xl bg-surface-container flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                <span class="material-symbols-outlined text-primary-container">developer_board</span>
              </div>
              <h5 class="font-bold text-lg mb-2">Clean Architecture Workshop</h5>
              <p class="text-sm text-outline mb-6">Interactive documentation on dependency inversion and domain design.</p>
              <a href="#" class="flex items-center gap-2 text-primary-container font-bold text-sm group/link">
                View Resource
                <span class="material-symbols-outlined text-sm group-hover/link:translate-x-1 transition-transform">arrow_forward</span>
              </a>
            </div>
          </template>
        </div>
      </section>

      <p v-if="loading" class="text-sm text-outline mt-8">Loading performance insights...</p>
    </div>
  </AppShell>
</template>
