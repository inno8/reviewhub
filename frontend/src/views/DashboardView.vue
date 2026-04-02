<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
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

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (authStore.isAdmin) {
    await loadAdminData();
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
        <!-- Project cards (no project selected) -->
        <template v-if="!devSelectedProject">
          <header class="mb-10">
            <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">{{ currentDate }}</h1>
            <p class="text-outline text-sm">Select a project to view findings and issues.</p>
          </header>

          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div
              v-for="project in projectsStore.projects" :key="project.id"
              class="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all cursor-pointer group h-full flex flex-col"
              @click="selectDevProject(project.id)">
              <div class="flex items-start justify-between mb-4">
                <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                  <span class="material-symbols-outlined text-primary text-2xl">terminal</span>
                </div>
                <span class="material-symbols-outlined text-outline group-hover:text-primary transition-colors">arrow_forward</span>
              </div>
              <h3 class="text-lg font-bold text-on-surface mb-1">{{ project.displayName }}</h3>
              <p class="text-xs text-outline mb-4 line-clamp-2 flex-1">{{ project.description || 'No description' }}</p>
              <div class="flex items-center gap-3 text-xs text-outline">
                <span class="flex items-center gap-1"><span class="material-symbols-outlined text-sm">code</span>Project</span>
              </div>
            </div>

            <div v-if="!projectsStore.projects.length" class="col-span-full flex flex-col items-center justify-center py-16">
              <span class="material-symbols-outlined text-6xl text-outline mb-4">folder_open</span>
              <p class="text-on-surface-variant text-lg">No projects assigned to you</p>
              <p class="text-outline text-sm">Ask your admin to add you to a project.</p>
            </div>
          </div>
        </template>

        <!-- Issues view (project selected) -->
        <template v-else>
          <header class="mb-10">
            <button @click="backToProjects" class="flex items-center gap-1 text-sm text-outline hover:text-primary mb-4 transition-colors">
              <span class="material-symbols-outlined text-sm">arrow_back</span> All Projects
            </button>
            <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">{{ currentDate }}</h1>
            <p class="text-outline text-sm">
              <span class="text-primary font-semibold">{{ filteredFindings.length }} findings</span> across {{ fileGroups.length }} files
            </p>
          </header>

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
</template>

<style scoped>
.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.25s ease, opacity 0.25s ease; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(100%); opacity: 0; }
</style>
