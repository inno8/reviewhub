/**
 * Smoke tests for GradingSessionDetailView.vue.
 *
 * The highest-risk UX guarantees this view makes (per eng review):
 *   1. Double-click Send → single API call (no double-post)
 *   2. Autosave + Send serialize correctly (dirty edits flush before Send)
 *   3. Partial-post banner renders with Resume button
 *   4. Generate-draft button appears when no draft exists
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/composables/useApi', () => {
  const m = {
    sessionsList: vi.fn(),
    coursesList: vi.fn(),
    rubricsList: vi.fn(),
    get: vi.fn(),
    update: vi.fn(),
    startReview: vi.fn(),
    generateDraft: vi.fn(),
    send: vi.fn(),
    resume: vi.fn(),
  };
  return {
    api: {
      grading: {
        rubrics: { list: m.rubricsList },
        courses: { list: m.coursesList },
        sessions: {
          list: m.sessionsList,
          get: m.get,
          update: m.update,
          startReview: m.startReview,
          generateDraft: m.generateDraft,
          send: m.send,
          resume: m.resume,
        },
        submissions: { list: vi.fn() },
        costLogs: { list: vi.fn() },
      },
    },
    __mocks: m,
  };
});

const push = vi.fn();
vi.mock('vue-router', async () => {
  const actual = await vi.importActual<any>('vue-router');
  return {
    ...actual,
    useRouter: () => ({ push }),
    useRoute: () => ({ params: { id: '42' } }),
    onBeforeRouteLeave: () => { /* no-op in tests */ },
  };
});

import GradingSessionDetailView from '@/views/GradingSessionDetailView.vue';
import * as apiModule from '@/composables/useApi';

const mocks = (apiModule as any).__mocks;

function draftedSession(overrides: Record<string, any> = {}) {
  return {
    id: 42,
    state: 'drafted',
    student_email: 'jan@ex.com',
    student_name: 'Jan de Boer',
    course_name: 'MBO-4 ICT',
    pr_url: 'https://github.com/jan/repo/pull/1',
    pr_title: 'Fix null handling',
    rubric: 7,
    rubric_snapshot: {
      id: 7,
      name: 'Standard',
      criteria: [
        {
          id: 'readability',
          name: 'Readability',
          weight: 1,
          levels: [
            { score: 1, description: 'bad' },
            { score: 4, description: 'good' },
          ],
        },
      ],
      calibration: {},
    },
    ai_draft_scores: { readability: { score: 3, evidence: 'clean diff' } },
    ai_draft_comments: [
      { file: 'src/a.py', line: 10, body: 'Good fix, consider an edge case.' },
    ],
    ai_draft_model: 'claude-sonnet-4.5',
    ai_draft_generated_at: '2026-04-17T18:00:00Z',
    ai_draft_truncated: false,
    final_scores: {},
    final_comments: [],
    final_summary: '',
    docent_review_started_at: null,
    docent_review_time_seconds: null,
    sending_started_at: null,
    posted_at: null,
    partial_post_error: null,
    posted_comments: [],
    ...overrides,
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  push.mockReset();
  for (const m of Object.values(mocks)) (m as any).mockReset();
});

