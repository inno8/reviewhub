<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import SchoolAdminDashboardView from '@/views/SchoolAdminDashboardView.vue';
import SkillRadarChart from '@/components/charts/SkillRadarChart.vue';
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
const adminTeam = ref<any>(null);

async function loadAdminTeam() {
  try {
    const { data } = await api.dashboard.adminTeam();
    adminTeam.value = data;
  } catch (e) {
    // Surface to console so DevTools shows the failure mode (401 / 500 / etc.).
    // The earlier silent catch hid stale-token issues — dashboard would render
    // empty with no signal that anything went wrong.
    console.error('loadAdminTeam failed:', e);
    adminTeam.value = null;
  }
}

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
    const { data } = await api.dashboard.developerHome(projectId);
    devHome.value = data;
  } catch (e) {
    // Surface to console — bare axios + silent catch was masking 401s when
    // the access token expired (~15 min after login). Dashboard appeared
    // empty even though the backend had real data. The shared client now
    // handles the silent refresh and retries the request automatically.
    console.error('loadDevHome failed:', e);
    devHome.value = null;
  } finally {
    devHomeLoading.value = false;
  }
}

function setProjectFilter(projectId: number | null) {
  devProjectFilter.value = projectId;
  loadDevHome(projectId ?? undefined);
}

const showLevelBreakdown = ref(false);

function getLevelColor(level: string) {
  const m: Record<string, string> = { beginner: 'text-red-400', junior: 'text-orange-400', intermediate: 'text-yellow-400', senior: 'text-green-400', expert: 'text-primary' };
  return m[level] || 'text-outline';
}
function getLevelBg(level: string) {
  const m: Record<string, string> = { beginner: 'bg-red-500/15', junior: 'bg-orange-500/15', intermediate: 'bg-yellow-500/15', senior: 'bg-green-500/15', expert: 'bg-primary/15' };
  return m[level] || 'bg-surface-container';
}

// ─── Teacher dashboard data (Nakijken-aware) ───────────────────────────────
// Single round-trip aggregate replacing the legacy admin-team chrome.
// Returns counts by state + oldest drafted PRs + review-time aggregate +
// top recurring patterns scoped to this teacher's cohorts.
interface InboxKpi {
  needs_draft: number;
  needs_review: number;
  in_review: number;
  posted_today: number;
  posted_this_week: number;
}
interface InboxNextUpRow {
  id: number;
  pr_title: string;
  pr_url: string;
  student_id: number | null;
  student_name: string;
  course_name: string | null;
  cohort_id: number | null;
  cohort_name: string | null;
  iteration_number: number;
  days_waiting: number;
  state: string;
  due_at: string | null;
}
interface InboxReviewTime {
  p50_seconds: number | null;
  p95_seconds: number | null;
  samples: number;
  target_seconds: number;
}
interface InboxRecurringPattern {
  pattern_key: string;
  pattern_type: string;
  frequency: number;
  students_affected: number;
}
interface InboxSummary {
  kpi: InboxKpi;
  next_up: InboxNextUpRow[];
  review_time: InboxReviewTime;
  recurring_patterns: InboxRecurringPattern[];
}

const inboxSummary = ref<InboxSummary | null>(null);
const inboxLoading = ref(false);

async function loadInboxSummary() {
  inboxLoading.value = true;
  try {
    const { data } = await (api as any).grading.sessions.inboxSummary();
    inboxSummary.value = data as InboxSummary;
  } catch (err) {
    console.error('inbox-summary failed:', err);
    inboxSummary.value = null;
  } finally {
    inboxLoading.value = false;
  }
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem ? `${h}u ${rem}m` : `${h}u`;
}

function reviewTimeStatus(rt: InboxReviewTime | undefined | null): {
  color: string; label: string;
} {
  if (!rt || rt.p50_seconds == null) return { color: 'text-outline', label: 'geen data' };
  if (rt.p50_seconds <= rt.target_seconds) return { color: 'text-green-400', label: 'onder doel' };
  if (rt.p50_seconds <= rt.target_seconds * 1.5) return { color: 'text-yellow-400', label: 'rond doel' };
  return { color: 'text-orange-400', label: 'boven doel' };
}

function goToInboxFiltered(state: string) {
  router.push({ path: '/grading', query: { state } });
}

function goToSession(sessionId: number) {
  router.push({ name: 'grading-session-detail', params: { id: sessionId } });
}

function goToStudent(studentId: number) {
  router.push({ name: 'grading-student-profile', params: { id: studentId } });
}

// ─── Student dashboard data (Nakijken-aware) ───────────────────────────────
// Two extra fetches on top of the legacy developer-home aggregate, so the
// student lands on "what did my teacher say + how am I doing on the rubric"
// instead of pre-Nakijken commit-level numbers. Both endpoints already work
// for students per the access fix in 29bafcb.
interface StudentLatestFeedback {
  session_id: number;
  pr_title: string;
  pr_url: string;
  course_name: string | null;
  posted_at: string;
  comment_count: number;
  has_summary: boolean;
}
interface StudentPerSkill {
  skill_slug: string;
  display_name: string;
  bayesian_score: number | null;
  confidence: number;
  observation_count: number;
  trend: 'up' | 'down' | 'stable';
  trend_delta: number;
  level_label: string | null;
  kerntaak: string | null;
}
const studentLatestFeedback = ref<StudentLatestFeedback | null>(null);
const studentPerSkill = ref<StudentPerSkill[]>([]);
const studentCohortName = ref<string | null>(null);

