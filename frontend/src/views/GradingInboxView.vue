<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <header class="flex flex-wrap gap-4 justify-between items-end mb-8">
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">Grading Inbox</h1>
            <p class="text-sm text-on-surface-variant mt-2">
              <span v-if="store.overdueCount > 0" class="text-error font-semibold">
                {{ store.overdueCount }} overdue
              </span>
              <span v-if="store.overdueCount > 0" class="opacity-50 mx-1">·</span>
              <span>{{ store.pendingCount }} to grade</span>
            </p>
          </div>
          <button
            @click="refresh"
            :disabled="store.sessionsLoading"
            class="bg-surface-container hover:bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-medium border border-outline-variant/20 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            data-testid="refresh-btn"
          >
            <span v-if="store.sessionsLoading">Loading…</span>
            <span v-else>Refresh</span>
          </button>
        </header>

        <div
          class="flex flex-wrap gap-4 items-center px-4 py-3 bg-surface-container-low border border-outline-variant/10 rounded-xl mb-4"
        >
          <label class="flex flex-col text-xs text-on-surface-variant">
            <span class="mb-1 uppercase tracking-widest font-semibold">Course</span>
            <select
              v-model="selectedCourse"
              @change="onFilterChange"
              class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1.5 px-2 min-w-[180px] focus:ring-1 focus:ring-primary/50 focus:outline-none"
              data-testid="filter-course"
            >
              <option :value="undefined">All courses</option>
              <option v-for="c in store.courses" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </label>

          <label class="flex flex-col text-xs text-on-surface-variant">
            <span class="mb-1 uppercase tracking-widest font-semibold">State</span>
            <select
              v-model="selectedState"
              @change="onFilterChange"
              class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1.5 px-2 min-w-[180px] focus:ring-1 focus:ring-primary/50 focus:outline-none"
              data-testid="filter-state"
            >
              <option :value="undefined">All states</option>
              <option value="pending">Pending</option>
              <option value="drafted">Draft ready</option>
              <option value="reviewing">In review</option>
              <option value="partial">Partial post</option>
              <option value="posted">Posted</option>
              <option value="failed">Failed</option>
            </select>
          </label>

          <label class="flex items-center gap-2 text-sm text-on-surface cursor-pointer mt-4">
            <input
              type="checkbox"
              v-model="overdueOnly"
              @change="onFilterChange"
              class="h-4 w-4 rounded border-outline-variant bg-surface-container text-primary"
              data-testid="filter-overdue"
            />
            <span>Overdue only</span>
          </label>
        </div>

        <div
          v-if="store.sessionsError"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm mb-4"
          data-testid="error-banner"
        >
          {{ store.sessionsError }}
        </div>

        <div v-if="store.sessionsLoading && store.sessions.length === 0" class="flex flex-col gap-2">
          <div
            v-for="n in 5"
            :key="n"
            class="h-16 bg-surface-container-low rounded-xl animate-pulse"
          ></div>
        </div>

        <div
          v-else-if="store.sessions.length === 0"
          class="glass-panel p-12 text-center rounded-xl"
          data-testid="empty-state"
        >
          <h2 class="text-xl font-semibold text-on-surface mb-2">All caught up.</h2>
          <p class="text-on-surface-variant">Close the laptop. You earned it.</p>
        </div>

        <ul v-else class="flex flex-col gap-2 list-none p-0 m-0" data-testid="session-list">
          <li
            v-for="s in store.sessions"
            :key="s.id"
            class="flex items-center justify-between px-5 py-4 bg-surface-container-low border border-outline-variant/10 rounded-xl cursor-pointer hover:border-primary/40 hover:bg-surface-container transition-colors"
            :class="sessionRowClass(s)"
            @click="openSession(s.id)"
            :data-testid="`session-row-${s.id}`"
          >
            <div class="flex-1 min-w-0">
              <div class="flex gap-3 items-baseline mb-1">
                <span class="font-semibold text-on-surface">{{ s.student_name || s.student_email }}</span>
                <span class="text-on-surface-variant text-sm truncate">{{ s.pr_title || 'Untitled PR' }}</span>
              </div>
              <div class="text-xs text-on-surface-variant flex gap-2 items-center flex-wrap">
                <span>{{ s.course_name }}</span>
                <span class="opacity-50">·</span>
                <span
                  class="px-2 py-0.5 rounded-md text-[10px] uppercase tracking-widest font-semibold"
                  :class="stateBadgeClass(s.state)"
                >
                  {{ stateLabel(s.state) }}
                </span>
                <span v-if="s.due_at" class="opacity-50">·</span>
                <span v-if="s.due_at" :class="{ 'text-error font-semibold': isOverdue(s) }">
                  {{ formatDue(s.due_at) }}
                </span>
              </div>
            </div>
            <div class="shrink-0">
              <span class="text-primary font-medium text-sm whitespace-nowrap">Review →</span>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useGradingStore, type SessionState, type SessionListRow } from '@/stores/grading';
