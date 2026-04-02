<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
import SkillBreakdownDialog from '@/components/skills/SkillBreakdownDialog.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

type PeriodType = 'DAILY' | 'WEEKLY' | 'MONTHLY';

interface UserStat {
  id: number; username: string; email: string; display_name: string;
  total_commits: number; total_findings: number; fix_rate: number;
  categories: { id: number; name: string }[];
}

interface SkillCategory { id: number; name: string; displayName: string; description: string; icon: string; skills: { id: number; displayName: string; score: number; level: number }[]; }

const route = useRoute();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

// Admin user list
const adminUsers = ref<UserStat[]>([]);
const adminLoading = ref(false);
const adminSearch = ref('');
const adminCategories = ref<{ id: number; name: string }[]>([]);
const adminCategoryFilter = ref<number | null>(null);
const adminProjectFilter = ref<number | null>(null);

const selectedUserId = ref<number | null>(null);
const periodType = ref<PeriodType>('WEEKLY');
const loading = ref(false);
const performance = ref<any>(null);
const trends = ref<any[]>([]);
const skillCategories = ref<SkillCategory[]>([]);

const showUserList = computed(() => authStore.isAdmin && !selectedUserId.value);

onMounted(async () => {
  await projectsStore.fetchProjects();

  const queryUser = route.query.user;
  if (queryUser) selectedUserId.value = Number(queryUser);

  // Always seed our own userId so we see our own data by default
  if (!selectedUserId.value) {
    selectedUserId.value = authStore.user?.id ?? null;
  }

  if (authStore.isAdmin) {
    await loadAdminUsers();
  }

  if (selectedUserId.value) await loadAll();
});

watch([adminSearch, adminCategoryFilter, adminProjectFilter], () => loadAdminUsers());
watch(() => periodType.value, () => loadPerformance());
watch(() => projectsStore.selectedProjectId, () => { if (selectedUserId.value) loadAll(); });

async function loadAdminUsers() {
  adminLoading.value = true;
  try {
    const [usersRes, catsRes] = await Promise.all([
      api.users.adminStats({
        search: adminSearch.value || undefined,
        category: adminCategoryFilter.value || undefined,
        project: adminProjectFilter.value || undefined,
      } as any),
      api.categories.list(),
    ]);
    adminUsers.value = usersRes.data;
    adminCategories.value = (catsRes.data.results || catsRes.data || []);
  } catch { /* ignore */ } finally { adminLoading.value = false; }
}

function selectUser(userId: number) {
  selectedUserId.value = userId;
  loadAll();
}
function backToList() {
  selectedUserId.value = null;
  performance.value = null;
  trends.value = [];
  skillCategories.value = [];
}

async function loadAll() {
  await Promise.all([loadPerformance(), loadTrends(), loadSkills()]);
}

async function loadPerformance() {
  if (!selectedUserId.value) return;
  loading.value = true;
  try {
    const pid = projectsStore.selectedProjectId;
    const { data } = await api.performance.get(selectedUserId.value, {
      projectId: pid ?? undefined,
      periodType: periodType.value,
    });
    performance.value = data;
  } catch {
    performance.value = null;
  } finally {
    loading.value = false;
  }
}

async function loadTrends() {
  if (!selectedUserId.value) return;
  try {
    const pid = projectsStore.selectedProjectId;
    const { data } = await api.performance.trends(selectedUserId.value, { projectId: pid ?? undefined, weeks: 8 });
    trends.value = data;
  } catch {
    trends.value = [];
  }
}

async function loadSkills() {
  if (!selectedUserId.value) return;
  try {
    const pid = projectsStore.selectedProjectId;
    const { data } = await api.skills.user(selectedUserId.value, pid ?? undefined);
    skillCategories.value = data.categories;
  } catch {
    skillCategories.value = [];
  }
}

const CRITICAL_CATEGORIES = ['SECURITY', 'ARCHITECTURE'];
function formatWeekLabel(d: string) { const date = new Date(d); const start = new Date(date.getFullYear(), 0, 1); return `W${Math.ceil(((date.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7)}`; }
const criticalPoints = computed(() => trends.value.map(t => ({ label: formatWeekLabel(t.weekStart), value: CRITICAL_CATEGORIES.reduce((s: number, c: string) => s + (t.categories[c] || 0), 0) })));
const minorPoints = computed(() => trends.value.map(t => ({ label: formatWeekLabel(t.weekStart), value: Object.entries(t.categories).filter(([c]) => !CRITICAL_CATEGORIES.includes(c)).reduce((s: number, [, v]) => s + (v as number), 0) })));
const totalCritical = computed(() => criticalPoints.value.reduce((s, p) => s + p.value, 0));
const totalMinor = computed(() => minorPoints.value.reduce((s, p) => s + p.value, 0));

