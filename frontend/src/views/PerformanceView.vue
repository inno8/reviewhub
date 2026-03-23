<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Card from '@/components/common/Card.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
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

const trendLabel = computed(() => {
  if (trendDirection.value === 'down') return 'Improving';
  if (trendDirection.value === 'up') return 'Needs Attention';
  return 'Stable';
});

const trendColor = computed(() => {
  if (trendDirection.value === 'down') return 'text-success';
  if (trendDirection.value === 'up') return 'text-error';
  return 'text-text-secondary';
});

const chartPoints = computed(() =>
  trends.value.map((entry) => ({
    label: formatWeek(entry.weekStart, entry.weekEnd),
    value: entry.findingCount,
  })),
);

const progressionComparisons = computed(() => {
  if (!trends.value.length) return [];
  return trends.value.slice(1).map((current, index) => {
    const previous = trends.value[index];
    const improvedCategories = Object.keys(current.categories).filter(
      (category) => (current.categories[category] || 0) < (previous.categories[category] || 0),
    );
    return {
      label: `${formatWeek(previous.weekStart, previous.weekEnd)} vs ${formatWeek(current.weekStart, current.weekEnd)}`,
      previousCount: previous.findingCount,
      currentCount: current.findingCount,
      improvedCategories,
    };
  });
});

const weekOneVsFour = computed(() => {
  if (trends.value.length < 4) return null;
  const weekOne = trends.value[0];
  const weekFour = trends.value[3];
  const improvedCategories = Object.keys(weekFour.categories).filter(
    (category) => (weekFour.categories[category] || 0) < (weekOne.categories[category] || 0),
  );
  return {
    label: `${formatWeek(weekOne.weekStart, weekOne.weekEnd)} vs ${formatWeek(weekFour.weekStart, weekFour.weekEnd)}`,
    weekOneCount: weekOne.findingCount,
    weekFourCount: weekFour.findingCount,
    improvedCategories,
  };
});

function formatCategory(category: string) {
  return category
    .split('_')
    .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
    .join(' ');
}

function iconForRecommendation(type: Recommendation['type']) {
  if (type === 'book') return '[Book]';
  if (type === 'video') return '[Video]';
  if (type === 'tutorial') return '[Tutorial]';
  return '[Article]';
}

