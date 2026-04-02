<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import SkillRadarChart from '@/components/charts/SkillRadarChart.vue';
import ProgressChart from '@/components/charts/ProgressChart.vue';
import RecentFindings from '@/components/dashboard/RecentFindings.vue';
import SkillCard from '@/components/dashboard/SkillCard.vue';
import RecommendationsWidget from '@/components/skills/RecommendationsWidget.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

interface UserStat {
  id: number; username: string; email: string; display_name: string;
  total_evaluations: number; total_findings: number; avg_score: number;
  categories: { id: number; name: string }[];
}

const route = useRoute();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

// Admin user selection
const adminUsers = ref<UserStat[]>([]);
const adminLoading = ref(false);
const adminSearch = ref('');
const adminCategories = ref<{ id: number; name: string }[]>([]);
const adminCategoryFilter = ref<number | null>(null);
const adminProjectFilter = ref<number | null>(null);
const selectedUserId = ref<number | null>(null);

// Dashboard data
const loading = ref(false);
const overview = ref<any>(null);
const categoryScores = ref<any[]>([]);
const progressData = ref<any[]>([]);
const recentFindings = ref<any[]>([]);
const skillCategories = ref<any[]>([]);

// Pattern tracker
const patterns = ref<any[]>([]);
const patternsLoading = ref(false);
const showResolved = ref(false);
const resolvingId = ref<number | null>(null);

const showUserList = computed(() => authStore.isAdmin && !selectedUserId.value);

onMounted(async () => {
  await projectsStore.fetchProjects();
  
  // Check for ?user= query param
  const queryUser = route.query.user;
  if (queryUser) {
    selectedUserId.value = Number(queryUser);
  }

  // Always seed our own userId so we see our own data by default
  if (!selectedUserId.value) {
    selectedUserId.value = authStore.user?.id ?? null;
  }

  if (authStore.isAdmin) {
    await loadAdminUsers();
  }

  if (selectedUserId.value) await loadDashboardData();
});

watch(() => projectsStore.selectedProjectId, async () => {
  if (selectedUserId.value) await loadDashboardData();
});

watch([adminSearch, adminCategoryFilter, adminProjectFilter], () => loadAdminUsers());

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
  loadDashboardData();
}

function backToList() {
  selectedUserId.value = null;
  overview.value = null;
  skillCategories.value = [];
}

async function loadDashboardData() {
  if (!selectedUserId.value) return;
  loading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId ?? undefined;
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

    const catRes = await api.skills.user(
      selectedUserId.value,
      projectId != null ? projectId : undefined,
    );
    skillCategories.value = catRes.data.categories || [];
  } catch (e) { console.error(e); } finally { loading.value = false; }

  // Load patterns in parallel (non-blocking)
  loadPatterns();
}

async function loadPatterns() {
  patternsLoading.value = true;
  try {
    const projectId = projectsStore.selectedProjectId ?? undefined;
    const { data } = await api.evaluations.patterns(projectId);
    patterns.value = Array.isArray(data) ? data : (data.results || []);
  } catch { /* ignore */ } finally { patternsLoading.value = false; }
}

async function resolvePattern(id: number) {
  resolvingId.value = id;
  try {
    await api.evaluations.resolvePattern(id);
    patterns.value = patterns.value.map(p => p.id === id ? { ...p, is_resolved: true } : p);
  } catch { /* ignore */ } finally { resolvingId.value = null; }
}

const filteredPatterns = computed(() =>
  showResolved.value ? patterns.value : patterns.value.filter(p => !p.is_resolved)
);

const statCards = computed(() => {
  if (!overview.value) return [];
  return [
    { label: 'Total Evaluations', value: overview.value.total_evaluations, icon: 'analytics', color: 'primary' },
    { label: 'Total Findings', value: overview.value.total_findings, icon: 'bug_report', color: 'tertiary', sub: `${overview.value.critical_count} critical, ${overview.value.warning_count} warning` },
    { label: 'Fix Rate', value: `${overview.value.fix_rate}%`, icon: 'check_circle', color: 'primary-container' },
    { label: 'Average Score', value: `${overview.value.avg_score}%`, icon: 'school', color: 'secondary' },
  ];
});

