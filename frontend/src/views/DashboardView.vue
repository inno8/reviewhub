<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import SkillRadarChart from '@/components/charts/SkillRadarChart.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
import SkillBreakdownDialog from '@/components/skills/SkillBreakdownDialog.vue';
import { useFindingsStore } from '@/stores/findings';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const router = useRouter();
const route = useRoute();

const findingsStore = useFindingsStore();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

// ─── Admin state ──────────────────────────────────────────────────────────
interface UserStat {
  id: number;
  username: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  role: string;
  categories: { id: number; name: string }[];
  total_evaluations: number;
  total_findings: number;
  avg_score: number;
  total_commits: number;
  fixed_findings: number;
  fix_rate: number;
}

const adminUsers = ref<UserStat[]>([]);
const adminLoading = ref(false);
const adminSearch = ref('');
const adminCategoryFilter = ref<number | null>(null);
const adminProjectFilter = ref<number | null>(null);
const adminCategories = ref<{ id: number; name: string }[]>([]);
const adminProjects = ref<{ id: number; displayName: string }[]>([]);
const drawerUser = ref<UserStat | null>(null);

async function loadAdminData() {
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
    adminProjects.value = projectsStore.projects.map(p => ({ id: p.id, displayName: p.displayName }));
  } catch (e) {
    console.error('Admin data load failed:', e);
  } finally {
    adminLoading.value = false;
  }
}

watch([adminSearch, adminCategoryFilter, adminProjectFilter], () => {
  loadAdminData();
});

function openDrawer(user: UserStat) { drawerUser.value = user; }
function closeDrawer() { drawerUser.value = null; }
function goToUserSkills(userId: number) { router.push({ path: '/skills', query: { user: String(userId) } }); }
function goToUserInsights(userId: number) { router.push({ path: '/insights', query: { user: String(userId) } }); }

// ─── Developer state ─────────────────────────────────────────────────────
const devSelectedProject = ref<number | null>(null);
const selectedCategory = ref('all');
const selectedDifficulty = ref('all');
const selectedAuthor = ref('all');
const selectedDate = ref<string | null>(null);
const categories = ['SECURITY', 'PERFORMANCE', 'CODE_STYLE', 'TESTING', 'ARCHITECTURE'];
const difficulties = ['BEGINNER', 'INTERMEDIATE', 'ADVANCED'];

// Developer home data (unified endpoint)
const devHome = ref<any>(null);
const devHomeLoading = ref(false);
const devProjectFilter = ref<number | null>(null);

// Skill breakdown dialog
const breakdownOpen = ref(false);
const breakdownSkillId = ref<number | null>(null);
function openSkillBreakdown(id: number) {
  breakdownSkillId.value = id;
  breakdownOpen.value = true;
}

async function loadDevHome(projectId?: number) {
  if (authStore.isAdmin) return;
  devHomeLoading.value = true;
  try {
    const params: any = {};
    if (projectId) params.project = projectId;
    const axios = (await import('axios')).default;
    const token = localStorage.getItem('reviewhub_token');
    const { data } = await axios.get(
      `${import.meta.env.VITE_API_URL}/skills/dashboard/developer-home/`,
      { params, headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );
    devHome.value = data;
  } catch { devHome.value = null; }
  finally { devHomeLoading.value = false; }
}

function setProjectFilter(projectId: number | null) {
  devProjectFilter.value = projectId;
  loadDevHome(projectId ?? undefined);
}

function getLevelColor(level: string) {
  const m: Record<string, string> = { beginner: 'text-red-400', junior: 'text-orange-400', intermediate: 'text-yellow-400', senior: 'text-green-400', expert: 'text-primary' };
  return m[level] || 'text-outline';
}
function getLevelBg(level: string) {
  const m: Record<string, string> = { beginner: 'bg-red-500/15', junior: 'bg-orange-500/15', intermediate: 'bg-yellow-500/15', senior: 'bg-green-500/15', expert: 'bg-primary/15' };
  return m[level] || 'bg-surface-container';
}

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (authStore.isAdmin) {
    await loadAdminData();
  } else {
    await loadDevHome();
  }
  applyIssuesProjectFromRoute();
});