import AppShell from '@/components/layout/AppShell.vue';

const router = useRouter();
const store = useGradingStore();

const selectedCourse = ref<number | undefined>(undefined);
const selectedState = ref<SessionState | undefined>(undefined);
const overdueOnly = ref(false);

onMounted(async () => {
  await Promise.all([store.fetchCourses(), store.fetchSessions()]);
});

function onFilterChange() {
  store.setFilters({
    course: selectedCourse.value,
    state: selectedState.value,
    overdue: overdueOnly.value,
  });
  store.fetchSessions();
}

function refresh() {
  store.fetchSessions();
}

function openSession(id: number) {
  router.push({ name: 'grading-session-detail', params: { id } });
}

function stateLabel(state: SessionState): string {
  const labels: Record<SessionState, string> = {
    pending: 'Pending',
    drafting: 'Drafting…',
    drafted: 'Ready to review',
    reviewing: 'In review',
    sending: 'Sending…',
    posted: 'Posted',
    partial: 'Needs resume',
    failed: 'Failed',
    discarded: 'Discarded',
  };
  return labels[state] || state;
}

function stateBadgeClass(state: SessionState): string {
  // Stitch-palette severity badges
  switch (state) {
    case 'drafted':
      return 'bg-primary/15 text-primary';
    case 'reviewing':
      return 'bg-tertiary/20 text-tertiary';
    case 'posted':
      return 'bg-primary-container/15 text-primary-container';
    case 'partial':
      return 'bg-tertiary/20 text-tertiary';
    case 'failed':
      return 'bg-error/15 text-error';
    default:
      return 'bg-surface-container text-on-surface-variant';
  }
}

function sessionRowClass(s: SessionListRow) {
  const classes: string[] = [];
  if (['drafted', 'reviewing', 'partial'].includes(s.state)) {
    classes.push('border-l-[3px] !border-l-primary');
  }
  if (s.state === 'posted') {
    classes.push('opacity-70');
  }
  if (s.state === 'failed' || isOverdue(s)) {
    classes.push('border-l-[3px] !border-l-error');
  }
  return classes.join(' ');
}

function isOverdue(s: SessionListRow): boolean {
  return !!(
    s.due_at &&
    new Date(s.due_at).getTime() < Date.now() &&
    !['posted', 'discarded'].includes(s.state)
  );
}

function formatDue(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diffMs = d.getTime() - now;
  const diffHours = Math.round(diffMs / (1000 * 60 * 60));
  if (diffHours < -24) return `Overdue ${Math.abs(Math.round(diffHours / 24))}d`;
  if (diffHours < 0) return `Overdue ${Math.abs(diffHours)}h`;
  if (diffHours < 24) return `Due in ${diffHours}h`;
  return `Due ${d.toLocaleDateString()}`;
}
</script>