function formatCategory(c: string) { return c.split('_').map(p => p.charAt(0) + p.slice(1).toLowerCase()).join(' '); }
function getSkillLevel(s: number) { if (s >= 90) return 'Expert'; if (s >= 75) return 'Advanced'; if (s >= 50) return 'Intermediate'; if (s >= 25) return 'Developing'; return 'Beginner'; }
function getSkillBarColor(s: number) { if (s >= 90) return 'bg-primary'; if (s >= 75) return 'bg-green-500'; if (s >= 50) return 'bg-yellow-500'; if (s >= 25) return 'bg-orange-500'; return 'bg-red-500'; }
function categoryAverage(c: SkillCategory) { if (!c.skills.length) return 0; return Math.round(c.skills.reduce((s, sk) => s + sk.score, 0) / c.skills.length); }
function getRecommendationIcon(t: string) { return { book: 'menu_book', article: 'article', tutorial: 'school', video: 'play_circle' }[t] || 'link'; }

const selectedUserObj = computed(() => adminUsers.value.find(u => u.id === selectedUserId.value));
const recommendations = computed(() => performance.value?.recommendations || []);

const breakdownOpen = ref(false);
const breakdownSkillId = ref<number | null>(null);
function openSkillBreakdown(id: number) { breakdownSkillId.value = id; breakdownOpen.value = true; }
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Header -->
      <section class="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Analytics Overview</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">
            {{ showUserList ? 'Team Insights' : 'Performance Insights' }}
          </h1>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <button v-if="authStore.isAdmin && selectedUserId" @click="backToList"
            class="flex items-center gap-2 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20 text-sm hover:text-primary transition-colors">
            <span class="material-symbols-outlined text-sm">arrow_back</span> All Users
          </button>

          <template v-if="selectedUserId">
            <div v-if="selectedUserObj" class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
              <div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center text-xs font-bold text-primary">
                {{ selectedUserObj.username.charAt(0).toUpperCase() }}
              </div>
              <span class="text-sm font-semibold">{{ selectedUserObj.display_name || selectedUserObj.username }}</span>
            </div>

            <div v-if="!authStore.isAdmin && projectsStore.projects.length > 1" class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
              <span class="material-symbols-outlined text-sm text-outline">folder</span>
              <select :value="projectsStore.selectedProjectId"
                @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
                class="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer p-0">
                <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
              </select>
            </div>

            <div class="flex bg-surface-container-lowest p-1 rounded-lg">
              <button v-for="p in (['DAILY', 'WEEKLY', 'MONTHLY'] as PeriodType[])" :key="p"
                :class="['px-4 py-1.5 text-xs font-bold rounded-md transition-all', periodType === p ? 'bg-surface-container text-primary shadow-sm' : 'text-outline hover:text-on-surface']"
                @click="periodType = p">{{ p.charAt(0) + p.slice(1).toLowerCase() }}</button>
            </div>
          </template>
        </div>
      </section>

      <!-- ═══ Admin User List ═══ -->
      <template v-if="showUserList">
        <div class="flex flex-wrap items-center gap-3 mb-8">
          <input v-model="adminSearch" type="text" placeholder="Search..."
            class="w-56 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm" />
          <select v-model="adminCategoryFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">All Categories</option>
            <option v-for="c in adminCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="adminProjectFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">All Projects</option>
            <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
          </select>
        </div>

        <div v-if="adminLoading" class="flex items-center justify-center py-16">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          <div v-for="u in adminUsers" :key="u.id"
            class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all cursor-pointer"
            @click="selectUser(u.id)">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 rounded-lg bg-secondary-container flex items-center justify-center text-sm font-bold text-primary">
                {{ u.username.slice(0, 2).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <div class="text-sm font-bold text-on-surface truncate">{{ u.display_name || u.username }}</div>
                <div class="text-[11px] text-outline truncate">{{ u.email }}</div>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black">{{ u.total_commits }}</p>
                <p class="text-[8px] text-outline uppercase">Commits</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black">{{ u.total_findings }}</p>
                <p class="text-[8px] text-outline uppercase">Findings</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black" :class="u.fix_rate >= 50 ? 'text-green-400' : 'text-error'">{{ u.fix_rate }}%</p>
                <p class="text-[8px] text-outline uppercase">Fix Rate</p>
              </div>
            </div>
          </div>
          <div v-if="!adminUsers.length" class="col-span-full text-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">group</span>
            <p class="text-outline">No developers found</p>
          </div>
        </div>
      </template>

      <!-- ═══ User Performance View ═══ -->
      <template v-else>
        <!-- Stats Grid -->
        <section v-if="performance" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Total Commits</p>
            <h3 class="text-3xl font-black">{{ performance.commitCount }}</h3>
          </div>
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-tertiary">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Total Findings</p>
            <h3 class="text-3xl font-black">{{ performance.findingCount }}</h3>
          </div>
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary-container">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Fix Rate %</p>
            <h3 class="text-3xl font-black">{{ performance.fixRate }}%</h3>
          </div>
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-outline">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Review Velocity</p>
            <h3 class="text-3xl font-black">{{ performance.reviewVelocity !== null ? performance.reviewVelocity + 'd' : '—' }}</h3>
          </div>
        </section>
        <section v-else-if="!loading" class="mb-12">
          <div class="bg-surface-container-low p-8 rounded-xl text-center">
            <span class="material-symbols-outlined text-4xl text-outline mb-2">analytics</span>
            <p class="text-outline">No performance data available.</p>
          </div>
        </section>

        <!-- Strengths / Growth -->
        <section v-if="performance" class="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-12">
          <div class="space-y-6">
            <h4 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-1 bg-primary rounded-full"></span>Strengths</h4>
            <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
              <div v-for="s in performance.strengths" :key="s" class="flex items-center gap-4 p-4 bg-surface-container-lowest rounded-xl">
                <span class="material-symbols-outlined text-primary">check_circle</span>
                <span class="font-bold">{{ formatCategory(s) }}</span>
              </div>
              <p v-if="!performance.strengths.length" class="text-sm text-outline text-center py-4">No strengths identified yet</p>
            </div>
          </div>
          <div class="space-y-6">
            <h4 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-1 bg-tertiary rounded-full"></span>Growth Areas</h4>
            <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
              <div v-for="a in performance.growthAreas" :key="a" class="flex items-center gap-4 p-4 bg-surface-container-lowest rounded-xl">
                <span class="material-symbols-outlined text-tertiary">trending_up</span>
                <span class="font-bold">{{ formatCategory(a) }}</span>
              </div>
              <p v-if="!performance.growthAreas.length" class="text-sm text-outline text-center py-4">No growth areas identified yet</p>
            </div>
          </div>
        </section>

        <!-- Chart -->
        <section class="mb-12">
          <div class="bg-surface-container-low rounded-3xl p-8 border border-outline-variant/10">
            <div class="flex justify-between items-center mb-4">
              <div><h4 class="text-xl font-bold">Finding Trends</h4><p class="text-sm text-outline">Last 8 weeks</p></div>
              <div class="flex gap-4">
                <span class="flex items-center gap-2 text-xs font-bold"><span class="w-3 h-3 rounded-full bg-primary"></span>Critical ({{ totalCritical }})</span>
                <span class="flex items-center gap-2 text-xs font-bold"><span class="w-3 h-3 rounded-full" style="background:#F78166"></span>Minor ({{ totalMinor }})</span>
              </div>
            </div>
            <TrendChart title="" :points="criticalPoints" :secondary-points="minorPoints" :width="800" :height="300" />
          </div>
        </section>

        <!-- Recommendations -->
        <section v-if="recommendations.length" class="space-y-6 mb-12">
          <h4 class="text-2xl font-black tracking-tight">Recommended Learning</h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div v-for="rec in recommendations.slice(0, 3)" :key="rec.url" class="glass-panel p-6 rounded-2xl border border-outline-variant/10 hover:border-primary/30 transition-all">
              <span class="material-symbols-outlined text-primary mb-4 text-2xl">{{ getRecommendationIcon(rec.type) }}</span>
              <h5 class="font-bold text-lg mb-2">{{ rec.title }}</h5>
              <p class="text-sm text-outline mb-4">{{ rec.reason }}</p>
              <a :href="rec.url" target="_blank" class="text-primary font-bold text-sm">View Resource</a>
            </div>
          </div>
        </section>

        <!-- Skill Progress -->
        <section v-if="skillCategories.length" class="mb-12">
          <h4 class="text-2xl font-black tracking-tight mb-6">Skill Progress</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div v-for="cat in skillCategories" :key="cat.id" class="bg-surface-container-low p-6 rounded-xl">
              <div class="flex items-center gap-3 mb-4">
                <span class="material-symbols-outlined text-primary">{{ cat.icon }}</span>
                <h5 class="font-bold">{{ cat.displayName }}</h5>
              </div>
              <div class="space-y-3">
                <div v-for="skill in cat.skills" :key="skill.id"
                  class="space-y-1 cursor-pointer rounded-lg p-1 -m-1 hover:bg-surface-container-highest/50 transition-colors"
                  @click="openSkillBreakdown(skill.id)">
                  <div class="flex justify-between text-xs">
                    <span>{{ skill.displayName }}</span>
                    <span class="text-outline">{{ getSkillLevel(skill.score) }} · {{ skill.score }}%</span>
                  </div>
                  <div class="h-2 bg-surface-container-highest rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-500" :class="getSkillBarColor(skill.score)" :style="{ width: skill.score + '%' }"></div>
                  </div>
                </div>
              </div>
              <div class="mt-4 pt-4 border-t border-outline-variant/10 flex justify-between">
                <span class="text-sm font-bold">Average</span>
                <span class="text-sm font-bold text-primary">{{ categoryAverage(cat) }}%</span>
              </div>
            </div>
          </div>
        </section>

        <p v-if="loading" class="text-sm text-outline">Loading performance insights...</p>
      </template>
    </div>

    <SkillBreakdownDialog :open="breakdownOpen" :user-id="selectedUserId ?? 0" :skill-id="breakdownSkillId"
      :project-id="projectsStore.selectedProjectId ?? 0" @close="breakdownOpen = false" />
  </AppShell>
</template>