describe('GradingSessionDetailView', () => {
  it('renders AI draft scores + comments when loaded', async () => {
    mocks.get.mockResolvedValue({ data: draftedSession() });
    mocks.startReview.mockResolvedValue({
      data: { ...draftedSession(), state: 'reviewing' },
    });
    const wrapper = mount(GradingSessionDetailView);
    await flushPromises();
    expect(wrapper.find('[data-testid="score-readability"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="comment-0"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Jan de Boer');
  });

  it('auto-starts review (state drafted → reviewing) on mount', async () => {
    mocks.get.mockResolvedValue({ data: draftedSession() });
    mocks.startReview.mockResolvedValue({
      data: { ...draftedSession(), state: 'reviewing' },
    });
    mount(GradingSessionDetailView);
    await flushPromises();
    expect(mocks.startReview).toHaveBeenCalledWith(42);
  });

  it('double-click Send fires exactly ONE API call (idempotency)', async () => {
    mocks.get.mockResolvedValue({ data: draftedSession() });
    mocks.startReview.mockResolvedValue({
      data: { ...draftedSession(), state: 'reviewing' },
    });
    // Send returns slowly so rapid clicks would hit the 2nd if not guarded
    let sendResolver: ((v: any) => void) | null = null;
    mocks.send.mockImplementation(
      () =>
        new Promise((resolve) => {
          sendResolver = resolve;
        }),
    );

    const wrapper = mount(GradingSessionDetailView);
    await flushPromises();

    const sendBtn = wrapper.find('[data-testid="send-btn"]');
    expect(sendBtn.exists()).toBe(true);
    // First click: kicks off in-flight send
    await sendBtn.trigger('click');
    // Second click: should be ignored (button is :disabled while sendInFlight)
    await sendBtn.trigger('click');
    await sendBtn.trigger('click');

    // Resolve the pending send so the test finishes cleanly
    sendResolver!({
      data: { state: 'posted', posted_count: 1, skipped_duplicate_count: 0 },
    });
    await flushPromises();

    // ONE and only one API call regardless of click count
    expect(mocks.send).toHaveBeenCalledTimes(1);
  });

  it('renders Resume button (not Send) when state=partial', async () => {
    mocks.get.mockResolvedValue({
      data: draftedSession({
        state: 'partial',
        partial_post_error: { failed_at_comment_idx: 2 },
        posted_comments: [
          {
            id: 1, client_mutation_id: 'abc',
            github_comment_id: 7001,
            file_path: 'src/a.py', line_number: 10,
            body_preview: '...', posted_at: '',
          },
        ],
      }),
    });
    // No startReview on mount for partial state
    mocks.startReview.mockResolvedValue({ data: {} });
    const wrapper = mount(GradingSessionDetailView);
    await flushPromises();
    expect(wrapper.find('[data-testid="resume-btn"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="send-btn"]').exists()).toBe(false);
  });

  it('shows Generate draft prompt when no draft has been generated yet', async () => {
    mocks.get.mockResolvedValue({
      data: draftedSession({
        state: 'pending',
        ai_draft_generated_at: null,
        ai_draft_comments: [],
        ai_draft_scores: {},
      }),
    });
    mocks.startReview.mockResolvedValue({ data: {} });
    const wrapper = mount(GradingSessionDetailView);
    await flushPromises();
    expect(wrapper.text()).toContain('No AI draft yet');
  });

  it('Send posts dirty edits first (saves then sends)', async () => {
    mocks.get.mockResolvedValue({ data: draftedSession() });
    mocks.startReview.mockResolvedValue({
      data: { ...draftedSession(), state: 'reviewing' },
    });
    mocks.update.mockResolvedValue({ data: {} });
    mocks.send.mockResolvedValue({
      data: { state: 'posted', posted_count: 1, skipped_duplicate_count: 0 },
    });

    const wrapper = mount(GradingSessionDetailView);
    await flushPromises();

    // Edit a comment to make the view dirty
    const commentBody = wrapper.find('[data-testid="comment-body-0"]');
    expect(commentBody.exists()).toBe(true);
    await commentBody.setValue('Edited feedback text');
    await flushPromises();

    // Click send
    await wrapper.find('[data-testid="send-btn"]').trigger('click');
    await flushPromises();

    // Save called before send
    expect(mocks.update).toHaveBeenCalled();
    expect(mocks.send).toHaveBeenCalled();
    const updateOrder = mocks.update.mock.invocationCallOrder[0];
    const sendOrder = mocks.send.mock.invocationCallOrder[0];
    expect(updateOrder).toBeLessThan(sendOrder);
  });

  it('renders a partial-post banner after a 207 Multi-Status response', async () => {
    mocks.get.mockResolvedValue({ data: draftedSession() });
    mocks.startReview.mockResolvedValue({
      data: { ...draftedSession(), state: 'reviewing' },
    });
    mocks.send.mockRejectedValue({
      response: {
        status: 207,
        data: { error: 'partial_post', state: 'partial', posted_so_far: 1 },
      },
    });

    const wrapper = mount(GradingSessionDetailView);
    await flushPromises();
    await wrapper.find('[data-testid="send-btn"]').trigger('click');
    await flushPromises();
    expect(wrapper.text().toLowerCase()).toContain('partial post');
  });
});