function formatWeek(weekStart: string, weekEnd: string) {
  const start = new Date(weekStart);
  const end = new Date(weekEnd);
  return `${start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}-${end.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
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
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="space-y-6 p-6">
        <section class="space-y-4">
          <h2 class="text-xl font-semibold">Performance Insights</h2>
          <div class="flex flex-wrap items-end gap-3">
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Developer</label>
              <select
                v-model="selectedUserId"
                class="rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-sm"
              >
                <option :value="null" disabled>Select developer</option>
                <option v-for="user in users" :key="user.id" :value="user.id">{{ user.username }}</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Project</label>
              <select
                :value="projectsStore.selectedProjectId ?? ''"
                class="rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-sm"
                @change="projectsStore.setSelectedProject(($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null)"
              >
                <option disabled value="">Select project</option>
                <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
                  {{ project.displayName }}
                </option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Period</label>
              <div class="flex overflow-hidden rounded-lg border border-dark-border bg-dark-card text-sm">
                <button
                  v-for="period in ['DAILY', 'WEEKLY', 'MONTHLY']"
                  :key="period"
                  class="px-3 py-2"
                  :class="periodType === period ? 'bg-primary/20 text-primary' : 'text-text-secondary'"
                  @click="periodType = period as PeriodType"
                >
                  {{ period.charAt(0) + period.slice(1).toLowerCase() }}
                </button>
              </div>
            </div>
          </div>
        </section>

        <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p class="text-xs text-text-secondary">Total Commits</p>
            <p class="mt-2 text-2xl font-semibold">{{ performance?.commitCount ?? 0 }}</p>
          </Card>
          <Card>
            <p class="text-xs text-text-secondary">Total Findings</p>
            <p class="mt-2 text-2xl font-semibold">{{ performance?.findingCount ?? 0 }}</p>
          </Card>
          <Card>
            <p class="text-xs text-text-secondary">Fix Rate</p>
            <p class="mt-2 text-2xl font-semibold">{{ performance?.fixRate ?? 0 }}%</p>
          </Card>
          <Card>
            <p class="text-xs text-text-secondary">Trend</p>
            <p class="mt-2 text-xl font-semibold" :class="trendColor">
              <span v-if="trendDirection === 'up'">UP</span>
              <span v-else-if="trendDirection === 'down'">DOWN</span>
              <span v-else>FLAT</span>
              {{ trendLabel }}
            </p>
          </Card>
        </section>

        <section class="grid gap-4 lg:grid-cols-2">
          <Card>
            <h3 class="mb-3 text-lg font-semibold">Strengths</h3>
            <div v-if="performance?.strengths?.length" class="flex flex-wrap gap-2">
              <span
                v-for="category in performance.strengths"
                :key="`strength-${category}`"
                class="rounded-full border border-success/30 bg-success/10 px-3 py-1 text-sm text-success"
              >
                OK {{ formatCategory(category) }}
              </span>
            </div>
            <p v-else class="text-sm text-text-secondary">No strengths identified yet.</p>
          </Card>
          <Card>
            <h3 class="mb-3 text-lg font-semibold">Growth Areas</h3>
            <div v-if="performance?.growthAreas?.length" class="flex flex-wrap gap-2">
              <span
                v-for="category in performance.growthAreas"
                :key="`growth-${category}`"
                class="rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-sm text-warning"
              >
                NEXT {{ formatCategory(category) }}
              </span>
            </div>
            <p v-else class="text-sm text-text-secondary">No growth areas right now.</p>
          </Card>
        </section>

        <TrendChart title="Weekly Findings Trend" :points="chartPoints" />

        <section class="space-y-4">
          <h3 class="text-lg font-semibold">Recommendations</h3>
          <div v-if="!Object.keys(groupedRecommendations).length" class="rounded-xl border border-dark-border bg-dark-card p-4 text-sm text-text-secondary">
            No recommendations yet. Great work keeping findings low.
          </div>
          <div v-else class="space-y-4">
            <Card v-for="(items, category) in groupedRecommendations" :key="`rec-${category}`">
              <h4 class="mb-3 text-base font-semibold">
                {{ formatCategory(category) }}
                <span class="ml-2 rounded-full border border-dark-border px-2 py-0.5 text-xs text-text-secondary">
                  {{ items.length }} items
                </span>
              </h4>
              <div class="grid gap-3 md:grid-cols-2">
                <a
                  v-for="item in items"
                  :key="item.url"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="rounded-lg border border-dark-border bg-dark-bg p-3 transition hover:border-primary/60"
                >
                  <p class="text-sm">
                    <span class="mr-1">{{ iconForRecommendation(item.type) }}</span>
                    <span class="font-medium text-primary">{{ item.title }}</span>
                  </p>
                  <p class="mt-1 text-xs text-text-secondary">{{ item.reason }}</p>
                </a>
              </div>
            </Card>
          </div>
        </section>

        <section class="space-y-4">
          <h3 class="text-lg font-semibold">Your Progress</h3>
          <Card v-if="weekOneVsFour">
            <p class="text-sm font-medium">Week 1 vs Week 4</p>
            <p class="mt-1 text-sm text-text-secondary">{{ weekOneVsFour.label }}</p>
            <p class="mt-1 text-sm text-text-secondary">
              Findings: {{ weekOneVsFour.weekOneCount }} -> {{ weekOneVsFour.weekFourCount }}
            </p>
            <p class="mt-1 text-sm" :class="weekOneVsFour.improvedCategories.length ? 'text-success' : 'text-text-secondary'">
              <span v-if="weekOneVsFour.improvedCategories.length">
                Improved categories: {{ weekOneVsFour.improvedCategories.map(formatCategory).join(', ') }}
              </span>
              <span v-else>No category decreases between Week 1 and Week 4 yet.</span>
            </p>
          </Card>
          <Card>
            <div v-if="progressionComparisons.length" class="space-y-3">
              <div
                v-for="comparison in progressionComparisons"
                :key="comparison.label"
                class="rounded-lg border border-dark-border bg-dark-bg p-3"
              >
                <p class="text-sm font-medium">{{ comparison.label }}</p>
                <p class="mt-1 text-sm text-text-secondary">
                  Findings: {{ comparison.previousCount }} -> {{ comparison.currentCount }}
                </p>
                <p class="mt-1 text-sm" :class="comparison.improvedCategories.length ? 'text-success' : 'text-text-secondary'">
                  <span v-if="comparison.improvedCategories.length">
                    Improved categories: {{ comparison.improvedCategories.map(formatCategory).join(', ') }}
                  </span>
                  <span v-else>No category improvements in this step.</span>
                </p>
              </div>
            </div>
            <p v-else class="text-sm text-text-secondary">
              Not enough weekly history yet. Week 1 vs Week 4 comparisons appear once more trend data is available.
            </p>
          </Card>
        </section>

        <p v-if="loading" class="text-sm text-text-secondary">Loading performance insights...</p>
      </main>
    </div>
  </div>
</template>
