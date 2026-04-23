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
            :key="s.id"
            @click="openSession(s.id)"
            :data-testid="`pr-card-${s.id}`"
          >
            <PRCard
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
import { api } from '@/composables/useApi';
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
}

const route = useRoute();
const router = useRouter();

const studentId = computed(() => Number(route.params.id));

const student = ref<StudentInfo | null>(null);
const sessions = ref<SessionEntry[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const stateChips: Array<{ label: string; value: string | null }> = [
  { label: 'Alles', value: null },
  { label: 'In afwachting', value: 'pending' },
  { label: 'Klaar voor review', value: 'drafted' },
  { label: 'Bezig met nakijken', value: 'reviewing' },
  { label: 'Verstuurd', value: 'posted' },
];
const selectedState = ref<string | null>(null);
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
    list = list.filter(s => s.state === selectedState.value);
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

function openSession(sessionId: number) {
  router.push({ name: 'grading-session-detail', params: { id: sessionId } });
}
</script>