async function loadStudentLatestFeedback() {
  try {
    const { data } = await (api as any).grading.sessions.list({
      state: 'posted', page_size: 1, ordering: '-posted_at',
    });
    const rows = Array.isArray(data) ? data : (data.results || []);
    if (!rows.length) {
      studentLatestFeedback.value = null;
      return;
    }
    const r = rows[0];
    // The list serializer is leaner than the detail one — fetch full
    // detail just for the most-recent row so we have final_comments and
    // final_summary populated. One extra request is fine; this is the
    // pitch hero card.
    const { data: full } = await (api as any).grading.sessions.get(r.id);
    studentLatestFeedback.value = {
      session_id: full.id,
      pr_title: full.pr_title || full.repo_full_name || '',
      pr_url: full.pr_url || '',
      course_name: full.course_name || null,
      posted_at: full.posted_at || full.updated_at,
      comment_count: (full.final_comments || full.ai_draft_comments || []).length,
      has_summary: !!(full.final_summary && full.final_summary.trim()),
    };
  } catch {
    studentLatestFeedback.value = null;
  }
}

// snapshot.skill_radar drives the "Sterke en zwakke plekken" radar — same
// data shape and aggregation the teacher sees on TeacherStudentProfileView,
// so a student looking at their own dashboard sees identical numbers to
// the teacher's view of them. Hardcoded English "Skill Overview" was a
// pre-Crebo artifact; aligned now to the Dutch label the docent uses.
const studentSkillRadar = ref<Array<{ category: string; score: number }>>([]);

async function loadStudentSnapshot() {
  const sid = authStore.user?.id;
  if (!sid) return;
  try {
    // Route through the shared axios client so the 401-refresh interceptor
    // fires when the access token is stale. The previous bare axios call
    // with a manual localStorage Authorization header bypassed the
    // interceptor and silently caught every error — students saw
    // "Nog geen rubric-data" on the Eindniveau widget even when the
    // backend had real per_skill data.
    const { data } = await api.grading.students.snapshot(sid);
    studentPerSkill.value = data.per_skill || [];
    studentCohortName.value = data.student?.cohort?.name || null;
    studentSkillRadar.value = (data.skill_radar || []).map((r: any) => ({
      category: r.category,
      score: r.score,
    }));
  } catch (e) {
    console.error('loadStudentSnapshot failed:', e);
    studentPerSkill.value = [];
    studentSkillRadar.value = [];
  }
}

// Eindniveau: weighted avg of bayesian_score across rubric criteria,
// rendered on the 0-4 rubric scale (divide by 25). Mirrors the teacher
// view at /grading/students/<id> so a student sees the same number their
// teacher does.
const eindniveau = computed<number | null>(() => {
  const usable = studentPerSkill.value.filter(r => r.bayesian_score !== null);
  if (usable.length === 0) return null;
  const sum = usable.reduce((s, r) => s + (r.bayesian_score as number), 0);
  return sum / usable.length / 25;
});

interface EindniveauBand {
  label: string;
  bar: string;
  pill: string;
}
const eindniveauBand = computed<EindniveauBand>(() => {
  const v = eindniveau.value;
  if (v === null) return { label: 'Geen data', bar: 'bg-outline-variant', pill: 'bg-surface-container text-on-surface-variant' };
  if (v < 2) return { label: 'Onvoldoende', bar: 'bg-error', pill: 'bg-error/15 text-error' };
  if (v < 3) return { label: 'Net aan', bar: 'bg-tertiary', pill: 'bg-tertiary/20 text-tertiary' };
  if (v < 3.5) return { label: 'Voldoende', bar: 'bg-primary', pill: 'bg-primary/20 text-primary' };
  return { label: 'Goed', bar: 'bg-emerald-400', pill: 'bg-emerald-900/40 text-emerald-300' };
});

// Aanbevolen focus: the weakest criterion with at least 2 observations
// (so we don't recommend a focus area on a single noisy score). Tie-break
// on trend (down first) then lower confidence.
interface FocusItem {
  criterion: string;
  score_of_4: number;
  trend_label: string;
  observation_count: number;
}
const focus = computed<FocusItem | null>(() => {
  const rows = studentPerSkill.value.filter(
    r => r.bayesian_score !== null && r.observation_count >= 2,
  );
  if (rows.length === 0) return null;
  const sorted = [...rows].sort((a, b) => {
    const sa = a.bayesian_score as number;
    const sb = b.bayesian_score as number;
    if (sa !== sb) return sa - sb;
    const trendRank = (t: string) => (t === 'down' ? 0 : t === 'stable' ? 1 : 2);
    if (trendRank(a.trend) !== trendRank(b.trend)) return trendRank(a.trend) - trendRank(b.trend);
    return a.confidence - b.confidence;
  });
  const pick = sorted[0];
  return {
    criterion: pick.display_name,
    score_of_4: (pick.bayesian_score as number) / 25,
    trend_label: pick.trend === 'up' ? 'stijgend' : pick.trend === 'down' ? 'dalend' : 'stabiel',
    observation_count: pick.observation_count,
  };
});

