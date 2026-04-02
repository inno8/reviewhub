<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import SkillRadarChart from '@/components/charts/SkillRadarChart.vue';
import ProgressChart from '@/components/charts/ProgressChart.vue';
import RecentFindings from '@/components/dashboard/RecentFindings.vue';
import SkillCard from '@/components/dashboard/SkillCard.vue';
import RecommendationsWidget from '@/components/skills/RecommendationsWidget.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

interface OverviewStats {
  total_evaluations: number;
  total_findings: number;
  avg_score: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  fixed_count: number;
  fix_rate: number;
}

interface CategoryScore {
  category: string;
  score: number;
  color: string;
}

interface WeeklyProgress {
  week_start: string;
  week_end: string;
  avg_score: number;
  evaluation_count: number;
  finding_count: number;
}

interface Finding {
  id: number;
  title: string;
  description: string;
  severity: string;
  file_path: string;
  line_start: number;
  is_fixed: boolean;
  created_at: string;
  skills: Array<{
    id: number;
    name: string;
    category: string;
  }>;
}

interface Skill {
  id: number;
  displayName: string;
  score: number;
  level: number;
}

interface SkillCategory {
  id: number;
  name: string;
  displayName: string;
  description: string;
  icon: string;
  skills: Skill[];
}

const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const loading = ref(false);
const overview = ref<OverviewStats | null>(null);
const categoryScores = ref<CategoryScore[]>([]);
const progressData = ref<WeeklyProgress[]>([]);
const recentFindings = ref<Finding[]>([]);
const skillCategories = ref<SkillCategory[]>([]);

onMounted(async () => {
  await projectsStore.fetchProjects();
  await loadDashboardData();
});

watch(() => projectsStore.selectedProjectId, async () => {
  await loadDashboardData();
});

async function loadDashboardData() {
  if (loading.value) return;
  
  loading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId ?? undefined;
    
    // Load all dashboard data in parallel
    const [overviewRes, skillsRes, progressRes, recentRes] = await Promise.all([
      api.dashboard.overview(projectId),
      api.dashboard.skills(projectId),
      api.dashboard.progress(projectId, 8),
      api.dashboard.recent(projectId, 10),
    ]);

    overview.value = overviewRes.data;
    categoryScores.value = skillsRes.data;
    progressData.value = progressRes.data;
    recentFindings.value = recentRes.data;

    // Also load full skill breakdown for cards
    if (authStore.user?.id) {
      const categoriesRes = await api.skills.user(authStore.user.id);
      skillCategories.value = categoriesRes.data.categories || [];
    }
  } catch (error) {
    console.error('Failed to load dashboard data:', error);
  } finally {
    loading.value = false;
  }
}

