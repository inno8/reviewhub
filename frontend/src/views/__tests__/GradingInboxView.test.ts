/**
 * Smoke tests for GradingInboxView.vue.
 *
 * Keeps the scope tight: renders the three states (loading, empty, populated),
 * click fires router.push, and the state/course filters trigger fetchSessions.
 *
 * We stub useRouter + mock the api module. No Django required.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

// Mock useApi FIRST so the store picks up the mock.
vi.mock('@/composables/useApi', () => {
  const sessionsList = vi.fn();
  const coursesList = vi.fn();
  return {
    api: {
      grading: {
        rubrics: { list: vi.fn() },
        courses: { list: coursesList },
        sessions: {
          list: sessionsList,
          get: vi.fn(),
          update: vi.fn(),
          startReview: vi.fn(),
          generateDraft: vi.fn(),
          send: vi.fn(),
          resume: vi.fn(),
        },
        submissions: { list: vi.fn() },
        costLogs: { list: vi.fn() },
      },
    },
    __mocks: { sessionsList, coursesList },
  };
});

const push = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

import GradingInboxView from '@/views/GradingInboxView.vue';
import * as apiModule from '@/composables/useApi';

const mocks = (apiModule as any).__mocks;

beforeEach(() => {
  setActivePinia(createPinia());
  push.mockReset();
  mocks.sessionsList.mockReset();
  mocks.coursesList.mockReset();
});

describe('GradingInboxView', () => {
  it('renders the empty state when API returns no sessions', async () => {
    mocks.sessionsList.mockResolvedValue({ data: { count: 0, results: [] } });
    mocks.coursesList.mockResolvedValue({ data: { count: 0, results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="session-list"]').exists()).toBe(false);
  });

  it('renders session rows when API returns sessions', async () => {
    mocks.sessionsList.mockResolvedValue({
      data: {
        count: 2,
        results: [
          {
            id: 10, state: 'drafted', student_email: 'jan@ex.com',
            student_name: 'Jan de Boer',
            course_id: 1, course_name: 'MBO-4 ICT Y2',
            pr_url: 'https://github.com/jan/repo/pull/1',
            pr_title: 'Add null-check to parser',
            due_at: null, ai_draft_generated_at: null, posted_at: null,
            docent_review_time_seconds: null,
            created_at: '', updated_at: '',
          },
          {
            id: 11, state: 'posted', student_email: 'piet@ex.com',
            student_name: 'Piet Jansen',
            course_id: 1, course_name: 'MBO-4 ICT Y2',
            pr_url: 'https://github.com/piet/repo/pull/2',
            pr_title: 'Refactor login',
            due_at: null, ai_draft_generated_at: '', posted_at: '',
            docent_review_time_seconds: 120,
            created_at: '', updated_at: '',
          },
        ],
      },
    });
    mocks.coursesList.mockResolvedValue({ data: { count: 0, results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(wrapper.find('[data-testid="session-list"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="empty-state"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="session-row-10"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="session-row-11"]').exists()).toBe(true);
    // Student name renders
    expect(wrapper.text()).toContain('Jan de Boer');
    expect(wrapper.text()).toContain('Piet Jansen');
  });

  it('renders the error banner on API failure', async () => {
    mocks.sessionsList.mockRejectedValue({
      response: { data: { detail: 'server exploded' } },
    });
    mocks.coursesList.mockResolvedValue({ data: { count: 0, results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(wrapper.find('[data-testid="error-banner"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('server exploded');
  });

  it('routes to the session detail view when a row is clicked', async () => {
    mocks.sessionsList.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 42, state: 'drafted', student_email: 'x@ex.com', student_name: 'X',
            course_id: 1, course_name: 'A', pr_url: '', pr_title: 'X',
            due_at: null, ai_draft_generated_at: null, posted_at: null,
            docent_review_time_seconds: null,
            created_at: '', updated_at: '',
          },
        ],
      },
    });
    mocks.coursesList.mockResolvedValue({ data: { count: 0, results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    await wrapper.find('[data-testid="session-row-42"]').trigger('click');
    expect(push).toHaveBeenCalledWith({
      name: 'grading-session-detail',
      params: { id: 42 },
    });
  });

  it('changing the state filter re-fetches with the new param', async () => {
    mocks.sessionsList.mockResolvedValue({ data: { count: 0, results: [] } });
    mocks.coursesList.mockResolvedValue({ data: { count: 0, results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(mocks.sessionsList).toHaveBeenCalledTimes(1);
    await wrapper.find('[data-testid="filter-state"]').setValue('drafted');
    await flushPromises();
    expect(mocks.sessionsList).toHaveBeenCalledTimes(2);
    expect(mocks.sessionsList.mock.calls[1][0]).toEqual({ state: 'drafted' });
  });
});