function formatRelativeTime(iso: string): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMin = Math.round((now - then) / 60000);
  if (diffMin < 1) return 'zojuist';
  if (diffMin < 60) return `${diffMin} min geleden`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `${diffH} uur geleden`;
  const diffD = Math.round(diffH / 24);
  if (diffD < 14) return `${diffD} dag${diffD === 1 ? '' : 'en'} geleden`;
  const d = new Date(iso);
  return d.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' });
}

function goToLatestFeedback() {
  if (!studentLatestFeedback.value) return;
  router.push({
    name: 'grading-session-detail',
    params: { id: studentLatestFeedback.value.session_id },
  });
}

onMounted(async () => {
  await projectsStore.fetchProjects();
  if (authStore.isAdmin) {
    // The Nakijken aggregate is the front-door story for teachers + admins.
    // loadAdminTeam stays for the "All Developers" grid lower down (legacy
    // pre-Nakijken pipeline data). loadAdminData populates the admin user
    // detail drawer.
    await Promise.all([loadInboxSummary(), loadAdminData(), loadAdminTeam()]);
  } else {
    // Student: legacy dev-home aggregate + the two Nakijken-aware pieces
    // for the new front-door cards. All three independent → fan out.
    await Promise.all([
      loadDevHome(),
      loadStudentLatestFeedback(),
      loadStudentSnapshot(),
    ]);
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
  findingsStore.fetchFindings({ projectId, is_fixed: false });
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

// `backToProjects()` was removed Apr 28 2026 — it pushed to `/projects`
// (the legacy ProjectsView, decoupled from Nakijken grading) but
// nothing in the active UI invoked it. The grading-first v1 nav
// goes Dashboard → Code Review / PR Review / Skills, not back through
// a Projects index. Route still exists for direct-URL access until we
// fully retire the legacy projects.Project model post-pitch.

watch(() => projectsStore.selectedProjectId, async (newId) => {
  if (newId && !authStore.isAdmin && devSelectedProject.value) {
    await findingsStore.fetchFindings({ projectId: newId, is_fixed: false });
  }
});

function clearDateFilter() {
  selectedDate.value = null;
  if (projectsStore.selectedProjectId) findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId, is_fixed: false });
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
function openFile(filePath: string) { router.push({ path: '/file-review', query: { file: filePath, ids: groupedByFile.value[filePath].map(f => f.id).join(','), project: devSelectedProject.value ? String(devSelectedProject.value) : undefined } }); }
function formatCategory(cat: string) { return cat.replace('_', ' '); }

function scoreColor(score: number) {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-yellow-400';
  return 'text-error';
}
</script>

<template>
  <AppShell>
    <!-- ═══ SCHOOL ADMIN DASHBOARD (new Apr 28 2026) ═══
         A non-developer IT/program manager doesn't need the per-student
         code metrics, leaderboards, or commit feeds the legacy admin
         dashboard rendered. They need cohorts, teachers, students-at-
         risk, license health. SchoolAdminDashboardView is the answer.
         Falls through to the existing admin dashboard for superusers
         and teacher-admins (a school admin role + teacher role combo). -->
    <template v-if="authStore.isSchoolAdmin && !authStore.isTeacher && !authStore.isSuperuser">
      <SchoolAdminDashboardView />
    </template>

    <!-- ═══ ADMIN DASHBOARD ═══ -->
    <template v-else-if="authStore.isAdmin">
      <div class="p-8 flex-1">
        <!-- Teacher-first hero banner (shown for role=teacher before the admin KPIs). -->
        <section
          v-if="authStore.isTeacher"
          class="mb-8 p-6 rounded-xl bg-primary/10 border border-primary/30 flex flex-wrap items-center justify-between gap-4"
          data-testid="teacher-hero-banner"
        >
          <div class="min-w-0">
            <p class="text-[11px] uppercase tracking-[0.2em] text-primary font-bold">Nakijken Copilot</p>
            <h1 class="text-2xl md:text-3xl font-black text-on-surface tracking-tight mt-1">
              Welkom terug{{ authStore.user?.first_name ? `, ${authStore.user.first_name}` : '' }}.
            </h1>
            <p class="text-sm text-on-surface-variant mt-1">
              Ga naar je inbox om de PRs van je studenten na te kijken.
            </p>
          </div>
          <button
            @click="router.push('/grading')"
            class="primary-gradient text-on-primary font-bold px-5 py-2.5 rounded-lg text-sm shadow-lg shadow-primary/10 hover:shadow-primary/20 active:scale-95 inline-flex items-center gap-1.5"
            data-testid="teacher-start-grading-btn"
          >
            <span class="material-symbols-outlined text-base">rate_review</span>
            <span>Nakijken beginnen</span>
          </button>
        </section>

        <header class="mb-8">
          <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">
            {{ authStore.isTeacher ? 'Vandaag op je bord' : 'Admin Dashboard' }}
          </span>
          <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">
            {{ authStore.isTeacher ? 'Welkom terug' : 'Team Overview' }}
          </h1>
        </header>

        <!-- ════════════════════════════════════════════════════════════════
             NAKIJKEN COPILOT — front-door teacher KPIs
             Single round-trip from /sessions/inbox-summary/ replaces a
             half-dozen legacy admin-team calls and tells the docent the
             three numbers they actually opened the app to find.
        ════════════════════════════════════════════════════════════════ -->
        <section
          v-if="authStore.isTeacher && inboxSummary"
          class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8"
          data-testid="inbox-kpi-row"
        >
          <button
            type="button"
            class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-left hover:border-primary/30 transition-colors group"
            @click="goToInboxFiltered('pending')"
          >
            <p class="text-3xl font-black text-on-surface group-hover:text-primary">
              {{ inboxSummary.kpi.needs_draft }}
            </p>
            <p class="text-[11px] text-outline uppercase tracking-wider mt-1">Concept opstellen</p>
          </button>

          <button
            type="button"
            class="primary-gradient p-5 rounded-xl text-left shadow-lg shadow-primary/15 hover:shadow-primary/30 transition-shadow group"
            @click="goToInboxFiltered('drafted')"
            data-testid="needs-review-card"
          >
            <p class="text-3xl font-black text-on-primary">
              {{ inboxSummary.kpi.needs_review }}
            </p>
            <p class="text-[11px] uppercase tracking-wider mt-1 text-on-primary/80">Klaar voor review</p>
          </button>

          <button
            type="button"
            class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-left hover:border-primary/30 transition-colors group"
            @click="goToInboxFiltered('reviewing')"
          >
            <p class="text-3xl font-black text-on-surface group-hover:text-primary">
              {{ inboxSummary.kpi.in_review }}
            </p>
            <p class="text-[11px] text-outline uppercase tracking-wider mt-1">Mid-review</p>
          </button>

          <button
            type="button"
            class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-left hover:border-primary/30 transition-colors group"
            @click="goToInboxFiltered('posted')"
          >
            <p class="text-3xl font-black text-green-400">
              {{ inboxSummary.kpi.posted_this_week }}
            </p>
            <p class="text-[11px] text-outline uppercase tracking-wider mt-1">Verstuurd · 7 dagen</p>
            <p
              v-if="inboxSummary.kpi.posted_today"
              class="text-[10px] text-green-400 mt-0.5"
            >+{{ inboxSummary.kpi.posted_today }} vandaag</p>
          </button>
        </section>

        <!-- Two-column: Next-up inbox preview + review-time / patterns -->
        <section
          v-if="authStore.isTeacher && inboxSummary"
          class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10"
          data-testid="inbox-detail-row"
        >
          <!-- Next up (oldest drafted) -->
          <div class="lg:col-span-2 bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="px-5 py-3 border-b border-outline-variant/10 flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary text-sm">rate_review</span>
                <h3 class="text-sm font-bold">Next up</h3>
              </div>
              <button
                @click="router.push('/grading')"
                class="text-[11px] text-primary font-semibold hover:underline"
              >
                Open inbox →
              </button>
            </div>
            <div v-if="inboxSummary.next_up.length === 0" class="p-8 text-center text-on-surface-variant text-sm">
              <span class="material-symbols-outlined text-3xl text-outline mb-2 block">check_circle</span>
              Geen openstaande PRs. Alles is bijgewerkt.
            </div>
            <ul v-else class="divide-y divide-outline-variant/10">
              <li
                v-for="row in inboxSummary.next_up"
                :key="row.id"
                class="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-surface-container-lowest transition-colors group"
                @click="goToSession(row.id)"
                :data-testid="`next-up-${row.id}`"
              >
                <button
                  type="button"
                  class="w-8 h-8 rounded-full bg-surface-container-highest text-on-surface text-[11px] font-bold flex-shrink-0 inline-flex items-center justify-center hover:bg-primary/15 hover:text-primary transition-colors"
                  :title="`Profiel van ${row.student_name}`"
                  @click.stop="row.student_id && goToStudent(row.student_id)"
                >
                  {{ (row.student_name || '?').slice(0, 2).toUpperCase() }}
                </button>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-semibold text-on-surface truncate">{{ row.pr_title || '(geen titel)' }}</p>
                  <p class="text-xs text-on-surface-variant truncate">
                    {{ row.student_name }}
                    <span v-if="row.cohort_name"> · {{ row.cohort_name }}</span>
                  </p>
                </div>
                <span
                  class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant flex-shrink-0"
                  :class="row.days_waiting >= 7 ? 'text-orange-400 bg-orange-500/10' : ''"
                >
                  {{ row.days_waiting }}d
                </span>
                <span class="material-symbols-outlined text-outline text-sm group-hover:text-primary transition-colors">chevron_right</span>
              </li>
            </ul>
          </div>

          <!-- Right: review time + recurring patterns -->
          <div class="space-y-6">
            <!-- Review time -->
            <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
              <div class="flex items-center gap-2 mb-3">
                <span class="material-symbols-outlined text-primary text-sm">timer</span>
                <h3 class="text-sm font-bold">Reviewtijd p50</h3>
              </div>
              <p
                class="text-3xl font-black"
                :class="reviewTimeStatus(inboxSummary.review_time).color"
              >
                {{ formatDuration(inboxSummary.review_time.p50_seconds) }}
              </p>
              <p class="text-[11px] text-outline mt-1">
                doel ≤ {{ formatDuration(inboxSummary.review_time.target_seconds) }}
                · {{ inboxSummary.review_time.samples }} sample{{ inboxSummary.review_time.samples === 1 ? '' : 's' }}
                · {{ reviewTimeStatus(inboxSummary.review_time).label }}
              </p>
              <p
                v-if="inboxSummary.review_time.p95_seconds != null"
                class="text-[10px] text-on-surface-variant mt-2"
              >
                p95: {{ formatDuration(inboxSummary.review_time.p95_seconds) }}
              </p>
            </div>

            <!-- Recurring patterns -->
            <div class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
              <div class="flex items-center gap-2 mb-3">
                <span class="material-symbols-outlined text-tertiary text-sm">repeat</span>
                <h3 class="text-sm font-bold">Terugkerende patronen</h3>
              </div>
              <ul
                v-if="inboxSummary.recurring_patterns.length"
                class="space-y-2"
              >
                <li
                  v-for="p in inboxSummary.recurring_patterns"
                  :key="p.pattern_key"
                  class="flex items-center gap-2 text-xs"
                >
                  <span class="font-mono text-on-surface truncate flex-1" :title="p.pattern_key">
                    {{ p.pattern_key }}
                  </span>
                  <span class="text-tertiary font-bold">{{ p.frequency }}×</span>
                  <span class="text-outline">·</span>
                  <span class="text-on-surface-variant">{{ p.students_affected }} stud</span>
                </li>
              </ul>
              <p v-else class="text-sm text-on-surface-variant">Geen patronen.</p>
            </div>
          </div>
        </section>

        <!-- ── Team Health Row (legacy admin-team — hidden for teachers) ── -->
        <section v-if="!authStore.isTeacher && adminTeam" class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <div v-if="!authStore.isTeacher" class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
            <p class="text-3xl font-black" :class="adminTeam.teamAvgScore >= 60 ? 'text-green-400' : adminTeam.teamAvgScore >= 40 ? 'text-yellow-400' : 'text-red-400'">
              {{ adminTeam.teamAvgScore }}
            </p>
            <p class="text-[10px] text-outline uppercase mt-1">Team Avg Score</p>
          </div>
          <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
            <p class="text-3xl font-black text-primary">{{ adminTeam.totalDevelopers }}</p>
            <p class="text-[10px] text-outline uppercase mt-1">{{ authStore.isTeacher ? 'Studenten' : 'Developers' }}</p>
          </div>
          <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
            <p class="text-3xl font-black text-tertiary">{{ adminTeam.totalFindings }}</p>
            <p class="text-[10px] text-outline uppercase mt-1">{{ authStore.isTeacher ? 'Feedbackpunten' : 'Total Findings' }}</p>
          </div>
          <div v-if="!authStore.isTeacher" class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
            <p class="text-3xl font-black" :class="adminTeam.teamFixRate > 30 ? 'text-green-400' : 'text-red-400'">{{ adminTeam.teamFixRate }}%</p>
            <p class="text-[10px] text-outline uppercase mt-1">Fix Rate</p>
          </div>
          <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10">
            <p class="text-[10px] text-outline uppercase mb-2">Level Distribution</p>
            <div class="flex gap-1 h-6">
              <div v-for="(count, lvl) in adminTeam.levelDistribution" :key="lvl"
                v-show="count > 0"
                class="rounded flex items-center justify-center text-[9px] font-bold text-white"
                :class="{ 'bg-red-500': lvl === 'beginner', 'bg-orange-500': lvl === 'junior', 'bg-yellow-500': lvl === 'intermediate', 'bg-green-500': lvl === 'senior', 'bg-primary': lvl === 'expert' }"
                :style="{ flex: count }">
                {{ count }}{{ String(lvl)[0].toUpperCase() }}
              </div>
            </div>
          </div>
        </section>

        <!-- ── Two Column: Attention + Leaderboard ──
             Hidden for teachers — legacy admin-team data uses the
             pre-Nakijken per-commit pipeline scoring, which would
             confuse the demo audience next to the rubric grades.
             Stays for non-teacher admins (school admins / superusers)
             since it's the only summary surface they have today. -->
        <section v-if="!authStore.isTeacher && adminTeam" class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <!-- Needs Attention -->
          <div class="bg-surface-container-low rounded-xl border border-outline-variant/10">
            <div class="px-5 py-3 border-b border-outline-variant/10 flex items-center gap-2">
              <span class="material-symbols-outlined text-red-400 text-sm">warning</span>
              <h3 class="text-sm font-bold">Needs Attention</h3>
            </div>
            <div v-if="adminTeam.needsAttention?.length" class="divide-y divide-outline-variant/10">
              <div v-for="a in adminTeam.needsAttention" :key="a.id" class="px-5 py-3 flex items-center gap-3 cursor-pointer hover:bg-surface-container-lowest transition-colors"
                @click="goToUserInsights(a.id)">
                <div class="w-8 h-8 rounded-full bg-red-500/15 flex items-center justify-center text-xs font-bold text-red-400">
                  {{ a.displayName[0] }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-bold truncate">{{ a.displayName }}</p>
                  <p class="text-[10px] text-red-400">{{ a.reasons.join(' · ') }}</p>
                </div>
                <span class="material-symbols-outlined text-xs text-outline">chevron_right</span>
              </div>
            </div>
            <p v-else class="p-5 text-sm text-outline text-center">All developers are on track</p>
          </div>

          <!-- Leaderboard -->
          <div class="bg-surface-container-low rounded-xl border border-outline-variant/10">
            <div class="px-5 py-3 border-b border-outline-variant/10 flex items-center gap-2">
              <span class="material-symbols-outlined text-yellow-400 text-sm">emoji_events</span>
              <h3 class="text-sm font-bold">Leaderboard</h3>
            </div>
            <div class="p-5 space-y-4">
              <div v-if="adminTeam.topImprovers?.length">
                <p class="text-[10px] text-outline uppercase mb-2">Top Improvers</p>
                <div v-for="t in adminTeam.topImprovers" :key="t.id" class="flex items-center gap-2 text-sm">
                  <span class="text-green-400 font-bold">+{{ t.improvement }}%</span>
                  <span class="truncate">{{ t.name }}</span>
                  <span class="text-[9px] text-outline capitalize ml-auto">{{ t.level }}</span>
                </div>
              </div>
              <div v-if="adminTeam.topQuality?.length">
                <p class="text-[10px] text-outline uppercase mb-2">Top Code Quality</p>
                <div v-for="t in adminTeam.topQuality" :key="t.id" class="flex items-center gap-2 text-sm">
                  <span class="text-primary font-bold">{{ t.avgScore }}%</span>
                  <span class="truncate">{{ t.name }}</span>
                  <span class="text-[9px] text-outline capitalize ml-auto">{{ t.level }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Team Patterns and Skill Matrix removed — available in Skills and Journey views -->

        <!-- ── Developer Cards (with enhanced data) ──
             Teachers reach the canonical Nakijken-aware student roster via
             the sidebar "Studenten" link (/grading/students). Hiding this
             pre-Nakijken grid for them avoids two scoring systems on one
             screen. School admins / superusers still see it. -->
        <section v-if="!authStore.isTeacher">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-bold">All Developers</h3>
            <div class="flex items-center gap-3">
              <input v-model="adminSearch" type="text" placeholder="Search..."
                class="w-48 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2 px-3 text-xs" />
              <span class="text-xs text-outline">{{ adminTeam?.developers?.length || adminUsers.length }} devs</span>
            </div>
          </div>
          <div v-if="adminLoading" class="flex items-center justify-center py-16">
            <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="dev in (adminTeam?.developers || [])" :key="dev.id"
              class="bg-surface-container-low p-4 rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all cursor-pointer"
              @click="goToUserInsights(dev.id)">
              <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 rounded-lg bg-secondary-container flex items-center justify-center text-sm font-bold text-primary">
                  {{ dev.displayName[0]?.toUpperCase() || '?' }}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-bold truncate">{{ dev.displayName }}</div>
                  <div class="text-[10px] text-outline">{{ dev.email }}</div>
                </div>
                <div class="text-right">
                  <span class="text-xs font-bold capitalize px-2 py-0.5 rounded-full"
                    :class="getLevelBg(dev.level) + ' ' + getLevelColor(dev.level)">{{ dev.level }}</span>
                  <p class="text-[9px] text-outline mt-0.5">{{ dev.compositeScore }}pts</p>
                </div>
              </div>
              <div class="grid grid-cols-4 gap-2 text-center text-[10px]">
                <div><p class="text-sm font-black">{{ dev.commitCount }}</p><p class="text-outline">Commits</p></div>
                <div><p class="text-sm font-black text-tertiary">{{ dev.findingCount }}</p><p class="text-outline">Findings</p></div>
                <div><p class="text-sm font-black" :class="dev.fixRate > 0 ? 'text-green-400' : 'text-red-400'">{{ dev.fixRate }}%</p><p class="text-outline">Fix Rate</p></div>
                <div><p class="text-sm font-black" :class="dev.improvement > 0 ? 'text-green-400' : dev.improvement < 0 ? 'text-red-400' : 'text-outline'">{{ dev.improvement > 0 ? '+' : '' }}{{ dev.improvement }}%</p><p class="text-outline">Trend</p></div>
              </div>
              <!-- Mini sparkline -->
              <div v-if="dev.sparkline?.length >= 2" class="mt-2 flex items-end gap-0.5 h-6">
                <div v-for="(s, i) in dev.sparkline" :key="i"
                  class="flex-1 rounded-sm transition-all"
                  :class="s >= 70 ? 'bg-green-500/50' : s >= 40 ? 'bg-yellow-500/50' : 'bg-red-500/50'"
                  :style="{ height: Math.max(4, s * 0.24) + 'px' }">
                </div>
              </div>
            </div>
          </div>
        </section>
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

        <!-- Developer Overview (default view, no project filter) -->
        <template v-if="!devSelectedProject && devHome">

          <!-- ════════════════════════════════════════════════════════════
               NAKIJKEN COPILOT — student front-door cards
               (Path B: hero replace; legacy KPI row stays as auxiliary
               stats below.)

               Latest teacher feedback is the platform's promise — show it
               first. Eindniveau on the rubric scale + Aanbevolen focus
               give the student "where am I" + "what to fix next" using
               the same numbers the teacher sees.
          ════════════════════════════════════════════════════════════ -->
          <section
            v-if="studentLatestFeedback || eindniveau !== null"
            class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8"
            data-testid="student-front-door"
          >
            <!-- Latest feedback card (spans 2 cols on lg) -->
            <button
              v-if="studentLatestFeedback"
              type="button"
              class="lg:col-span-2 primary-gradient rounded-xl p-5 text-left shadow-lg shadow-primary/15 hover:shadow-primary/30 transition-shadow group"
              @click="goToLatestFeedback"
              data-testid="latest-feedback-card"
            >
              <div class="flex items-start gap-3">
                <span class="material-symbols-outlined text-on-primary text-xl mt-0.5">rate_review</span>
                <div class="flex-1 min-w-0">
                  <p class="text-[11px] uppercase tracking-[0.2em] text-on-primary/80 font-bold">
                    Feedback van je docent
                  </p>
                  <h2 class="text-lg font-black text-on-primary mt-1 truncate">
                    {{ studentLatestFeedback.pr_title || '(geen titel)' }}
                  </h2>
                  <p class="text-xs text-on-primary/85 mt-1">
                    {{ studentLatestFeedback.comment_count }} comment{{ studentLatestFeedback.comment_count === 1 ? '' : 's' }}
                    <span v-if="studentLatestFeedback.has_summary"> · samenvatting</span>
                    <span v-if="studentLatestFeedback.course_name"> · {{ studentLatestFeedback.course_name }}</span>
                    · {{ formatRelativeTime(studentLatestFeedback.posted_at) }}
                  </p>
                </div>
                <span class="material-symbols-outlined text-on-primary group-hover:translate-x-1 transition-transform">arrow_forward</span>
              </div>
            </button>

            <!-- Empty state when student has no posted feedback yet -->
            <div
              v-else
              class="lg:col-span-2 bg-surface-container-low rounded-xl border border-outline-variant/10 p-5 flex items-center gap-3"
            >
              <span class="material-symbols-outlined text-outline text-xl">rate_review</span>
              <div>
                <p class="text-sm font-semibold text-on-surface">Nog geen feedback ontvangen</p>
                <p class="text-xs text-on-surface-variant mt-0.5">
                  Open een PR om feedback van je docent te krijgen.
                </p>
              </div>
            </div>

            <!-- Eindniveau bar -->
            <div
              v-if="eindniveau !== null"
              class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5"
              data-testid="eindniveau-card"
            >
              <div class="flex items-baseline justify-between gap-2 mb-2">
                <p class="text-[11px] uppercase tracking-wider text-on-surface-variant font-semibold">
                  Eindniveau
                </p>
                <span class="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded font-bold" :class="eindniveauBand.pill">
                  {{ eindniveauBand.label }}
                </span>
              </div>
              <p class="text-3xl font-black text-on-surface">
                {{ eindniveau.toFixed(1) }}<span class="text-base font-bold text-outline">/4</span>
              </p>
              <div class="mt-3 h-2 bg-surface-container rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="eindniveauBand.bar"
                  :style="{ width: Math.min(100, (eindniveau / 4) * 100) + '%' }"
                ></div>
              </div>
              <p v-if="studentCohortName" class="text-[10px] text-outline mt-2">
                {{ studentCohortName }}
              </p>
            </div>
            <div
              v-else
              class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5"
            >
              <p class="text-[11px] uppercase tracking-wider text-on-surface-variant font-semibold">
                Eindniveau
              </p>
              <p class="text-sm text-on-surface-variant mt-2">Nog geen rubric-data.</p>
            </div>
          </section>

          <!-- Aanbevolen focus card -->
          <section
            v-if="focus"
            class="mb-8 p-5 rounded-xl bg-tertiary/10 border border-tertiary/30 flex items-start gap-4"
            data-testid="focus-card"
          >
            <span class="material-symbols-outlined text-tertiary text-xl mt-0.5">target</span>
            <div class="flex-1 min-w-0">
              <p class="text-[11px] uppercase tracking-wider text-tertiary font-bold">
                Aanbevolen focus
              </p>
              <p class="text-base font-bold text-on-surface mt-1">
                {{ focus.criterion }}
                <span class="text-tertiary"> · {{ focus.score_of_4.toFixed(1) }}/4</span>
              </p>
              <p class="text-xs text-on-surface-variant mt-1">
                Trend {{ focus.trend_label }} ·
                {{ focus.observation_count }} observatie{{ focus.observation_count === 1 ? '' : 's' }} ·
                gericht oefenen op dit criterium in je volgende PR.
              </p>
            </div>
            <button
              type="button"
              class="bg-tertiary/15 text-tertiary hover:bg-tertiary/25 px-4 py-2 rounded-lg text-xs font-bold transition-colors flex-shrink-0"
              @click="router.push('/skills')"
            >
              Open Skills →
            </button>
          </section>

          <!-- ── Top Metrics Row (legacy auxiliary stats) ──
               Pre-Nakijken AI-auto-review numbers from the per-commit
               pipeline. Useful at a glance ("how active have I been")
               but NOT the rubric grade — the new cards above own that.
               Demoted by surrounding section header so the audience
               doesn't conflate the two scoring systems. -->
          <p class="text-[11px] uppercase tracking-wider text-outline font-semibold mb-2">
            AI auto-review (over al je commits)
          </p>
          <section class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center">
              <p class="text-4xl font-black" :class="devHome.avgScore >= 70 ? 'text-green-400' : devHome.avgScore >= 50 ? 'text-yellow-400' : 'text-red-400'">
                {{ devHome.avgScore }}%
              </p>
              <p class="text-[10px] text-outline uppercase tracking-wider mt-1">Avg Score</p>
            </div>
            <div class="bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 text-center cursor-pointer group"
              @click="showLevelBreakdown = !showLevelBreakdown">
              <div class="inline-flex items-center justify-center w-12 h-12 rounded-full mb-1" :class="getLevelBg(devHome.level)">
                <span class="text-sm font-black uppercase" :class="getLevelColor(devHome.level)">{{ (devHome.level || '?')[0] }}</span>
              </div>
              <p class="text-sm font-bold capitalize" :class="getLevelColor(devHome.level)">{{ devHome.level }}</p>
              <p v-if="devHome.compositeScore" class="text-[9px] text-outline mt-0.5">{{ devHome.compositeScore }}pts <span class="group-hover:text-primary">▾</span></p>
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
              <div v-if="devHome.streak?.active" class="mt-1 flex items-center gap-1 justify-center">
                <span class="material-symbols-outlined text-xs text-yellow-400">local_fire_department</span>
                <span class="text-[9px] font-bold text-yellow-400">{{ devHome.streak.count }} streak</span>
              </div>
            </div>
          </section>

          <!-- Level Breakdown Panel -->
          <section v-if="showLevelBreakdown && devHome.levelBreakdown" class="mb-8 bg-surface-container-low rounded-xl border border-outline-variant/10 p-5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-sm font-bold">How Your Level Is Calculated</h3>
              <button @click="showLevelBreakdown = false" class="text-xs text-outline hover:text-on-surface">Hide</button>
            </div>
            <div class="space-y-2.5">
              <div v-for="(data, factor) in devHome.levelBreakdown" :key="factor" class="flex items-center gap-3">
                <span class="text-[10px] font-medium w-28 text-right capitalize">{{ String(factor).replace('_', ' ') }} ({{ data.weight }}%)</span>
                <div class="flex-1 bg-surface-container-lowest rounded-full h-4 overflow-hidden">
                  <div class="h-full rounded-full transition-all"
                    :class="data.score >= 70 ? 'bg-green-500' : data.score >= 40 ? 'bg-yellow-500' : 'bg-red-500'"
                    :style="{ width: data.score + '%' }">
                  </div>
                </div>
                <span class="text-xs font-bold w-14 text-right">{{ data.score }}% → {{ data.weighted }}pt</span>
              </div>
            </div>
            <div class="mt-3 pt-3 border-t border-outline-variant/10 flex items-center justify-between">
              <p class="text-xs text-outline">Composite: <strong class="text-on-surface">{{ devHome.compositeScore }}pts</strong></p>
              <p class="text-xs capitalize font-bold" :class="getLevelColor(devHome.level)">{{ devHome.level }}</p>
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

              <!-- Pattern Findings & Resolution Chart -->
              <div v-if="devHome.patternChart?.length" class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
                <div class="flex items-center justify-between p-4 border-b border-outline-variant/10">
                  <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-tertiary">repeat</span>
                    <h3 class="text-sm font-bold">Recurring Patterns</h3>
                  </div>
                  <div class="flex items-center gap-3 text-[10px]">
                    <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-sm bg-tertiary"></span> Active</span>
                    <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-sm bg-green-500"></span> Resolved</span>
                    <span v-if="devHome.patternsResolved || devHome.patternsActive" class="text-outline">
                      {{ devHome.patternsResolved }} resolved · {{ devHome.patternsActive }} active
                    </span>
                  </div>
                </div>

                <!-- Horizontal bar chart -->
                <div class="p-4 space-y-2.5">
                  <div v-for="p in devHome.patternChart" :key="p.name" class="flex items-center gap-3">
                    <span class="text-[10px] font-medium w-24 truncate text-right">{{ p.name }}</span>
                    <div class="flex-1 bg-surface-container-lowest rounded-full h-5 overflow-hidden relative">
                      <div class="h-full rounded-full transition-all flex items-center"
                        :class="p.resolved ? 'bg-green-500/70' : 'bg-tertiary/70'"
                        :style="{ width: Math.max(10, (p.frequency / devHome.patternChart[0].frequency * 100)) + '%' }">
                        <span class="text-[9px] font-bold text-white pl-2">{{ p.frequency }}x</span>
                      </div>
                    </div>
                    <span v-if="p.resolved" class="material-symbols-outlined text-xs text-green-400">check_circle</span>
                    <router-link v-else to="/skills" class="text-[10px] text-primary font-semibold">Fix</router-link>
                  </div>
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

            </div>

            <!-- RIGHT: Visual Column (1/3 width) -->
            <div class="space-y-6">

              <!-- Skill Radar — "Sterke en zwakke plekken" mirrors the
                   teacher's view of this student. Pulled from
                   snapshot.skill_radar (StudentSnapshotView) so student
                   and teacher see the exact same numbers + axes. -->
              <div v-if="studentSkillRadar.length >= 3" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
                <SkillRadarChart :data="studentSkillRadar" title="Sterke en zwakke plekken" />
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

        <!-- Developer Overview (no project selected) -->
        <template v-else-if="devHomeLoading && !devHome">
          <div class="flex items-center justify-center py-20">
            <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
          </div>
        </template>

        <!-- Findings view (project selected from Projects page) -->
        <template v-else-if="devSelectedProject">
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
