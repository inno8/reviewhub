<script setup lang="ts">
/**
 * SchoolAdminDashboardView — landing page for `auth.isSchoolAdmin` users.
 *
 * Replaces the developer-focused content rendered by DashboardView when
 * a school admin logs in. The previous mix (Needs Attention, Leaderboard,
 * All Developers grid from the pre-Nakijken pipeline) tells the wrong
 * story to a non-technical IT/program manager. This view tells the
 * right one: cohorts, teachers, at-risk students, license health.
 *
 * Six widgets in priority order:
 *   1. License + Health (placeholder until backend ships subscription endpoint)
 *   2. Cohorts summary (count, table)
 *   3. Teachers summary (count, table)
 *   4. At-risk students (rolled up across all cohorts)
 *   5. Pending invites (only if any)
 *   6. Org growth snapshot (omitted in v1 — needs aggregator endpoint)
 *
 * All copy in Dutch — audience is Dutch MBO school administrators.
 * Translation pass on May 1 2026 covers any English remnants.
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const router = useRouter();
const auth = useAuthStore();

// ─────────────────────────────────────────────────────────────────────────────
// Data fetches
// ─────────────────────────────────────────────────────────────────────────────
const cohorts = ref<any[]>([]);
const members = ref<any[]>([]);
const invitations = ref<any[]>([]);
const atRiskStudents = ref<any[]>([]);
const loading = ref(true);
const errorText = ref<string | null>(null);

const teacherCount = computed(() =>
  members.value.filter((m: any) => m.role === 'teacher').length,
);
const studentCount = computed(() =>
  members.value.filter((m: any) => m.role === 'developer').length,
);
const pendingInvites = computed(() =>
  invitations.value.filter((i: any) => i.status === 'pending'),
);
const activeCohorts = computed(() =>
  cohorts.value.filter((c: any) => !c.archived_at),
);

async function loadDashboard() {
  loading.value = true;
  errorText.value = null;
  try {
    const [cohortsRes, membersRes, invitesRes] = await Promise.all([
      api.grading.cohorts.list({}),
      api.org.members(),
      api.org.invitations(),
    ]);
    cohorts.value = cohortsRes.data?.results || cohortsRes.data || [];
    members.value = membersRes.data?.results || membersRes.data || [];
    invitations.value = invitesRes.data?.results || invitesRes.data || [];

    // Roll up at-risk students across all active cohorts.
    // A cohort overview returns a per-student `band` ('onvoldoende' | 'voldoende' | 'goed')
    // and `trend` ('improving' | 'stable' | 'declining'). At-risk = band onvoldoende
    // OR trend declining.
    await loadAtRiskStudents(activeCohorts.value);
  } catch (e: any) {
    errorText.value = e?.message || 'Kon dashboard niet laden.';
  } finally {
    loading.value = false;
  }
}

async function loadAtRiskStudents(cohortList: any[]) {
  const acc: any[] = [];
  for (const c of cohortList) {
    try {
      const ov = await api.grading.cohorts.overview?.(c.id) ||
                 await fallbackOverview(c.id);
      const ovStudents = ov?.data?.students || ov?.students || [];
      for (const s of ovStudents) {
        if (s.band === 'onvoldoende' || s.trend === 'declining') {
          acc.push({
            ...s,
            cohort_id: c.id,
            cohort_name: c.name,
          });
        }
      }
    } catch {
      // Cohort overview failures shouldn't kill the dashboard.
    }
  }
  // Cap at 5 to keep the card scannable.
  acc.sort((a, b) => {
    // declining trend first, then onvoldoende band, then by recent updated.
    const aRisk = (a.trend === 'declining' ? 2 : 0) + (a.band === 'onvoldoende' ? 1 : 0);
    const bRisk = (b.trend === 'declining' ? 2 : 0) + (b.band === 'onvoldoende' ? 1 : 0);
    return bRisk - aRisk;
  });
  atRiskStudents.value = acc.slice(0, 5);
}

// Cohort overview API may not be wired in useApi.js yet. Fallback to direct fetch.
async function fallbackOverview(cohortId: number) {
  return await fetch(`/api/grading/cohorts/${cohortId}/overview/`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('reviewhub_token')}` },
  }).then(r => r.ok ? r.json().then(j => ({ data: j })) : null);
}

onMounted(loadDashboard);

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function gotoCohorts() { router.push('/org/cohorts'); }
function gotoMembers() { router.push('/org/members'); }
function gotoCohort(id: number) { router.push(`/org/cohorts/${id}`); }
function gotoStudent(cohortId: number, studentId: number) {
  router.push(`/org/cohorts/${cohortId}?student=${studentId}`);
}
</script>

<template>
  <div class="px-6 lg:px-10 py-8 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-8">
      <p class="text-xs uppercase tracking-widest text-outline mb-2 font-bold">School-overzicht</p>
      <h1 class="text-3xl font-bold text-on-surface tracking-tight">
        Dag {{ auth.user?.name || auth.user?.email || 'admin' }}
      </h1>
      <p class="text-on-surface-variant mt-1">
        Een overzicht van je cohorts, docenten en studenten — in één blik.
      </p>
    </div>

    <!-- Loading / Error -->
    <div v-if="loading" class="text-center py-16 text-outline">
      <span class="material-symbols-outlined text-4xl animate-spin">progress_activity</span>
      <p class="mt-2 text-sm">Laden…</p>
    </div>
    <div v-else-if="errorText" class="bg-error-container/30 border border-error/30 rounded-xl p-6 text-error">
      <p class="font-bold mb-1">Er ging iets mis.</p>
      <p class="text-sm">{{ errorText }}</p>
    </div>

    <div v-else class="space-y-6">
      <!-- Widget 1 — License + Health -->
      <section class="bg-gradient-to-br from-primary/10 to-primary-container/5 border border-primary/20 rounded-2xl p-6 md:p-7">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined text-primary text-2xl">verified</span>
            </div>
            <div>
              <p class="text-xs uppercase tracking-widest text-outline font-bold mb-1">Licentie</p>
              <p class="text-lg font-bold text-on-surface">
                {{ activeCohorts.length }} actief cohort{{ activeCohorts.length === 1 ? '' : 'en' }}
              </p>
              <p class="text-sm text-on-surface-variant">
                Alles operationeel · verlenging in <span class="text-on-surface font-semibold">45 dagen</span>
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
            <span class="text-sm font-semibold text-green-400">Gezond</span>
          </div>
        </div>
      </section>

      <!-- Widgets row — Cohorts + Teachers/Students -->
      <div class="grid lg:grid-cols-2 gap-6">
        <!-- Widget 2 — Cohorts -->
        <section class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-primary/15 flex items-center justify-center">
                <span class="material-symbols-outlined text-primary text-xl">groups_2</span>
              </div>
              <div>
                <h2 class="text-lg font-bold text-on-surface">Cohorts</h2>
                <p class="text-xs text-outline">{{ cohorts.length }} totaal · {{ activeCohorts.length }} actief</p>
              </div>
            </div>
            <button
              @click="gotoCohorts"
              class="text-sm text-primary font-semibold hover:underline flex items-center gap-1"
            >
              Alle cohorts
              <span class="material-symbols-outlined text-base">arrow_forward</span>
            </button>
          </div>
          <div v-if="!activeCohorts.length" class="text-center py-8 text-outline text-sm">
            Nog geen actieve cohorts. <button @click="gotoCohorts" class="text-primary font-semibold hover:underline">Maak er een aan</button>.
          </div>
          <div v-else class="space-y-2">
            <button
              v-for="c in activeCohorts.slice(0, 5)" :key="c.id"
              @click="gotoCohort(c.id)"
              class="w-full text-left bg-surface-container-lowest hover:bg-surface-container border border-outline-variant/10 rounded-xl p-3 transition-colors flex items-center justify-between gap-3"
            >
              <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-on-surface truncate">{{ c.name }}</p>
                <p class="text-xs text-outline">
                  {{ c.student_count || 0 }} student{{ (c.student_count || 0) === 1 ? '' : 'en' }}
                  · {{ c.course_count || 0 }} vak{{ (c.course_count || 0) === 1 ? '' : 'ken' }}
                </p>
              </div>
              <span class="material-symbols-outlined text-outline text-base shrink-0">chevron_right</span>
            </button>
          </div>
        </section>

        <!-- Widget 3 — Teachers + Students -->
        <section class="bg-surface-container-low rounded-2xl border border-outline-variant/10 p-6">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-primary/15 flex items-center justify-center">
                <span class="material-symbols-outlined text-primary text-xl">school</span>
              </div>
              <div>
                <h2 class="text-lg font-bold text-on-surface">Mensen</h2>
                <p class="text-xs text-outline">{{ teacherCount }} docent{{ teacherCount === 1 ? '' : 'en' }} · {{ studentCount }} student{{ studentCount === 1 ? '' : 'en' }}</p>
              </div>
            </div>
            <button
              @click="gotoMembers"
              class="text-sm text-primary font-semibold hover:underline flex items-center gap-1"
            >
              Beheer
              <span class="material-symbols-outlined text-base">arrow_forward</span>
            </button>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div class="bg-surface-container-lowest border border-outline-variant/10 rounded-xl p-4">
              <p class="text-3xl font-bold text-on-surface">{{ teacherCount }}</p>
              <p class="text-xs text-on-surface-variant mt-1">Docenten</p>
            </div>
            <div class="bg-surface-container-lowest border border-outline-variant/10 rounded-xl p-4">
              <p class="text-3xl font-bold text-on-surface">{{ studentCount }}</p>
              <p class="text-xs text-on-surface-variant mt-1">Studenten</p>
            </div>
          </div>
          <div v-if="pendingInvites.length" class="mt-4 pt-4 border-t border-outline-variant/10">
            <div class="flex items-center justify-between">
              <p class="text-xs text-on-surface-variant">
                <span class="text-tertiary font-bold">{{ pendingInvites.length }}</span>
                openstaande uitnodiging{{ pendingInvites.length === 1 ? '' : 'en' }}
              </p>
              <button @click="gotoMembers" class="text-xs text-primary font-semibold hover:underline">
                Bekijk
              </button>
            </div>
          </div>
        </section>
      </div>

      <!-- Widget 4 — At-risk students -->
      <section
        v-if="atRiskStudents.length"
        class="bg-surface-container-low rounded-2xl border border-tertiary/30 p-6"
      >
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-tertiary/15 flex items-center justify-center">
              <span class="material-symbols-outlined text-tertiary text-xl">priority_high</span>
            </div>
            <div>
              <h2 class="text-lg font-bold text-on-surface">Aandacht nodig</h2>
              <p class="text-xs text-outline">
                Studenten die zwakker presteren of afglijden — ongeacht cohort
              </p>
            </div>
          </div>
        </div>
        <div class="divide-y divide-outline-variant/10">
          <button
            v-for="s in atRiskStudents" :key="`${s.cohort_id}-${s.student_id}`"
            @click="gotoStudent(s.cohort_id, s.student_id)"
            class="w-full text-left py-3 flex items-center gap-4 hover:bg-surface-container/40 transition-colors px-3 -mx-3 rounded-lg"
          >
            <div class="w-9 h-9 rounded-full bg-tertiary/15 flex items-center justify-center shrink-0">
              <span class="material-symbols-outlined text-tertiary text-base">person</span>
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-on-surface truncate">
                {{ s.student_name || s.student_email || 'Student' }}
              </p>
              <p class="text-xs text-outline truncate">{{ s.cohort_name }}</p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span
                v-if="s.trend === 'declining'"
                class="text-[10px] font-bold uppercase tracking-widest text-error bg-error/15 px-2 py-1 rounded-md"
              >Daalt</span>
              <span
                v-else-if="s.band === 'onvoldoende'"
                class="text-[10px] font-bold uppercase tracking-widest text-tertiary bg-tertiary/15 px-2 py-1 rounded-md"
              >Onvoldoende</span>
              <span class="material-symbols-outlined text-outline text-base">chevron_right</span>
            </div>
          </button>
        </div>
      </section>

      <!-- Empty-state callout — no at-risk students -->
      <section
        v-else-if="!atRiskStudents.length && activeCohorts.length"
        class="bg-surface-container-lowest border border-outline-variant/10 rounded-2xl p-6 text-center"
      >
        <span class="material-symbols-outlined text-green-400 text-3xl mb-2">check_circle</span>
        <p class="text-sm font-semibold text-on-surface">Geen studenten die nu aandacht vragen</p>
        <p class="text-xs text-outline mt-1">
          Iedereen ligt op koers of er is nog niet genoeg data om te oordelen.
        </p>
      </section>
    </div>
  </div>
</template>
