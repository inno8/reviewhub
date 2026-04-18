/**
 * Smoke tests for the grading Pinia store.
 *
 * Covers the critical flows the Vue views rely on:
 *   - inbox list unwraps DRF pagination + computed counts
 *   - send flow maps HTTP status codes to the right result shape
 *     (200 → ok, 207 → partial, 401 → github_auth, 409 → pr_closed, 502 → github_failed)
 *
 * The `api` client is mocked out — no Django required.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

vi.mock('@/composables/useApi', () => {
  const listMock = vi.fn();
  const getMock = vi.fn();
  const sendMock = vi.fn();
  const resumeMock = vi.fn();
  const startReviewMock = vi.fn();
  const generateDraftMock = vi.fn();
  const updateMock = vi.fn();
  const classroomsListMock = vi.fn();
  const rubricsListMock = vi.fn();

  return {
    api: {
      grading: {
        rubrics: { list: rubricsListMock },
        classrooms: { list: classroomsListMock },
        sessions: {
          list: listMock,
          get: getMock,
          update: updateMock,
          startReview: startReviewMock,
          generateDraft: generateDraftMock,
          send: sendMock,
          resume: resumeMock,
        },
        submissions: { list: vi.fn() },
        costLogs: { list: vi.fn() },
      },
    },
    // expose for direct access in tests
    __mocks: {
      listMock, getMock, sendMock, resumeMock, startReviewMock,
      generateDraftMock, updateMock, classroomsListMock, rubricsListMock,
    },
  };
});

import { useGradingStore } from '@/stores/grading';
import * as apiModule from '@/composables/useApi';

// Helper to access the internal mocks.
const mocks = (apiModule as any).__mocks as {
  listMock: any;
  getMock: any;
  sendMock: any;
  resumeMock: any;
  startReviewMock: any;
  generateDraftMock: any;
  updateMock: any;
  classroomsListMock: any;
  rubricsListMock: any;
};

beforeEach(() => {
  setActivePinia(createPinia());
  for (const m of Object.values(mocks)) m.mockReset();
});

// ─────────────────────────────────────────────────────────────────────────────
// Inbox list
// ─────────────────────────────────────────────────────────────────────────────
describe('inbox list', () => {
  it('unwraps DRF paginated {results} shape', async () => {
    mocks.listMock.mockResolvedValue({
      data: {
        count: 2,
        results: [
          { id: 1, state: 'drafted', student_email: 'a@ex.com', due_at: null },
          { id: 2, state: 'posted', student_email: 'b@ex.com', due_at: null },
        ],
      },
    });
    const store = useGradingStore();
    await store.fetchSessions();
    expect(store.sessions).toHaveLength(2);
    expect(store.sessions[0].id).toBe(1);
  });

  it('accepts bare arrays (non-paginated endpoints)', async () => {
    mocks.listMock.mockResolvedValue({
      data: [{ id: 5, state: 'drafted', student_email: 'x@ex.com', due_at: null }],
    });
    const store = useGradingStore();
    await store.fetchSessions();
    expect(store.sessions).toHaveLength(1);
  });

  it('computes pendingCount from the three actionable states', async () => {
    mocks.listMock.mockResolvedValue({
      data: {
        results: [
          { id: 1, state: 'pending', due_at: null },
          { id: 2, state: 'drafted', due_at: null },
          { id: 3, state: 'reviewing', due_at: null },
          { id: 4, state: 'posted', due_at: null },
          { id: 5, state: 'failed', due_at: null },
        ],
      },
    });
    const store = useGradingStore();
    await store.fetchSessions();
    expect(store.pendingCount).toBe(3);
  });

  it('computes overdueCount only for non-terminal sessions past due_at', async () => {
    const past = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    const future = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    mocks.listMock.mockResolvedValue({
      data: {
        results: [
          { id: 1, state: 'drafted', due_at: past },   // overdue
          { id: 2, state: 'reviewing', due_at: past }, // overdue
          { id: 3, state: 'posted', due_at: past },    // NOT overdue (already posted)
          { id: 4, state: 'drafted', due_at: future }, // NOT overdue (still future)
          { id: 5, state: 'drafted', due_at: null },   // NOT overdue (no deadline)
        ],
      },
    });
    const store = useGradingStore();
    await store.fetchSessions();
    expect(store.overdueCount).toBe(2);
  });

  it('captures the error message and empties the list on API failure', async () => {
    mocks.listMock.mockRejectedValue({
      response: { data: { detail: 'forbidden' } },
    });
    const store = useGradingStore();
    await store.fetchSessions();
    expect(store.sessionsError).toBe('forbidden');
    expect(store.sessions).toEqual([]);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Send flow — HTTP status → result shape mapping
// ─────────────────────────────────────────────────────────────────────────────
describe('send', () => {
  it('returns ok on 200', async () => {
    mocks.sendMock.mockResolvedValue({
      data: { state: 'posted', posted_count: 3, skipped_duplicate_count: 0 },
    });
    mocks.getMock.mockResolvedValue({
      data: {
        id: 1, state: 'posted', rubric_snapshot: { criteria: [] },
        ai_draft_scores: {}, ai_draft_comments: [], final_scores: {},
        final_comments: [], final_summary: '', posted_comments: [],
      },
    });
    const store = useGradingStore();
    const result = await store.send(1);
    expect(result.ok).toBe(true);
    expect(result.summary.posted_count).toBe(3);
    expect(result.sessionState).toBe('posted');
  });

  it('returns partial on 207', async () => {
    mocks.sendMock.mockRejectedValue({
      response: {
        status: 207,
        data: {
          error: 'partial_post',
          state: 'partial',
          failed_at_comment_idx: 2,
          posted_so_far: 1,
        },
      },
    });
    mocks.getMock.mockResolvedValue({
      data: {
        id: 1, state: 'partial', rubric_snapshot: { criteria: [] },
        ai_draft_scores: {}, ai_draft_comments: [], final_scores: {},
        final_comments: [], final_summary: '', posted_comments: [],
      },
    });
    const store = useGradingStore();
    const result = await store.send(1);
    expect(result.ok).toBe(false);
    expect(result.kind).toBe('partial');
    expect(result.posted_so_far).toBe(1);
  });

  it('maps 401 → github_auth', async () => {
    mocks.sendMock.mockRejectedValue({
      response: { status: 401, data: { error: 'github_auth', message: 'reauth' } },
    });
    const store = useGradingStore();
    const result = await store.send(1);
    expect(result.ok).toBe(false);
    expect(result.kind).toBe('github_auth');
  });

  it('maps 409 → pr_closed', async () => {
    mocks.sendMock.mockRejectedValue({
      response: { status: 409, data: { error: 'pr_closed', message: 'closed' } },
    });
    const store = useGradingStore();
    const result = await store.send(1);
    expect(result.ok).toBe(false);
    expect(result.kind).toBe('pr_closed');
  });

  it('maps 502 → github_failed', async () => {
    mocks.sendMock.mockRejectedValue({
      response: { status: 502, data: { error: 'github_failed', message: 'upstream' } },
    });
    const store = useGradingStore();
    const result = await store.send(1);
    expect(result.ok).toBe(false);
    expect(result.kind).toBe('github_failed');
  });

  it('falls back to network kind on no response', async () => {
    mocks.sendMock.mockRejectedValue(new Error('offline'));
    const store = useGradingStore();
    const result = await store.send(1);
    expect(result.ok).toBe(false);
    expect(result.kind).toBe('network');
  });
});

describe('resume', () => {
  it('returns ok on 200', async () => {
    mocks.resumeMock.mockResolvedValue({
      data: { state: 'posted', posted_count: 2, skipped_duplicate_count: 1 },
    });
    mocks.getMock.mockResolvedValue({
      data: {
        id: 1, state: 'posted', rubric_snapshot: { criteria: [] },
        ai_draft_scores: {}, ai_draft_comments: [], final_scores: {},
        final_comments: [], final_summary: '', posted_comments: [],
      },
    });
    const store = useGradingStore();
    const result = await store.resume(1);
    expect(result.ok).toBe(true);
    expect(result.summary.posted_count).toBe(2);
    expect(result.summary.skipped_duplicate_count).toBe(1);
  });
});
