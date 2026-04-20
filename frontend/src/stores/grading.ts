/**
 * Pinia store for Nakijken Copilot.
 *
 * Lean design for v1: this store holds the inbox list + the currently
 * opened session + the pending edits. The session detail view is the
 * only place that mutates heavily (edit comments, click Send).
 *
 * Keeps API response shapes close to Django's DRF output. We unwrap the
 * {results, count, next, previous} pagination shape so components see
 * plain arrays.
 */
import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/composables/useApi';

export type SessionState =
  | 'pending'
  | 'drafting'
  | 'drafted'
  | 'reviewing'
  | 'sending'
  | 'posted'
  | 'partial'
  | 'failed'
  | 'discarded';

export interface GradingComment {
  file: string;
  line: number;
  body: string;
}

export interface SessionListRow {
  id: number;
  state: SessionState;
  student_email: string;
  student_name: string;
  course_id: number;
  course_name: string;
  pr_url: string;
  pr_title: string;
  due_at: string | null;
  ai_draft_generated_at: string | null;
  posted_at: string | null;
  docent_review_time_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface RubricCriterion {
  id: string;
  name: string;
  weight?: number;
  levels: Array<{ score: number; description?: string }>;
}

export interface SessionDetail extends SessionListRow {
  rubric: number;
  rubric_snapshot: {
    id: number;
    name: string;
    criteria: RubricCriterion[];
    calibration: Record<string, unknown>;
  };
  ai_draft_scores: Record<string, { score: number; evidence?: string }>;
  ai_draft_comments: GradingComment[];
  ai_draft_model: string;
  ai_draft_truncated: boolean;
  final_scores: Record<string, { score: number; evidence?: string }>;
  final_comments: GradingComment[];
  final_summary: string;
  docent_review_started_at: string | null;
  sending_started_at: string | null;
  partial_post_error: Record<string, unknown> | null;
  posted_comments: Array<{
    id: number;
    client_mutation_id: string;
    github_comment_id: number | null;
    file_path: string;
    line_number: number;
    body_preview: string;
    posted_at: string;
  }>;
}

export interface Course {
  id: number;
  name: string;
  owner: number;
  owner_email: string;
  rubric: number | null;
  rubric_name: string | null;
  student_count: number;
  target_branch_pattern: string;
  source_control_type: string;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Rubric {
  id: number;
  name: string;
  org: number | null;
  is_template: boolean;
  criteria: RubricCriterion[];
  calibration: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

function unwrapPage<T>(data: any): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as T[];
  if (Array.isArray(data.results)) return data.results as T[];
  return [];
}

export const useGradingStore = defineStore('grading', () => {
  // ── state ─────────────────────────────────────────────────────────────
  const sessions = ref<SessionListRow[]>([]);
  const sessionsLoading = ref(false);
  const sessionsError = ref<string | null>(null);

  const activeSession = ref<SessionDetail | null>(null);
  const activeSessionLoading = ref(false);
  const activeSessionError = ref<string | null>(null);

  const courses = ref<Course[]>([]);
  const rubrics = ref<Rubric[]>([]);

  const filters = ref({
    course: undefined as number | undefined,
    state: undefined as SessionState | undefined,
    overdue: false,
  });

  // ── computed ──────────────────────────────────────────────────────────
  const pendingCount = computed(
    () => sessions.value.filter(s => ['pending', 'drafted', 'reviewing'].includes(s.state)).length,
  );
  const overdueCount = computed(() => {
    const now = Date.now();
    return sessions.value.filter(s =>
      s.due_at &&
      new Date(s.due_at).getTime() < now &&
      !['posted', 'discarded'].includes(s.state),
    ).length;
  });

  // ── inbox ─────────────────────────────────────────────────────────────
  async function fetchSessions() {
    sessionsLoading.value = true;
    sessionsError.value = null;
    try {
      const params: Record<string, unknown> = {};
      if (filters.value.course) params.course = filters.value.course;
      if (filters.value.state) params.state = filters.value.state;
      if (filters.value.overdue) params.overdue = 'true';
      const { data } = await api.grading.sessions.list(params);
      sessions.value = unwrapPage<SessionListRow>(data);
    } catch (err: any) {
      sessionsError.value = err?.response?.data?.detail || err.message || 'Failed to load sessions';
      sessions.value = [];
    } finally {
      sessionsLoading.value = false;
    }
  }

  function setFilters(next: Partial<typeof filters.value>) {
    filters.value = { ...filters.value, ...next };
  }

  // ── session detail ────────────────────────────────────────────────────
  async function fetchSession(id: number) {
    activeSessionLoading.value = true;
    activeSessionError.value = null;
    try {
      const { data } = await api.grading.sessions.get(id);
      activeSession.value = data;
    } catch (err: any) {
      activeSessionError.value = err?.response?.data?.detail || err.message || 'Failed to load';
      activeSession.value = null;
    } finally {
      activeSessionLoading.value = false;
    }
  }

  async function startReview(id: number) {
    const { data } = await api.grading.sessions.startReview(id);
    if (activeSession.value && activeSession.value.id === id) activeSession.value = data;
    return data;
  }

  async function generateDraft(id: number) {
    const { data } = await api.grading.sessions.generateDraft(id);
    if (activeSession.value && activeSession.value.id === id) activeSession.value = data;
    return data;
  }

  /**
   * Persist in-flight edits to the server. Called on autosave + before Send.
   * Only sends the docent-editable fields.
   */
  async function saveEdits(
    id: number,
    patch: Partial<Pick<SessionDetail, 'final_scores' | 'final_comments' | 'final_summary'>>,
  ) {
    const { data } = await api.grading.sessions.update(id, patch);
    if (activeSession.value && activeSession.value.id === id) {
      activeSession.value = { ...activeSession.value, ...data };
    }
    return data;
  }

  /**
   * Send. Returns one of:
   *   { ok: true, summary, sessionState: 'posted' }
   *   { ok: false, kind: 'partial', postedSoFar, sessionState: 'partial' }
   *   { ok: false, kind: 'pr_closed' | 'github_auth' | 'github_failed', message }
   */
  async function send(id: number): Promise<any> {
    try {
      const { data } = await api.grading.sessions.send(id);
      // Refresh detail to pull fresh state.
      await fetchSession(id);
      return { ok: true, summary: data, sessionState: data.state };
    } catch (err: any) {
      const resp = err?.response;
      if (!resp) return { ok: false, kind: 'network', message: err?.message };
      if (resp.status === 207) {
        await fetchSession(id);
        return { ok: false, kind: 'partial', ...resp.data };
      }
      if (resp.status === 409) return { ok: false, kind: 'pr_closed', ...resp.data };
      if (resp.status === 401) return { ok: false, kind: 'github_auth', ...resp.data };
      return { ok: false, kind: 'github_failed', ...resp.data };
    }
  }

  async function resume(id: number): Promise<any> {
    try {
      const { data } = await api.grading.sessions.resume(id);
      await fetchSession(id);
      return { ok: true, summary: data, sessionState: data.state };
    } catch (err: any) {
      const resp = err?.response;
      if (!resp) return { ok: false, kind: 'network', message: err?.message };
      if (resp.status === 207) {
        await fetchSession(id);
        return { ok: false, kind: 'partial', ...resp.data };
      }
      return { ok: false, kind: 'github_failed', ...resp.data };
    }
  }

  // ── courses / rubrics (read-only for v1 UI) ───────────────────────────
  async function fetchCourses() {
    const { data } = await api.grading.courses.list();
    courses.value = unwrapPage<Course>(data);
  }

  async function fetchRubrics() {
    const { data } = await api.grading.rubrics.list();
    rubrics.value = unwrapPage<Rubric>(data);
  }

  function reset() {
    sessions.value = [];
    activeSession.value = null;
    courses.value = [];
    rubrics.value = [];
    filters.value = { course: undefined, state: undefined, overdue: false };
  }

  return {
    // state
    sessions,
    sessionsLoading,
    sessionsError,
    activeSession,
    activeSessionLoading,
    activeSessionError,
    courses,
    rubrics,
    filters,
    // computed
    pendingCount,
    overdueCount,
    // actions
    fetchSessions,
    setFilters,
    fetchSession,
    startReview,
    generateDraft,
    saveEdits,
    send,
    resume,
    fetchCourses,
    fetchRubrics,
    reset,
  };
});
