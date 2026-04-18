<template>
  <div class="grading-inbox">
    <header class="inbox-header">
      <div>
        <h1 class="text-2xl font-semibold text-slate-100">Grading Inbox</h1>
        <p class="text-sm text-slate-400 mt-1">
          <span v-if="store.overdueCount > 0" class="text-red-400 font-medium">
            {{ store.overdueCount }} overdue
          </span>
          <span v-if="store.overdueCount > 0">·</span>
          <span>{{ store.pendingCount }} to grade</span>
        </p>
      </div>
      <button
        @click="refresh"
        :disabled="store.sessionsLoading"
        class="btn-secondary"
        data-testid="refresh-btn"
      >
        <span v-if="store.sessionsLoading">Loading…</span>
        <span v-else>Refresh</span>
      </button>
    </header>

    <div class="filters">
      <label class="filter">
        <span class="filter-label">Classroom</span>
        <select
          v-model="selectedClassroom"
          @change="onFilterChange"
          class="filter-select"
          data-testid="filter-classroom"
        >
          <option :value="undefined">All classrooms</option>
          <option v-for="c in store.classrooms" :key="c.id" :value="c.id">
            {{ c.name }}
          </option>
        </select>
      </label>

      <label class="filter">
        <span class="filter-label">State</span>
        <select
          v-model="selectedState"
          @change="onFilterChange"
          class="filter-select"
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

      <label class="filter checkbox">
        <input
          type="checkbox"
          v-model="overdueOnly"
          @change="onFilterChange"
          data-testid="filter-overdue"
        />
        <span>Overdue only</span>
      </label>
    </div>

    <div v-if="store.sessionsError" class="error-banner" data-testid="error-banner">
      {{ store.sessionsError }}
    </div>

    <div v-if="store.sessionsLoading && store.sessions.length === 0" class="skeleton-list">
      <div class="skeleton-row" v-for="n in 5" :key="n"></div>
    </div>

    <div
      v-else-if="store.sessions.length === 0"
      class="empty-state"
      data-testid="empty-state"
    >
      <h2>All caught up.</h2>
      <p>Close the laptop. You earned it.</p>
    </div>

    <ul v-else class="session-list" data-testid="session-list">
      <li
        v-for="s in store.sessions"
        :key="s.id"
        class="session-row"
        :class="stateClass(s)"
        @click="openSession(s.id)"
        :data-testid="`session-row-${s.id}`"
      >
        <div class="session-row-main">
          <div class="session-title">
            <span class="student-name">{{ s.student_name || s.student_email }}</span>
            <span class="pr-title">{{ s.pr_title || 'Untitled PR' }}</span>
          </div>
          <div class="session-meta">
            <span class="classroom">{{ s.classroom_name }}</span>
            <span class="separator">·</span>
            <span class="state-badge" :class="`state-${s.state}`">{{ stateLabel(s.state) }}</span>
            <span v-if="s.due_at" class="separator">·</span>
            <span v-if="s.due_at" :class="{ 'due-overdue': isOverdue(s) }">
              {{ formatDue(s.due_at) }}
            </span>
          </div>
        </div>
        <div class="session-row-cta">
          <span class="action-hint">Review →</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useGradingStore, type SessionState, type SessionListRow } from '@/stores/grading';

const router = useRouter();
const store = useGradingStore();

const selectedClassroom = ref<number | undefined>(undefined);
const selectedState = ref<SessionState | undefined>(undefined);
const overdueOnly = ref(false);

onMounted(async () => {
  await Promise.all([store.fetchClassrooms(), store.fetchSessions()]);
});

function onFilterChange() {
  store.setFilters({
    classroom: selectedClassroom.value,
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

function stateClass(s: SessionListRow) {
  return {
    'state-actionable': ['drafted', 'reviewing', 'partial'].includes(s.state),
    'state-posted': s.state === 'posted',
    'state-failed': s.state === 'failed',
    'is-overdue': isOverdue(s),
  };
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

<style scoped>
.grading-inbox {
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.inbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.filters {
  display: flex;
  gap: 1rem;
  align-items: center;
  flex-wrap: wrap;
  padding: 0.75rem 1rem;
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.filter {
  display: flex;
  flex-direction: column;
  font-size: 0.75rem;
  color: rgb(148 163 184);
}

.filter.checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: rgb(226 232 240);
  margin-top: 1rem;
}

.filter-label {
  margin-bottom: 0.25rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.filter-select {
  background: rgb(30 41 59);
  border: 1px solid rgb(51 65 85);
  color: rgb(226 232 240);
  padding: 0.4rem 0.6rem;
  border-radius: 0.375rem;
  min-width: 180px;
}

.btn-secondary {
  background: rgb(30 41 59);
  border: 1px solid rgb(71 85 105);
  color: rgb(226 232 240);
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.btn-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-banner {
  background: rgb(127 29 29);
  border: 1px solid rgb(185 28 28);
  color: rgb(254 226 226);
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
  color: rgb(148 163 184);
}

.empty-state h2 {
  font-size: 1.25rem;
  color: rgb(226 232 240);
  margin-bottom: 0.5rem;
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.skeleton-row {
  height: 4rem;
  background: rgb(30 41 59);
  border-radius: 0.5rem;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.session-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.session-row:hover {
  background: rgb(22 30 48);
  border-color: rgb(51 65 85);
}

.session-row.state-actionable {
  border-left: 3px solid rgb(99 102 241);
}

.session-row.state-posted {
  opacity: 0.7;
}

.session-row.state-failed {
  border-left: 3px solid rgb(239 68 68);
}

.session-row.is-overdue {
  border-left: 3px solid rgb(239 68 68);
}

.session-row-main {
  flex: 1;
  min-width: 0;
}

.session-title {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
  margin-bottom: 0.25rem;
}

.student-name {
  font-weight: 600;
  color: rgb(226 232 240);
}

.pr-title {
  color: rgb(148 163 184);
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  font-size: 0.8rem;
  color: rgb(148 163 184);
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.separator {
  opacity: 0.5;
}

.state-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}

.state-badge.state-drafted { background: rgb(59 130 246 / 0.2); color: rgb(147 197 253); }
.state-badge.state-reviewing { background: rgb(234 179 8 / 0.2); color: rgb(253 224 71); }
.state-badge.state-posted { background: rgb(34 197 94 / 0.2); color: rgb(134 239 172); }
.state-badge.state-partial { background: rgb(249 115 22 / 0.2); color: rgb(253 186 116); }
.state-badge.state-failed { background: rgb(239 68 68 / 0.2); color: rgb(252 165 165); }

.due-overdue {
  color: rgb(248 113 113);
  font-weight: 600;
}

.action-hint {
  color: rgb(99 102 241);
  font-weight: 500;
  font-size: 0.875rem;
  white-space: nowrap;
}
</style>