watch(
  () => route.query.project,
  () => {
    applyIssuesProjectFromRoute();
  },
);

function selectDevProject(projectId: number) {
  devSelectedProject.value = projectId;
  projectsStore.setSelectedProject(projectId);
  findingsStore.fetchFindings({ projectId });
  loadDevOverview(projectId);
}

function applyIssuesProjectFromRoute() {
  if (authStore.isAdmin) return;
  const raw = route.query.project;
  if (raw === undefined || raw === null || raw === '') return;
  const s = Array.isArray(raw) ? raw[0] : raw;
  const n = Number(s);
  if (!Number.isFinite(n)) return;
  selectDevProject(n);
}

function backToProjects() {
  devSelectedProject.value = null;
  router.push('/projects');
}

watch(() => projectsStore.selectedProjectId, async (newId) => {
  if (newId && !authStore.isAdmin && devSelectedProject.value) {
    await findingsStore.fetchFindings({ projectId: newId });
  }
});

function clearDateFilter() {
  selectedDate.value = null;
  if (projectsStore.selectedProjectId) findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
}

const authors = computed(() => {
  const s = new Set<string>();
  findingsStore.findings.forEach(f => { if (f.commitAuthor) s.add(f.commitAuthor); });
  return Array.from(s);
});

const filteredFindings = computed(() =>
  findingsStore.findings.filter(f => {
    if (selectedCategory.value !== 'all' && f.category !== selectedCategory.value) return false;
    if (selectedDifficulty.value !== 'all' && f.difficulty !== selectedDifficulty.value) return false;
    if (selectedAuthor.value !== 'all' && f.commitAuthor !== selectedAuthor.value) return false;
    return true;
  })
);

const groupedByFile = computed(() => {
  const g: Record<string, typeof filteredFindings.value> = {};
  filteredFindings.value.forEach(f => { if (!g[f.filePath]) g[f.filePath] = []; g[f.filePath].push(f); });
  return g;
});

const fileGroups = computed(() =>
  Object.entries(groupedByFile.value).map(([filePath, findings]) => ({
    filePath, findings,
    branch: findings[0]?.review?.branch || 'main',
    categories: [...new Set(findings.map(f => f.category))],
    authors: [...new Set(findings.map(f => f.commitAuthor).filter(Boolean))],
  }))
);

const currentDate = computed(() => new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }));

function getCategoryClass(cat: string) {
  const c = cat.toLowerCase().replace('_', '');
  return { security: 'bg-error/10 text-error border-error/20', performance: 'bg-tertiary/10 text-tertiary border-tertiary/20', codestyle: 'bg-primary/10 text-primary border-primary/20', testing: 'bg-primary-container/10 text-primary-container border-primary-container/20', architecture: 'bg-secondary/10 text-secondary border-secondary/20' }[c] || 'bg-outline/10 text-outline border-outline/20';
}
function openFile(filePath: string) { router.push({ path: '/file-review', query: { file: filePath, ids: groupedByFile.value[filePath].map(f => f.id).join(',') } }); }
function formatCategory(cat: string) { return cat.replace('_', ' '); }

function scoreColor(score: number) {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-yellow-400';
  return 'text-error';
}
</script>