const statCards = computed(() => {
  if (!overview.value) return [];
  
  return [
    {
      label: 'Total Evaluations',
      value: overview.value.total_evaluations,
      icon: 'analytics',
      color: 'primary',
    },
    {
      label: 'Total Findings',
      value: overview.value.total_findings,
      icon: 'bug_report',
      color: 'tertiary',
      breakdown: `${overview.value.critical_count} critical, ${overview.value.warning_count} warning`,
    },
    {
      label: 'Fix Rate',
      value: `${overview.value.fix_rate}%`,
      icon: 'check_circle',
      color: 'primary-container',
      status: overview.value.fix_rate >= 70 ? 'Excellent' : overview.value.fix_rate >= 50 ? 'Good' : 'Needs Work',
    },
    {
      label: 'Average Score',
      value: `${overview.value.avg_score}%`,
      icon: 'school',
      color: 'secondary',
      status: overview.value.avg_score >= 80 ? 'Excellent' : overview.value.avg_score >= 60 ? 'Good' : 'Needs Work',
    },
  ];
});
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Header -->
      <section class="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Skills & Metrics</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">Developer Dashboard</h1>
          <p class="text-outline text-sm mt-2">Track your coding skills and progress over time</p>
        </div>
        
        <!-- Project Selector -->
        <div class="flex items-center gap-2 px-4 py-2 bg-surface-container-low rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">folder</span>
          <select
            :value="projectsStore.selectedProjectId"
            @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
            class="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer"
          >
            <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
              {{ project.displayName }}
            </option>
          </select>
        </div>
      </section>

      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-16">
        <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
      </div>

      <template v-else>
        <!-- Stats Grid -->
        <section v-if="overview" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div
            v-for="stat in statCards"
            :key="stat.label"
            class="bg-surface-container-low p-6 rounded-xl border-l-4"
            :class="`border-${stat.color}`"
          >
            <div class="flex items-start justify-between mb-4">
              <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                :class="`bg-${stat.color}/10`"
              >
                <span class="material-symbols-outlined" :class="`text-${stat.color}`">
                  {{ stat.icon }}
                </span>
              </div>
              <span v-if="stat.status" class="text-xs font-bold px-2 py-1 rounded-full"
                :class="stat.status === 'Excellent' ? 'bg-primary/10 text-primary' : stat.status === 'Good' ? 'bg-green-500/10 text-green-400' : 'bg-orange-500/10 text-orange-400'"
              >
                {{ stat.status }}
              </span>
            </div>
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">{{ stat.label }}</p>
            <div class="flex items-end justify-between">
              <h3 class="text-3xl font-black">{{ stat.value }}</h3>
            </div>
            <p v-if="stat.breakdown" class="text-xs text-outline mt-2">{{ stat.breakdown }}</p>
          </div>
        </section>

        <!-- Charts Grid -->
        <section class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          <!-- Radar Chart -->
          <SkillRadarChart
            :data="categoryScores"
            title="Skill Categories Overview"
          />

          <!-- Progress Chart -->
          <ProgressChart
            :data="progressData"
            title="Weekly Progress (Last 8 Weeks)"
          />
        </section>

        <!-- Recommendations Section -->
        <section class="mb-12">
          <RecommendationsWidget :project-id="projectsStore.selectedProjectId" />
        </section>

        <!-- Recent Findings & Skills -->
        <section class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          <!-- Recent Findings (2 cols) -->
          <div class="lg:col-span-2">
            <RecentFindings :findings="recentFindings" />
          </div>

          <!-- Quick Stats Card -->
          <div class="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10">
            <h4 class="text-xl font-bold mb-6">Quick Stats</h4>
            
            <div class="space-y-4">
              <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                <div class="flex items-center gap-3">
                  <span class="material-symbols-outlined text-error">error</span>
                  <span class="text-sm font-medium">Critical Issues</span>
                </div>
                <span class="text-xl font-black">{{ overview?.critical_count || 0 }}</span>
              </div>

              <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                <div class="flex items-center gap-3">
                  <span class="material-symbols-outlined text-yellow-500">warning</span>
                  <span class="text-sm font-medium">Warnings</span>
                </div>
                <span class="text-xl font-black">{{ overview?.warning_count || 0 }}</span>
              </div>

              <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                <div class="flex items-center gap-3">
                  <span class="material-symbols-outlined text-primary">check_circle</span>
                  <span class="text-sm font-medium">Fixed</span>
                </div>
                <span class="text-xl font-black">{{ overview?.fixed_count || 0 }}</span>
              </div>

              <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                <div class="flex items-center gap-3">
                  <span class="material-symbols-outlined text-outline">info</span>
                  <span class="text-sm font-medium">Info</span>
                </div>
                <span class="text-xl font-black">{{ overview?.info_count || 0 }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- Skill Cards Grid -->
        <section v-if="skillCategories.length > 0" class="mb-12">
          <h4 class="text-2xl font-black tracking-tight mb-6">Skill Breakdown by Category</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <SkillCard
              v-for="category in skillCategories"
              :key="category.id"
              :category="category"
            />
          </div>
        </section>

        <!-- Empty State -->
        <section v-if="!overview" class="text-center py-16">
          <span class="material-symbols-outlined text-6xl text-outline mb-4">insights</span>
          <h3 class="text-xl font-bold mb-2">No Dashboard Data Yet</h3>
          <p class="text-outline">Start pushing code to see your skill metrics and progress!</p>
        </section>
      </template>
    </div>
  </AppShell>
</template>