const selectedUserObj = computed(() => adminUsers.value.find(u => u.id === selectedUserId.value));
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Header -->
      <section class="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div class="space-y-2">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Skills & Metrics</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">
            {{ showUserList ? 'Team Skills' : 'Developer Dashboard' }}
          </h1>
          <p class="text-outline text-sm">
            {{ showUserList ? 'Select a developer to view their skill metrics' : 'Track coding skills and progress over time' }}
          </p>
        </div>

        <div class="flex items-center gap-3">
          <button v-if="authStore.isAdmin && selectedUserId" @click="backToList"
            class="flex items-center gap-2 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20 text-sm text-on-surface hover:text-primary transition-colors">
            <span class="material-symbols-outlined text-sm">arrow_back</span> All Users
          </button>
          <div v-if="selectedUserId && selectedUserObj" class="flex items-center gap-2 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
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
        </div>
      </section>

      <!-- ═══ Admin User List ═══ -->
      <template v-if="showUserList">
        <div class="flex flex-wrap items-center gap-3 mb-8">
          <input v-model="adminSearch" type="text" placeholder="Search..."
            class="w-56 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm" />
          <select v-model="adminCategoryFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm text-on-surface focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">All Categories</option>
            <option v-for="c in adminCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="adminProjectFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm text-on-surface focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
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
                <p class="text-base font-black">{{ u.total_evaluations }}</p>
                <p class="text-[8px] text-outline uppercase">Evaluations</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black">{{ u.total_findings }}</p>
                <p class="text-[8px] text-outline uppercase">Findings</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black" :class="u.avg_score >= 70 ? 'text-green-400' : u.avg_score >= 50 ? 'text-yellow-400' : 'text-error'">{{ u.avg_score }}%</p>
                <p class="text-[8px] text-outline uppercase">Score</p>
              </div>
            </div>
          </div>
          <div v-if="!adminUsers.length" class="col-span-full text-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">group</span>
            <p class="text-outline">No developers found</p>
          </div>
        </div>
      </template>

      <!-- ═══ User Dashboard (existing) ═══ -->
      <template v-else>
        <div v-if="loading" class="flex items-center justify-center py-16">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>

        <template v-else>
          <section v-if="overview" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            <div v-for="stat in statCards" :key="stat.label"
              class="bg-surface-container-low p-6 rounded-xl border-l-4" :class="`border-${stat.color}`">
              <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">{{ stat.label }}</p>
              <h3 class="text-3xl font-black">{{ stat.value }}</h3>
              <p v-if="stat.sub" class="text-xs text-outline mt-2">{{ stat.sub }}</p>
            </div>
          </section>

          <section class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
            <SkillRadarChart :data="categoryScores" title="Skill Categories Overview" />
            <ProgressChart :data="progressData" title="Weekly Progress (Last 8 Weeks)" />
          </section>

          <section class="mb-12">
            <RecommendationsWidget
              :project-id="projectsStore.selectedProjectId != null ? String(projectsStore.selectedProjectId) : undefined"
            />
          </section>

          <section class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
            <div class="lg:col-span-2"><RecentFindings :findings="recentFindings" /></div>
            <div class="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10">
              <h4 class="text-xl font-bold mb-6">Quick Stats</h4>
              <div class="space-y-4">
                <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                  <div class="flex items-center gap-3"><span class="material-symbols-outlined text-error">error</span><span class="text-sm">Critical</span></div>
                  <span class="text-xl font-black">{{ overview?.critical_count || 0 }}</span>
                </div>
                <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                  <div class="flex items-center gap-3"><span class="material-symbols-outlined text-yellow-500">warning</span><span class="text-sm">Warnings</span></div>
                  <span class="text-xl font-black">{{ overview?.warning_count || 0 }}</span>
                </div>
                <div class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
                  <div class="flex items-center gap-3"><span class="material-symbols-outlined text-primary">check_circle</span><span class="text-sm">Fixed</span></div>
                  <span class="text-xl font-black">{{ overview?.fixed_count || 0 }}</span>
                </div>
              </div>
            </div>
          </section>

          <section v-if="skillCategories.length" class="mb-12">
            <h4 class="text-2xl font-black tracking-tight mb-6">Skill Breakdown by Category</h4>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <SkillCard v-for="cat in skillCategories" :key="cat.id" :category="cat" />
            </div>
          </section>

          <!-- ─── Pattern Tracker ─── -->
          <section class="mb-12">
            <div class="flex items-center justify-between mb-5">
              <div>
                <h4 class="text-2xl font-black tracking-tight">Pattern Tracker</h4>
                <p class="text-sm text-outline mt-0.5">Recurring code issues detected across your evaluations</p>
              </div>
              <label class="flex items-center gap-2 text-sm text-outline cursor-pointer">
                <input type="checkbox" v-model="showResolved" class="accent-primary rounded" />
                Show resolved
              </label>
            </div>

            <div v-if="patternsLoading" class="flex items-center gap-3 py-8 text-outline">
              <span class="material-symbols-outlined animate-spin text-2xl">progress_activity</span>
              Loading patterns…
            </div>

            <div v-else-if="!filteredPatterns.length" class="p-8 bg-surface-container-low rounded-2xl border border-outline-variant/10 text-center">
              <span class="material-symbols-outlined text-4xl text-outline mb-2 block">verified</span>
              <p class="text-sm text-outline">{{ showResolved ? 'No patterns found.' : 'No recurring issues detected.' }}</p>
            </div>

            <div v-else class="bg-surface-container-low rounded-2xl border border-outline-variant/10 overflow-hidden">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-outline-variant/10 text-xs text-outline uppercase tracking-wider">
                    <th class="px-5 py-3 text-left">Pattern</th>
                    <th class="px-5 py-3 text-center">Frequency</th>
                    <th class="px-5 py-3 text-left hidden md:table-cell">First seen</th>
                    <th class="px-5 py-3 text-left hidden md:table-cell">Last seen</th>
                    <th class="px-5 py-3 text-center">Status</th>
                    <th class="px-3 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="p in filteredPatterns"
                    :key="p.id"
                    class="border-b border-outline-variant/5 hover:bg-surface-container-lowest/40 transition-colors"
                    :class="p.is_resolved ? 'opacity-50' : ''"
                  >
                    <td class="px-5 py-3">
                      <div class="flex items-center gap-3">
                        <span class="material-symbols-outlined text-error text-base">repeat</span>
                        <div>
                          <p class="font-semibold text-on-surface capitalize">
                            {{ p.pattern_key.split(':')[0].replace(/_/g, ' ') }}
                          </p>
                          <p class="text-xs text-outline capitalize">{{ p.pattern_type }}</p>
                        </div>
                      </div>
                    </td>
                    <td class="px-5 py-3 text-center">
                      <span class="px-2.5 py-1 rounded-full text-xs font-bold"
                        :class="p.frequency >= 5 ? 'bg-error/15 text-error' : p.frequency >= 3 ? 'bg-yellow-500/15 text-yellow-500' : 'bg-outline/10 text-outline'">
                        ×{{ p.frequency }}
                      </span>
                    </td>
                    <td class="px-5 py-3 text-outline text-xs hidden md:table-cell">
                      {{ new Date(p.first_seen).toLocaleDateString() }}
                    </td>
                    <td class="px-5 py-3 text-outline text-xs hidden md:table-cell">
                      {{ new Date(p.last_seen).toLocaleDateString() }}
                    </td>
                    <td class="px-5 py-3 text-center">
                      <span v-if="p.is_resolved" class="px-2 py-0.5 rounded-full text-xs bg-emerald-500/15 text-emerald-500 font-semibold">Resolved</span>
                      <span v-else class="px-2 py-0.5 rounded-full text-xs bg-error/10 text-error font-semibold">Active</span>
                    </td>
                    <td class="px-3 py-3 text-right">
                      <button
                        v-if="!p.is_resolved"
                        type="button"
                        :disabled="resolvingId === p.id"
                        class="px-3 py-1.5 rounded-lg border border-outline-variant/20 text-xs hover:border-primary/40 hover:text-primary transition-colors disabled:opacity-50"
                        @click="resolvePattern(p.id)"
                      >
                        <span v-if="resolvingId === p.id" class="material-symbols-outlined text-xs animate-spin">progress_activity</span>
                        <span v-else>Mark resolved</span>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section v-if="!overview && !loading" class="text-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">insights</span>
            <h3 class="text-xl font-bold mb-2">No Dashboard Data Yet</h3>
            <p class="text-outline">Start pushing code to see skill metrics and progress!</p>
          </section>
        </template>
      </template>
    </div>
  </AppShell>
</template>