<template>
  <AppShell>
    <!-- ═══ ADMIN DASHBOARD ═══ -->
    <template v-if="authStore.isAdmin">
      <div class="p-8 flex-1">
        <header class="mb-10">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Admin Dashboard</span>
          <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">Team Overview</h1>
          <p class="text-outline text-sm">Monitor your team's progress and performance.</p>
        </header>

        <!-- Filters -->
        <div class="flex flex-wrap items-center gap-3 mb-8">
          <input v-model="adminSearch" type="text" placeholder="Search..."
            class="w-56 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm" />
          <select v-model="adminCategoryFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">All Categories</option>
            <option v-for="cat in adminCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
          <select v-model="adminProjectFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">All Projects</option>
            <option v-for="p in adminProjects" :key="p.id" :value="p.id">{{ p.displayName }}</option>
          </select>
          <span class="ml-auto text-xs text-outline">{{ adminUsers.length }} users</span>
        </div>

        <!-- User Grid -->
        <div v-if="adminLoading" class="flex items-center justify-center py-16">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div
            v-for="u in adminUsers" :key="u.id"
            class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all cursor-pointer group"
            @click="openDrawer(u)">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-11 h-11 rounded-lg bg-secondary-container flex items-center justify-center text-sm font-bold text-primary">
                {{ u.username.slice(0, 2).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <div class="text-sm font-bold text-on-surface truncate">{{ u.display_name || u.username }}</div>
                <div class="text-[11px] text-outline truncate">{{ u.email }}</div>
              </div>
            </div>
            <div class="flex gap-1.5 flex-wrap mb-3">
              <span v-for="cat in u.categories" :key="cat.id" class="text-[10px] bg-surface-container-highest px-1.5 py-0.5 rounded text-on-surface-variant">{{ cat.name }}</span>
            </div>
            <div class="grid grid-cols-3 gap-2 text-center">
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-lg font-black text-on-surface">{{ u.total_evaluations }}</p>
                <p class="text-[9px] text-outline uppercase tracking-wider">Evals</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-lg font-black text-on-surface">{{ u.total_findings }}</p>
                <p class="text-[9px] text-outline uppercase tracking-wider">Findings</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-lg font-black" :class="scoreColor(u.avg_score)">{{ u.avg_score }}%</p>
                <p class="text-[9px] text-outline uppercase tracking-wider">Score</p>
              </div>
            </div>
          </div>
          <div v-if="!adminUsers.length" class="col-span-full flex flex-col items-center justify-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">group</span>
            <p class="text-on-surface-variant text-lg">No users found</p>
          </div>
        </div>
      </div>

      <!-- User Drawer (RIGHT side) -->
      <Transition name="slide-right">
        <div v-if="drawerUser" class="fixed inset-y-0 right-0 z-[90] flex" @click.self="closeDrawer">
          <div class="flex-1" @click="closeDrawer"></div>
          <div class="w-96 bg-surface-container-low border-l border-outline-variant/20 shadow-2xl overflow-y-auto mt-16">
            <div class="p-6 relative">
              <button @click="closeDrawer" class="absolute top-4 right-4 text-outline hover:text-on-surface">
                <span class="material-symbols-outlined">close</span>
              </button>
              <div class="flex items-center gap-4 mb-6">
                <div class="w-14 h-14 rounded-xl bg-secondary-container flex items-center justify-center text-lg font-bold text-primary">
                  {{ drawerUser.username.slice(0, 2).toUpperCase() }}
                </div>
                <div>
                  <h3 class="text-xl font-bold text-on-surface">{{ drawerUser.display_name || drawerUser.username }}</h3>
                  <p class="text-xs text-outline">{{ drawerUser.email }}</p>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-3 mb-6">
                <div class="bg-surface-container-lowest rounded-lg p-3">
                  <p class="text-2xl font-black text-on-surface">{{ drawerUser.total_evaluations }}</p>
                  <p class="text-[10px] text-outline uppercase">Evaluations</p>
                </div>
                <div class="bg-surface-container-lowest rounded-lg p-3">
                  <p class="text-2xl font-black text-on-surface">{{ drawerUser.total_findings }}</p>
                  <p class="text-[10px] text-outline uppercase">Findings</p>
                </div>
                <div class="bg-surface-container-lowest rounded-lg p-3">
                  <p class="text-2xl font-black" :class="scoreColor(drawerUser.avg_score)">{{ drawerUser.avg_score }}%</p>
                  <p class="text-[10px] text-outline uppercase">Avg Score</p>
                </div>
                <div class="bg-surface-container-lowest rounded-lg p-3">
                  <p class="text-2xl font-black text-on-surface">{{ drawerUser.fix_rate }}%</p>
                  <p class="text-[10px] text-outline uppercase">Fix Rate</p>
                </div>
              </div>
              <div v-if="drawerUser.categories.length" class="mb-6">
                <p class="text-xs font-bold uppercase tracking-widest text-outline mb-2">Categories</p>
                <div class="flex gap-1.5 flex-wrap">
                  <span v-for="c in drawerUser.categories" :key="c.id" class="text-xs bg-surface-container-highest px-2 py-0.5 rounded">{{ c.name }}</span>
                </div>
              </div>
              <div class="space-y-2">
                <button @click="goToUserSkills(drawerUser.id)"
                  class="w-full flex items-center gap-3 p-3 bg-surface-container-lowest rounded-lg hover:bg-primary/10 transition-colors text-left">
                  <span class="material-symbols-outlined text-primary">school</span>
                  <div><p class="text-sm font-bold text-on-surface">Skills Dashboard</p><p class="text-[10px] text-outline">View skill breakdown and metrics</p></div>
                  <span class="material-symbols-outlined text-outline ml-auto text-sm">arrow_forward</span>
                </button>
                <button @click="goToUserInsights(drawerUser.id)"
                  class="w-full flex items-center gap-3 p-3 bg-surface-container-lowest rounded-lg hover:bg-primary/10 transition-colors text-left">
                  <span class="material-symbols-outlined text-tertiary">analytics</span>
                  <div><p class="text-sm font-bold text-on-surface">Performance Insights</p><p class="text-[10px] text-outline">Trends, strengths, and recommendations</p></div>
                  <span class="material-symbols-outlined text-outline ml-auto text-sm">arrow_forward</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </template>

    <!-- ═══ DEV DASHBOARD ═══ -->
    <template v-else>
      <div class="p-8 flex-1">

        <!-- Loading -->
        <div v-if="devHomeLoading && !devHome" class="flex items-center justify-center py-20">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>

        <template v-else-if="devHome">

          <!-- ── Top Metrics Row ── -->
          <section class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
              <p class="text-4xl font-black" :class="devHome.avgScore >= 70 ? 'text-green-400' : devHome.avgScore >= 50 ? 'text-yellow-400' : 'text-red-400'">
                {{ devHome.avgScore }}%
              </p>
              <p class="text-[10px] text-outline uppercase tracking-wider mt-1">Avg Score</p>
            </div>
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
              <div class="inline-flex items-center justify-center w-12 h-12 rounded-full mb-1" :class="getLevelBg(devHome.level)">
                <span class="text-sm font-black uppercase" :class="getLevelColor(devHome.level)">{{ (devHome.level || '?')[0] }}</span>
              </div>
              <p class="text-sm font-bold capitalize" :class="getLevelColor(devHome.level)">{{ devHome.level }}</p>
            </div>
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
              <p class="text-2xl font-black" :class="devHome.improving ? 'text-green-400' : 'text-orange-400'">
                {{ devHome.improving ? '+' : '' }}{{ devHome.improvementPct }}%
              </p>
              <p class="text-[10px] text-outline uppercase tracking-wider mt-1">{{ devHome.improving ? 'Improving' : 'Trend' }}</p>
            </div>
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
              <p class="text-2xl font-black text-tertiary">{{ devHome.findingCount }}</p>
              <p class="text-[10px] text-outline uppercase tracking-wider mt-1">Findings</p>
            </div>
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
              <p class="text-2xl font-black text-primary">{{ devHome.commitCount }}</p>
              <p class="text-[10px] text-outline uppercase tracking-wider mt-1">Commits</p>
            </div>
          </section>

          <!-- ── Two Column Layout ── -->
          <section class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">

            <!-- LEFT: Action Column (2/3 width) -->
            <div class="lg:col-span-2 space-y-6">

              <!-- Focus This Week -->
              <div v-if="devHome.priorities?.length" class="p-5 rounded-xl bg-primary/5 border border-primary/20">
                <div class="flex items-center gap-2 mb-3">
                  <span class="material-symbols-outlined text-primary">target</span>
                  <h3 class="text-sm font-bold text-primary uppercase tracking-wider">Focus this week</h3>
                </div>
                <div class="flex flex-wrap gap-3">
                  <div v-for="p in devHome.priorities" :key="p.slug"
                    class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container border border-outline-variant/20 cursor-pointer hover:border-primary/40 transition-colors"
                    @click="p.id && openSkillBreakdown(p.id)">
                    <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-black"
                      :class="p.score < 40 ? 'bg-red-500/20 text-red-400' : p.score < 70 ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'">
                      {{ Math.round(p.score) }}
                    </div>
                    <div>
                      <p class="text-sm font-bold">{{ p.skill }}</p>
                      <p class="text-[10px] text-outline">{{ p.issues }} issues</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Pattern Alerts -->
              <div v-if="devHome.patterns?.length" class="space-y-2">
                <div v-for="pat in devHome.patterns" :key="pat.key"
                  class="flex items-center gap-3 p-3 rounded-lg bg-tertiary/5 border border-tertiary/20">
                  <span class="material-symbols-outlined text-tertiary">repeat</span>
                  <p class="text-sm flex-1">
                    <span class="font-bold text-tertiary">{{ pat.type.replace('_', ' ') }}:</span>
                    {{ pat.message }}.
                  </p>
                  <router-link to="/skills" class="text-xs text-primary font-semibold whitespace-nowrap">Fix it</router-link>
                </div>
              </div>

              <!-- Recent Commits -->
              <div class="bg-surface-container-low rounded-xl border border-outline-variant/10">
                <div class="flex items-center justify-between p-4 border-b border-outline-variant/10">
                  <h3 class="text-sm font-bold">Recent Activity</h3>
                  <router-link to="/timeline" class="text-xs text-primary font-semibold">View all</router-link>
                </div>
                <div class="divide-y divide-outline-variant/10">
                  <div v-for="c in devHome.recentCommits" :key="c.id"
                    class="flex items-center gap-3 p-3 hover:bg-surface-container-lowest transition-colors cursor-pointer"
                    @click="router.push({ name: 'file-review', query: { evaluationId: c.id } })">
                    <div class="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold"
                      :class="{
                        'bg-red-500/20 text-red-400': (c.score || 0) < 40,
                        'bg-orange-500/20 text-orange-400': (c.score || 0) >= 40 && (c.score || 0) < 60,
                        'bg-yellow-500/20 text-yellow-400': (c.score || 0) >= 60 && (c.score || 0) < 75,
                        'bg-green-500/20 text-green-400': (c.score || 0) >= 75,
                      }">{{ c.score != null ? Math.round(c.score) : '?' }}</div>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-medium truncate">{{ c.message }}</p>
                      <p class="text-[10px] text-outline">{{ c.sha }} · {{ c.project }} · {{ c.findings }} findings</p>
                    </div>
                    <span class="material-symbols-outlined text-sm text-outline">chevron_right</span>
                  </div>
                  <div v-if="!devHome.recentCommits?.length" class="p-8 text-center text-outline text-sm">
                    No commits analyzed yet. Link a repo to get started.
                  </div>
                </div>
              </div>

              <!-- Top Issue Areas -->
              <div v-if="devHome.topIssues?.length" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
                <h3 class="text-sm font-bold mb-4">Where you lose the most points</h3>
                <div class="space-y-2">
                  <div v-for="issue in devHome.topIssues" :key="issue.id"
                    class="flex items-center gap-3 cursor-pointer hover:bg-surface-container-lowest rounded-lg p-1 -m-1 transition-colors"
                    @click="issue.id && openSkillBreakdown(issue.id)">
                    <span class="text-xs font-medium w-28 truncate">{{ issue.name }}</span>
                    <div class="flex-1 bg-surface-container-lowest rounded-full h-3 overflow-hidden">
                      <div class="h-full bg-tertiary rounded-full" :style="{ width: (issue.count / devHome.topIssues[0].count * 100) + '%' }"></div>
                    </div>
                    <span class="text-xs font-bold w-6 text-right">{{ issue.count }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- RIGHT: Visual Column (1/3 width) -->
            <div class="space-y-6">

              <!-- Skill Radar -->
              <div v-if="devHome.radar?.length" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
                <h3 class="text-sm font-bold mb-3">Skill Overview</h3>
                <SkillRadarChart :data="devHome.radar" />
              </div>

              <!-- Score Sparkline -->
              <div v-if="devHome.sparkline?.length >= 2" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
                <h3 class="text-sm font-bold mb-1">Score Progression</h3>
                <p class="text-[10px] text-outline mb-3">Last {{ devHome.sparkline.length }} commits</p>
                <TrendChart title=""
                  :points="devHome.sparkline.map((s: number, i: number) => ({ label: String(i + 1), value: s }))"
                  :width="300" :height="120" />
              </div>

              <!-- Severity Breakdown -->
              <div v-if="devHome.severity" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
                <h3 class="text-sm font-bold mb-3">Finding Severity</h3>
                <div class="space-y-2">
                  <div v-for="(count, sev) in devHome.severity" :key="sev" class="flex items-center gap-2">
                    <span class="text-[10px] font-bold uppercase w-16"
                      :class="{ 'text-red-400': sev === 'critical', 'text-orange-400': sev === 'warning', 'text-blue-400': sev === 'info', 'text-green-400': sev === 'suggestion' }">
                      {{ sev }}
                    </span>
                    <div class="flex-1 bg-surface-container-lowest rounded-full h-2.5 overflow-hidden">
                      <div class="h-full rounded-full"
                        :class="{ 'bg-red-500': sev === 'critical', 'bg-orange-500': sev === 'warning', 'bg-blue-500': sev === 'info', 'bg-green-500': sev === 'suggestion' }"
                        :style="{ width: devHome.findingCount ? (count / devHome.findingCount * 100) + '%' : '0%' }">
                      </div>
                    </div>
                    <span class="text-xs font-bold w-5 text-right">{{ count }}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- ── Project Filter Row ── -->
          <section class="flex flex-wrap items-center gap-2">
            <span class="text-xs text-outline font-bold uppercase tracking-wider mr-2">Projects:</span>
            <button
              :class="['px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                !devProjectFilter ? 'bg-primary text-white' : 'bg-surface-container text-outline hover:text-on-surface']"
              @click="setProjectFilter(null)">All</button>
            <button v-for="p in projectsStore.projects" :key="p.id"
              :class="['px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                devProjectFilter === p.id ? 'bg-primary text-white' : 'bg-surface-container text-outline hover:text-on-surface']"
              @click="setProjectFilter(p.id)">{{ p.displayName }}</button>
          </section>

        </template>

        <!-- Empty state -->
        <div v-else class="flex flex-col items-center justify-center py-20">
          <span class="material-symbols-outlined text-6xl text-outline mb-4">analytics</span>
          <p class="text-on-surface-variant text-lg">No data yet</p>
          <p class="text-outline text-sm">Link a repository and push some code to get started.</p>
        </div>

        <!-- Findings view (when navigated from Projects page with ?project=) -->
        <template v-if="devSelectedProject">
          <header class="mb-10">
            <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">{{ currentDate }}</h1>
            <p class="text-outline text-sm">
              <span class="text-primary font-semibold">{{ filteredFindings.length }} findings</span> across {{ fileGroups.length }} files
            </p>
          </header>

          <!-- Focus Priorities -->
          <div v-if="devHome?.priorities?.length" class="mb-6 p-5 rounded-xl bg-primary/5 border border-primary/20">
            <div class="flex items-center gap-2 mb-3">
              <span class="material-symbols-outlined text-primary">target</span>
              <h3 class="text-sm font-bold text-primary uppercase tracking-wider">This week, focus on:</h3>
            </div>
            <div class="flex flex-wrap gap-3">
              <div v-for="p in devHome.priorities" :key="p.skill_slug"
                class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-container border border-outline-variant/20">
                <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-black"
                  :class="p.score < 40 ? 'bg-red-500/20 text-red-400' : p.score < 60 ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'">
                  {{ Math.round(p.score) }}
                </div>
                <div>
                  <p class="text-sm font-bold">{{ p.skill }}</p>
                  <p class="text-[10px] text-outline">{{ p.issues }} issues · {{ p.trend || 'stable' }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Pattern Alerts -->
          <div v-if="devHome?.pattern_insights?.length" class="mb-6 space-y-2">
            <div v-for="pat in devHome.pattern_insights.slice(0, 3)" :key="pat.key"
              class="flex items-center gap-3 p-3 rounded-lg bg-tertiary/5 border border-tertiary/20">
              <span class="material-symbols-outlined text-tertiary">repeat</span>
              <p class="text-sm">
                <span class="font-bold text-tertiary">{{ pat.type }}:</span>
                {{ pat.message }}.
                <router-link to="/skills" class="text-primary font-semibold ml-1">View recommendations →</router-link>
              </p>
            </div>
          </div>

          <!-- Filter Bar -->
          <div class="flex flex-wrap items-center gap-4 mb-8 bg-surface-container-low p-3 rounded-xl border border-outline-variant/10">
            <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
              <select v-model="selectedCategory" class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer">
                <option value="all">Category: All</option>
                <option v-for="c in categories" :key="c" :value="c">{{ formatCategory(c) }}</option>
              </select>
            </div>
            <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
              <select v-model="selectedDifficulty" class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer">
                <option value="all">Difficulty: All</option>
                <option v-for="d in difficulties" :key="d" :value="d">{{ d.charAt(0) + d.slice(1).toLowerCase() }}</option>
              </select>
            </div>
            <div v-if="selectedDate" class="flex items-center gap-2 px-3 py-1.5 bg-primary/10 rounded-lg border border-primary/20">
              <span class="text-xs text-primary font-medium">{{ selectedDate }}</span>
              <button @click="clearDateFilter" class="text-primary hover:text-error"><span class="material-symbols-outlined text-sm">close</span></button>
            </div>
            <span class="ml-auto text-[10px] text-outline uppercase font-bold">{{ filteredFindings.length }} findings</span>
          </div>

          <!-- File Cards -->
          <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            <div v-for="group in fileGroups" :key="group.filePath"
              class="bg-surface-container-low p-6 rounded-xl border border-outline-variant/5 hover:border-primary/20 transition-all cursor-pointer group relative"
              @click="openFile(group.filePath)">
              <div class="flex justify-between items-start mb-4">
                <span class="text-outline text-xs font-mono flex items-center gap-2">
                  <span class="material-symbols-outlined text-sm">description</span>{{ group.filePath.split('/').pop() }}
                </span>
                <span class="bg-surface-container-highest text-outline text-[10px] px-2 py-0.5 rounded">{{ group.branch.split('/').pop() }}</span>
              </div>
              <p class="text-on-surface-variant text-xs font-mono mb-4 truncate">{{ group.filePath }}</p>
              <div class="flex flex-wrap gap-2 mb-4">
                <span v-for="cat in group.categories" :key="cat" :class="['px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border', getCategoryClass(cat)]">{{ formatCategory(cat) }}</span>
              </div>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-2xl font-black text-primary">{{ group.findings.length }}</span>
                  <span class="text-xs text-outline">{{ group.findings.length === 1 ? 'finding' : 'findings' }}</span>
                </div>
              </div>
            </div>
            <div v-if="!fileGroups.length && !findingsStore.loading" class="col-span-full flex flex-col items-center justify-center py-16">
              <span class="material-symbols-outlined text-6xl text-outline mb-4">inbox</span>
              <p class="text-on-surface-variant text-lg">No findings match your filters</p>
            </div>
            <div v-if="findingsStore.loading" class="col-span-full flex items-center justify-center py-16">
              <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
            </div>
          </div>
        </template>
      </div>
    </template>
  </AppShell>

  <SkillBreakdownDialog
    :open="breakdownOpen"
    :user-id="authStore.user?.id ?? 0"
    :skill-id="breakdownSkillId"
    :project-id="devProjectFilter ?? projectsStore.selectedProjectId ?? 0"
    @close="breakdownOpen = false"
  />
</template>

<style scoped>
.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.25s ease, opacity 0.25s ease; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(100%); opacity: 0; }
</style>
