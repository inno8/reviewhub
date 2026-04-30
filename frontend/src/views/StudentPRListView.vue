<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-5xl mx-auto">
        <!-- Back button -->
        <button
          @click="goBack"
          class="text-sm text-on-surface-variant hover:text-on-surface transition-colors mb-4 inline-flex items-center gap-1"
          data-testid="back-btn"
        >
          <span class="material-symbols-outlined text-base">arrow_back</span>
          <span>Terug naar overzicht</span>
        </button>

        <!-- Student header / breadcrumb -->
        <header
          v-if="student"
          class="flex items-center gap-4 mb-6 p-5 bg-surface-container-low border border-outline-variant/10 rounded-xl"
        >
          <div
            class="w-14 h-14 rounded-full bg-surface-container-highest text-on-surface-variant flex items-center justify-center overflow-hidden shrink-0"
          >
            <img
              v-if="student.avatar_url"
              :src="student.avatar_url"
              :alt="student.name || student.email"
              class="w-full h-full object-cover"
            />
            <span v-else class="material-symbols-outlined text-3xl">person</span>
          </div>
          <div class="flex-1 min-w-0">
            <h1 class="text-2xl font-extrabold text-on-surface tracking-tight truncate">
              {{ student.name || student.email }}
            </h1>
            <p class="text-xs text-on-surface-variant truncate">{{ student.email }}</p>
          </div>
          <div class="text-right text-xs text-on-surface-variant">
            <div class="font-bold text-on-surface text-lg">{{ sessions.length }}</div>
            <div class="uppercase tracking-widest">PR-geschiedenis</div>
          </div>
        </header>

        <!-- Filters: state chips + sort toggle -->
        <div
          class="flex flex-wrap gap-3 items-center justify-between mb-5"
        >
          <div class="flex flex-wrap gap-1.5" data-testid="state-chips">
            <button
              v-for="chip in stateChips"
              :key="chip.value || 'all'"
              @click="selectedState = chip.value"
              :class="[
                'text-xs font-semibold uppercase tracking-widest px-3 py-1.5 rounded-md transition-colors',
                selectedState === chip.value
                  ? 'bg-primary/15 text-primary'
                  : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high',
              ]"
              :data-testid="`chip-${chip.value || 'all'}`"
            >
              {{ chip.label }}
            </button>
          </div>

          <button
            @click="toggleSort"
            class="bg-surface-container hover:bg-surface-container-high text-on-surface px-3 py-1.5 rounded-md text-xs font-medium border border-outline-variant/20 transition-colors inline-flex items-center gap-1"
            data-testid="sort-toggle"
          >
            <span class="material-symbols-outlined text-sm">swap_vert</span>
            <span>{{ sortDesc ? 'Nieuwste eerst' : 'Oudste eerst' }}</span>
          </button>
        </div>

        <div
          v-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm mb-4"
          data-testid="error-banner"
        >
          {{ error }}
        </div>

        <!-- Loading -->
        <div v-if="loading && sessions.length === 0" class="flex flex-col gap-3">
          <div
            v-for="n in 4"
            :key="n"
            class="h-28 bg-surface-container-low rounded-xl animate-pulse"
          ></div>
        </div>

        <!-- Empty -->
        <div
          v-else-if="filteredSessions.length === 0"
          class="glass-panel p-12 text-center rounded-xl"
          data-testid="empty-state"
        >
          <h2 class="text-xl font-semibold text-on-surface mb-2">
            Geen PRs van deze student gevonden
          </h2>
          <p class="text-on-surface-variant">
            Er zijn geen pull requests die aan de huidige filters voldoen.
          </p>
        </div>

        <!-- PR grid -->
        <div v-else class="flex flex-col gap-3" data-testid="pr-list">
          <div
            v-for="s in filteredSessions"
            :key="s.session_id"
            @click="openSession(s.session_id, s.state)"
            :data-testid="`pr-card-${s.session_id}`"
            :class="[
              s.is_superseded ? 'opacity-60' : '',
              viewerIsStudent && !isVisibleToStudent(s.state)
                ? 'cursor-not-allowed'
                : 'cursor-pointer',
            ]"
          >
            <div v-if="s.iteration_number > 1 || s.is_superseded" class="flex items-center gap-2 mb-1">
              <span class="text-[11px] uppercase tracking-widest text-on-surface-variant">
                Iteratie {{ s.iteration_number }}
              </span>
              <span
                v-if="s.is_superseded"
                class="text-[10px] uppercase tracking-widest text-outline bg-surface-container rounded px-1.5 py-0.5"
              >vervangen</span>
            </div>

            <!-- Student-side wachten-op-feedback wrapper.
                 Visible "ja, je PR is binnen" affordance + locked card so
                 the student can't open the docent's draft mid-review. -->
            <div
              v-if="viewerIsStudent && !isVisibleToStudent(s.state)"
              class="relative pointer-events-none select-none"
            >
              <div class="opacity-50 grayscale">
                <PRCard
                  :pr-number="s.pr_number"
                  :pr-title="s.pr_title"
                  :repo-full-name="s.repo_full_name"
                  :state="s.state"
                  :submitted-at="s.submitted_at"
                  :graded-at="s.graded_at"
                  :rubric-score-avg="null"
                  :course-name="s.course_name"
                />
              </div>
              <div class="absolute inset-0 flex items-center justify-center">
                <div class="bg-surface-container-low border border-outline-variant/30 rounded-lg px-4 py-2 shadow-lg flex items-center gap-2">
                  <span class="material-symbols-outlined text-base text-primary">hourglass_empty</span>
                  <span class="text-xs font-semibold text-on-surface">
                    {{ studentBadgeLabel(s.state) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Default card (teacher view, or student's posted sessions). -->
            <PRCard
              v-else
              :pr-number="s.pr_number"
              :pr-title="s.pr_title"
              :repo-full-name="s.repo_full_name"
              :state="s.state"
              :submitted-at="s.submitted_at"
              :graded-at="s.graded_at"
              :rubric-score-avg="s.rubric_score_avg"
              :course-name="s.course_name"
            />
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
/**
 * StudentPRListView — /grading/students/:id/prs
 *
 * Intermediate view between the grading inbox (student browser) and the
 * session detail page. Uses the existing `/grading/students/:id/pr-history/`
 * endpoint (Workstream D). Backend enforces teacher permission — if the
 * teacher can't see this student we surface the 403/404 gracefully.
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';
import AppShell from '@/components/layout/AppShell.vue';
import PRCard from '@/components/grading/PRCard.vue';

interface StudentInfo {
  id: number;
  name: string;
  email: string;
  avatar_url?: string | null;
}
interface SessionEntry {
  session_id: number;
  submission_id: number;
  pr_number: number | null;
  pr_title: string;
  repo_full_name: string | null;
  submitted_at: string | null;
  graded_at: string | null;
  state: string;
  rubric_score_avg: number | null;
  findings_count: number;
  course_name: string | null;
  iteration_number: number;
  is_superseded: boolean;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { user } = storeToRefs(auth);

// Two routes mount this view:
//   /grading/students/:id/prs    (teacher viewing a student — admin meta)
//   /my/prs                      (student viewing their own — no :id param)
// Fall back to the authed user's own id when :id is absent.
const studentId = computed(() => {
  const fromRoute = Number(route.params.id);
  if (Number.isFinite(fromRoute) && fromRoute > 0) return fromRoute;
  return Number(user.value?.id ?? 0);
});

// True when the authed user is viewing their own PR list (the /my/prs route
// without a :id param). Teachers viewing a student via /grading/students/:id/prs
// see everything; students see only sessions a docent has actually sent.
//
// Student gate:
//   - Cards for non-`posted` sessions render in a disabled state with a
//     "Wachten op feedback van docent" badge — student knows LEERA noticed
//     their PR but hasn't received feedback yet.
//   - Clicking a non-`posted` card does nothing for students.
//   - The state filter chip strip is replaced with student-friendly labels.
//
// We deliberately don't hide the rows. The student should see "yes, my push
// arrived" — that's reassuring even when the docent hasn't reviewed yet.
const viewerIsStudent = computed(() => {
  const fromRoute = Number(route.params.id);
  return !Number.isFinite(fromRoute) || fromRoute <= 0;
});

const student = ref<StudentInfo | null>(null);
const sessions = ref<SessionEntry[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// Teachers see the full lifecycle. Students only see two buckets:
// "Wacht op feedback" (everything pre-posted) and "Feedback ontvangen" (posted).
// We don't expose the internal state machine to students — they don't need
// to know the difference between "drafted" and "reviewing".
const stateChips = computed<Array<{ label: string; value: string | null }>>(() => {
  if (viewerIsStudent.value) {
    return [
      { label: 'Alles', value: null },
      { label: 'Wacht op feedback', value: '__pending_for_student' },
      { label: 'Feedback ontvangen', value: 'posted' },
    ];
  }
  return [
    { label: 'Alles', value: null },
    { label: 'In afwachting', value: 'pending' },
    { label: 'Klaar voor review', value: 'drafted' },
    { label: 'Bezig met nakijken', value: 'reviewing' },
    { label: 'Verstuurd', value: 'posted' },
  ];
});
const selectedState = ref<string | null>(null);

// Student-side helpers.
function isVisibleToStudent(state: string): boolean {
  return state === 'posted';
}
function studentBadgeLabel(state: string): string {
  if (state === 'posted') return 'Feedback ontvangen';
  if (state === 'failed') return 'Probleem bij review — docent kijkt ernaar';
  return 'Wacht op feedback van docent';
}
const sortDesc = ref(true);

function toggleSort() {
  sortDesc.value = !sortDesc.value;
}

async function load() {
  if (!studentId.value) return;
  loading.value = true;
  error.value = null;
  try {
    const { data } = await api.grading.students.prHistory(studentId.value);
    student.value = data?.student || null;
    // Be tolerant of the payload shape: sessions may be at `.sessions` or
    // `.pr_history`, each entry exposes `session_id` or `id`.
    const raw: any[] = data?.sessions || data?.pr_history || [];
    sessions.value = raw.map((r: any) => ({
      session_id: r.session_id ?? r.id,
      submission_id: r.submission_id ?? r.submission ?? 0,
      pr_number: r.pr_number ?? null,
      pr_title: r.pr_title ?? '',
      repo_full_name: r.repo_full_name ?? null,
      submitted_at: r.submitted_at ?? null,
      graded_at: r.graded_at ?? null,
      state: r.state ?? 'pending',
      rubric_score_avg: r.rubric_score_avg ?? null,
      findings_count: r.findings_count ?? 0,
      course_name: r.course_name ?? null,
      iteration_number: r.iteration_number ?? 1,
      is_superseded: Boolean(r.is_superseded),
    }));
  } catch (err: any) {
    const status = err?.response?.status;
    if (status === 403) {
      error.value = 'Je hebt geen toegang tot deze student.';
    } else if (status === 404) {
      error.value = 'Student niet gevonden.';
    } else {
      error.value =
        err?.response?.data?.detail || err?.message || 'Kon PRs niet laden';
    }
    sessions.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(studentId, load);

const filteredSessions = computed(() => {
  let list = sessions.value.slice();
  if (selectedState.value) {
    if (selectedState.value === '__pending_for_student') {
      // Student-side virtual filter: everything that's NOT posted yet.
      list = list.filter(s => !isVisibleToStudent(s.state));
    } else {
      list = list.filter(s => s.state === selectedState.value);
    }
  }
  list.sort((a, b) => {
    const at = a.submitted_at ? new Date(a.submitted_at).getTime() : 0;
    const bt = b.submitted_at ? new Date(b.submitted_at).getTime() : 0;
    return sortDesc.value ? bt - at : at - bt;
  });
  return list;
});

function goBack() {
  router.push({ name: 'grading-inbox' });
}

function openSession(sessionId: number, state: string) {
  // Students can only open sessions a docent has sent. Pre-`posted` sessions
  // are visible (so they can see "ja, mijn push is binnengekomen") but
  // non-clickable — clicking a "wacht op feedback" card does nothing.
  if (viewerIsStudent.value && !isVisibleToStudent(state)) return;
  router.push({ name: 'grading-session-detail', params: { id: sessionId } });
}
</script>
