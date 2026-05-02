<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
import CategoryTrendChart from '@/components/charts/CategoryTrendChart.vue';
import RecurringErrorsPanel from '@/components/performance/RecurringErrorsPanel.vue';
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
const patterns = ref<any[]>([]);
const rawCategories = ref<any[]>([]);

const showUserList = computed(() => authStore.isAdmin && !selectedUserId.value);

onMounted(async () => {
  await projectsStore.fetchProjects();

  const queryUser = route.query.user;
  if (queryUser) selectedUserId.value = Number(queryUser);

  // For developers: auto-select own ID. For admin: show user list first
  if (!selectedUserId.value && !authStore.isAdmin) {
    selectedUserId.value = authStore.user?.id ?? null;
  }

  if (authStore.isAdmin) {
    await loadAdminUsers();
  }

  if (selectedUserId.value) await loadAll();
});

watch([adminSearch, adminCategoryFilter, adminProjectFilter], () => loadAdminUsers());
watch(() => periodType.value, () => loadPerformance());
// No project watcher — Insights always shows cross-project data

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
  patterns.value = [];
}

async function loadAll() {
  await Promise.all([loadPerformance(), loadTrends(), loadSkills(), loadPatterns(), loadCategories()]);
}

async function loadPerformance() {
  if (!selectedUserId.value) return;
  loading.value = true;
  try {
    // Insights page: aggregate across ALL projects (no project filter)
    const { data } = await api.performance.get(selectedUserId.value, {
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
    // Insights page: aggregate across ALL projects
    const { data } = await api.performance.trends(selectedUserId.value, { days: 30, granularity: 'daily' });
    trends.value = data;
  } catch {
    trends.value = [];
  }
}

async function loadSkills() {
  if (!selectedUserId.value) return;
  try {
    // Insights page: aggregate across ALL projects
    const pid = undefined;
    const { data } = await api.skills.user(selectedUserId.value, pid ?? undefined);
    skillCategories.value = data.categories;
  } catch {
    skillCategories.value = [];
  }
}

async function loadPatterns() {
  if (!selectedUserId.value) return;
  try {
    const { data } = await api.evaluations.patterns({
      userId: selectedUserId.value,
      resolved: 'false',
    });
    patterns.value = Array.isArray(data) ? data : (data.results || []);
  } catch {
    patterns.value = [];
  }
}

async function loadCategories() {
  try {
    const { data } = await api.skills.categories();
    rawCategories.value = Array.isArray(data) ? data : (data.results || data || []);
  } catch {
    rawCategories.value = [];
  }
}

const categoryColors = computed(() => {
  const map: Record<string, string> = {};
  for (const cat of rawCategories.value) {
    const key = (cat.name || '').toUpperCase().replace(/ /g, '_').replace(/&/g, 'AND');
    if (cat.color) map[key] = cat.color;
  }
  return map;
});


function formatCategory(c: string) { return c.split('_').map(p => p.charAt(0) + p.slice(1).toLowerCase()).join(' '); }
// v1.1 (May 2 2026): backend returns developer level / severity as English
// enum keys (beginner/junior/intermediate/senior/expert and critical/warning/
// info/suggestion). The May 1 i18n pass missed these because they came in
// as DATA, not template literals — visible on the demo path though.
function levelLabel(l: string | null | undefined): string {
  const map: Record<string, string> = {
    beginner: 'Beginner',
    junior: 'Junior',
    intermediate: 'Halfgevorderd',
    senior: 'Senior',
    expert: 'Expert',
  };
  return l ? (map[l.toLowerCase()] || l) : 'Onbekend';
}
function severityLabel(s: string | number | null | undefined): string {
  const key = String(s || '').toLowerCase();
  const map: Record<string, string> = {
    critical: 'Kritiek',
    warning: 'Waarschuwing',
    info: 'Info',
    suggestion: 'Suggestie',
  };
  return map[key] || String(s || '');
}
function getSkillLevel(s: number) { if (s >= 90) return 'Expert'; if (s >= 75) return 'Gevorderd'; if (s >= 50) return 'Halfgevorderd'; if (s >= 25) return 'In ontwikkeling'; return 'Beginner'; }
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
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Analyse</span>
          <h1 class="text-5xl font-black tracking-tighter text-on-surface">
            {{ showUserList ? 'Klas-overzicht' : 'Voortgang — alle projecten' }}
          </h1>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <button v-if="authStore.isAdmin && selectedUserId" @click="backToList"
            class="flex items-center gap-2 px-4 py-2 bg-surface-container rounded-lg border border-outline-variant/20 text-sm hover:text-primary transition-colors">
            <span class="material-symbols-outlined text-sm">arrow_back</span> Alle gebruikers
          </button>

          <template v-if="selectedUserId">
            <div v-if="selectedUserObj" class="flex items-center gap-2 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20">
              <div class="w-6 h-6 rounded-full bg-secondary-container flex items-center justify-center text-xs font-bold text-primary">
                {{ selectedUserObj.username.charAt(0).toUpperCase() }}
              </div>
              <span class="text-sm font-semibold">{{ selectedUserObj.display_name || selectedUserObj.username }}</span>
            </div>

            <!-- Insights shows cross-project data — no project filter for developers -->

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
          <input v-model="adminSearch" type="text" placeholder="Zoeken..."
            class="w-56 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm" />
          <select v-model="adminCategoryFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">Alle categorieën</option>
            <option v-for="c in adminCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select v-model="adminProjectFilter"
            class="bg-surface-container-lowest border-none rounded-lg text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4">
            <option :value="null">Alle projecten</option>
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
                <p class="text-[8px] text-outline uppercase">Bevindingen</p>
              </div>
              <div class="bg-surface-container-lowest rounded-lg p-2">
                <p class="text-base font-black" :class="u.fix_rate >= 50 ? 'text-green-400' : 'text-error'">{{ u.fix_rate }}%</p>
                <p class="text-[8px] text-outline uppercase">Fix-percentage</p>
              </div>
            </div>
          </div>
          <div v-if="!adminUsers.length" class="col-span-full text-center py-16">
            <span class="material-symbols-outlined text-6xl text-outline mb-4">group</span>
            <p class="text-outline">Geen ontwikkelaars gevonden</p>
          </div>
        </div>
      </template>

      <!-- ═══ User Performance View ═══ -->
      <template v-else>
        <!-- Stats Grid -->
        <section v-if="performance" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Totaal commits</p>
            <h3 class="text-3xl font-black">{{ performance.commitCount }}</h3>
          </div>
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-tertiary">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Totaal bevindingen</p>
            <h3 class="text-3xl font-black">{{ performance.findingCount }}</h3>
          </div>
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-primary-container">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Fix-percentage</p>
            <h3 class="text-3xl font-black">{{ performance.fixRate }}%</h3>
          </div>
          <div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-outline">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Review-snelheid</p>
            <h3 class="text-3xl font-black">{{ performance.reviewVelocity !== null ? performance.reviewVelocity + 'd' : '—' }}</h3>
          </div>
        </section>
        <section v-else-if="!loading" class="mb-12">
          <div class="bg-surface-container-low p-8 rounded-xl text-center">
            <span class="material-symbols-outlined text-4xl text-outline mb-2">analytics</span>
            <p class="text-outline">Geen voortgangsdata beschikbaar.</p>
          </div>
        </section>

        <!-- Developer Level Badge + Severity Distribution + Category Breakdown -->
        <section v-if="performance" class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
          <!-- Developer Level -->
          <div class="bg-surface-container-low p-6 rounded-xl text-center">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-3">Ontwikkelaarsniveau</p>
            <div class="inline-flex items-center justify-center w-24 h-24 rounded-full mb-3"
              :class="{
                'bg-red-500/20 text-red-400': performance.level === 'beginner',
                'bg-orange-500/20 text-orange-400': performance.level === 'junior',
                'bg-yellow-500/20 text-yellow-400': performance.level === 'intermediate',
                'bg-green-500/20 text-green-400': performance.level === 'senior',
                'bg-primary/20 text-primary': performance.level === 'expert',
              }">
              <span class="text-2xl font-black uppercase">{{ performance.level?.[0] }}</span>
            </div>
            <p class="text-lg font-bold">{{ levelLabel(performance.level) }}</p>
            <p class="text-sm text-outline mt-1">{{ performance.compositeScore || performance.averageScore }} pt totaal</p>
          </div>

          <!-- Level Breakdown -->
          <div v-if="performance.levelBreakdown" class="bg-surface-container-low p-6 rounded-xl">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-4">Niveau-verdeling</p>
            <div class="space-y-2.5">
              <div v-for="(data, factor) in performance.levelBreakdown" :key="factor" class="flex items-center gap-2">
                <span class="text-[9px] font-medium w-20 text-right capitalize">{{ String(factor).replace('_', ' ') }}</span>
                <div class="flex-1 bg-surface-container-lowest rounded-full h-3 overflow-hidden">
                  <div class="h-full rounded-full transition-all"
                    :class="data.score >= 70 ? 'bg-green-500' : data.score >= 40 ? 'bg-yellow-500' : 'bg-red-500'"
                    :style="{ width: data.score + '%' }"></div>
                </div>
                <span class="text-[9px] font-bold w-8 text-right">{{ data.weighted }}pt</span>
              </div>
            </div>
          </div>

          <!-- Severity Distribution -->
          <div class="bg-surface-container-low p-6 rounded-xl">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-4">Bevindingen per ernst</p>
            <div v-if="performance.severityDistribution" class="space-y-3">
              <div v-for="(count, severity) in performance.severityDistribution" :key="severity" class="flex items-center gap-3">
                <span class="text-xs font-bold uppercase w-20"
                  :class="{
                    'text-red-400': severity === 'critical',
                    'text-orange-400': severity === 'warning',
                    'text-blue-400': severity === 'info',
                    'text-green-400': severity === 'suggestion',
                  }">{{ severityLabel(severity) }}</span>
                <div class="flex-1 bg-surface-container-lowest rounded-full h-4 overflow-hidden">
                  <div class="h-full rounded-full transition-all"
                    :class="{
                      'bg-red-500': severity === 'critical',
                      'bg-orange-500': severity === 'warning',
                      'bg-blue-500': severity === 'info',
                      'bg-green-500': severity === 'suggestion',
                    }"
                    :style="{ width: performance.findingCount ? (count / performance.findingCount * 100) + '%' : '0%' }">
                  </div>
                </div>
                <span class="text-sm font-bold w-8 text-right">{{ count }}</span>
              </div>
            </div>
            <p v-else class="text-sm text-outline text-center py-4">Nog geen data</p>
          </div>

          <!-- Top Issue Categories -->
          <div class="bg-surface-container-low p-6 rounded-xl">
            <p class="text-outline text-xs font-bold uppercase tracking-wider mb-4">Belangrijkste probleemgebieden</p>
            <div v-if="performance.categoryBreakdown?.length" class="space-y-2">
              <div v-for="cat in performance.categoryBreakdown.slice(0, 6)" :key="cat.name"
                class="flex items-center gap-3 cursor-pointer hover:bg-surface-container-lowest rounded-lg p-1 -m-1 transition-colors"
                @click="cat.id && openSkillBreakdown(cat.id)">
                <span class="text-xs font-medium w-28 truncate">{{ cat.name }}</span>
                <div class="flex-1 bg-surface-container-lowest rounded-full h-3 overflow-hidden">
                  <div class="h-full bg-tertiary rounded-full transition-all"
                    :style="{ width: (cat.count / performance.categoryBreakdown[0].count * 100) + '%' }">
                  </div>
                </div>
                <span class="text-xs font-bold w-6 text-right">{{ cat.count }}</span>
                <span class="material-symbols-outlined text-xs text-outline">chevron_right</span>
              </div>
            </div>
            <p v-else class="text-sm text-outline text-center py-4">Nog geen data</p>
          </div>
        </section>

        <!-- Progression Tracker -->
        <section v-if="performance?.progression?.length >= 2" class="mb-12">
          <div class="bg-surface-container-low rounded-3xl p-8 border border-outline-variant/10">
            <div class="flex justify-between items-start mb-6">
              <div>
                <h4 class="text-xl font-bold">Jouw voortgang</h4>
                <p class="text-sm text-outline mt-1">Elk punt is een commit — de lijn laat zien hoe je voortschrijdend gemiddelde verbetert in de tijd</p>
              </div>
              <div v-if="performance.progression.length >= 3"
                class="flex items-center gap-2 px-4 py-2 rounded-lg"
                :class="performance.improving ? 'bg-green-500/10 text-green-400' : 'bg-orange-500/10 text-orange-400'">
                <span class="material-symbols-outlined text-sm">{{ performance.improving ? 'trending_up' : 'trending_down' }}</span>
                <span class="text-sm font-bold">
                  {{ performance.improving ? '+' : '' }}{{ performance.improvementPct }}%
                  {{ performance.improving ? 'verbetering' : 'achteruitgang' }}
                </span>
                <span class="text-xs text-outline ml-1">(eerste 3 vs laatste 3 commits)</span>
              </div>
            </div>

            <!-- Legend -->
            <div class="flex gap-6 mb-4 text-xs">
              <span class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-primary"></span> Commit-score (0-100)</span>
              <span class="flex items-center gap-2"><span class="w-8 h-0.5 bg-green-400"></span> Voortschrijdend gemiddelde</span>
              <span class="flex items-center gap-2"><span class="w-3 h-3 rounded-full" style="background:#F78166"></span> Aantal bevindingen</span>
            </div>

            <!-- Chart -->
            <TrendChart
              title=""
              :points="performance.progression.map((p: any) => ({ label: p.commit, value: p.score }))"
              :secondary-points="performance.progression.map((p: any) => ({ label: p.commit, value: p.findings }))"
              :width="800" :height="280"
            />

            <!-- Score zones reference -->
            <div class="flex justify-between mt-4 text-[10px] text-outline px-4">
              <span class="text-red-400">0-39: Vraagt aandacht</span>
              <span class="text-orange-400">40-59: In ontwikkeling</span>
              <span class="text-yellow-400">60-74: Goed op weg</span>
              <span class="text-green-400">75-89: Sterk</span>
              <span class="text-primary">90-100: Expert</span>
            </div>

            <!-- Per-commit details (collapsible) -->
            <details class="mt-6">
              <summary class="text-sm font-bold text-outline cursor-pointer hover:text-on-surface">
                Bekijk commit-voor-commit verdeling ({{ performance.progression.length }} commits)
              </summary>
              <div class="mt-3 space-y-1 max-h-64 overflow-y-auto">
                <div v-for="(p, i) in performance.progression" :key="i"
                  class="flex items-center gap-3 py-2 px-3 rounded-lg text-sm"
                  :class="i % 2 === 0 ? 'bg-surface-container-lowest' : ''">
                  <span class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                    :class="{
                      'bg-red-500/20 text-red-400': p.score < 40,
                      'bg-orange-500/20 text-orange-400': p.score >= 40 && p.score < 60,
                      'bg-yellow-500/20 text-yellow-400': p.score >= 60 && p.score < 75,
                      'bg-green-500/20 text-green-400': p.score >= 75 && p.score < 90,
                      'bg-primary/20 text-primary': p.score >= 90,
                    }">{{ Math.round(p.score) }}</span>
                  <code class="text-xs text-outline w-16">{{ p.commit }}</code>
                  <span class="flex-1 truncate">{{ p.message }}</span>
                  <span class="text-xs text-outline">{{ p.findings }} problemen</span>
                  <span class="text-xs text-outline">gem: {{ p.runningAvg }}</span>
                </div>
              </div>
            </details>
          </div>
        </section>

        <!-- Strengths / Growth -->
        <section v-if="performance" class="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-12">
          <div class="space-y-6">
            <h4 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-1 bg-primary rounded-full"></span>Sterke punten</h4>
            <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
              <div v-for="s in performance.strengths" :key="s" class="flex items-center gap-4 p-4 bg-surface-container-lowest rounded-xl">
                <span class="material-symbols-outlined text-primary">check_circle</span>
                <span class="font-bold">{{ formatCategory(s) }}</span>
              </div>
              <p v-if="!performance.strengths.length" class="text-sm text-outline text-center py-4">Nog geen sterke punten in beeld</p>
            </div>
          </div>
          <div class="space-y-6">
            <h4 class="text-xl font-bold flex items-center gap-2"><span class="w-8 h-1 bg-tertiary rounded-full"></span>Groeipunten</h4>
            <div class="bg-surface-container-low rounded-2xl p-6 space-y-4">
              <div v-for="a in performance.growthAreas" :key="a" class="flex items-center gap-4 p-4 bg-surface-container-lowest rounded-xl">
                <span class="material-symbols-outlined text-tertiary">trending_up</span>
                <span class="font-bold">{{ formatCategory(a) }}</span>
              </div>
              <p v-if="!performance.growthAreas.length" class="text-sm text-outline text-center py-4">Nog geen groeipunten in beeld</p>
            </div>
          </div>
        </section>

        <!-- Category Improvement Trends -->
        <section v-if="trends.length" class="mb-12">
          <div class="bg-surface-container-low rounded-3xl p-8 border border-outline-variant/10">
            <div class="flex justify-between items-start mb-6">
              <div>
                <h4 class="text-xl font-bold">Trends per categorie</h4>
                <p class="text-sm text-outline mt-1">Dagelijkse bevindingen per categorie over de laatste 30 dagen — dalende lijnen betekenen verbetering</p>
              </div>
            </div>
            <CategoryTrendChart :trends="trends" :category-colors="categoryColors" :height="360" />
          </div>
        </section>

        <!-- Recurring Errors -->
        <section v-if="patterns.length" class="mb-12">
          <div class="bg-surface-container-low rounded-3xl p-8 border border-outline-variant/10">
            <div class="mb-6">
              <h4 class="text-xl font-bold flex items-center gap-2">
                <span class="material-symbols-outlined text-tertiary">repeat</span>
                Terugkerende fouten
              </h4>
              <p class="text-sm text-outline mt-1">Patronen die telkens opnieuw verschijnen in je code — los deze op om het snelst te groeien</p>
            </div>
            <RecurringErrorsPanel :patterns="patterns" />
          </div>
        </section>

        <!-- Recommendations -->
        <section v-if="recommendations.length" class="space-y-6 mb-12">
          <h4 class="text-2xl font-black tracking-tight">Aanbevolen leerpad</h4>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div v-for="rec in recommendations.slice(0, 3)" :key="rec.url" class="glass-panel p-6 rounded-2xl border border-outline-variant/10 hover:border-primary/30 transition-all">
              <span class="material-symbols-outlined text-primary mb-4 text-2xl">{{ getRecommendationIcon(rec.type) }}</span>
              <h5 class="font-bold text-lg mb-2">{{ rec.title }}</h5>
              <p class="text-sm text-outline mb-4">{{ rec.reason }}</p>
              <a :href="rec.url" target="_blank" class="text-primary font-bold text-sm">Bekijk bron</a>
            </div>
          </div>
        </section>

        <!-- Skill Progress -->
        <section v-if="skillCategories.length" class="mb-12">
          <h4 class="text-2xl font-black tracking-tight mb-6">Skill-voortgang</h4>
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
                <span class="text-sm font-bold">Gemiddeld</span>
                <span class="text-sm font-bold text-primary">{{ categoryAverage(cat) }}%</span>
              </div>
            </div>
          </div>
        </section>

        <p v-if="loading" class="text-sm text-outline">Voortgangsinzichten laden...</p>
      </template>
    </div>

    <SkillBreakdownDialog :open="breakdownOpen" :user-id="selectedUserId ?? 0" :skill-id="breakdownSkillId"
      :project-id="projectsStore.selectedProjectId ?? 0" @close="breakdownOpen = false" />
  </AppShell>
</template>
