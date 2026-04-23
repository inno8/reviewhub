/**
 * Smoke tests for GradingInboxView.vue — student browser (Piece 1).
 *
 * The inbox aggregates students from the teacher's assigned cohorts and
 * shows one card per student. Tests cover:
 *   - empty state when no cohorts are assigned
 *   - card grid when cohorts + members exist
 *   - search filters by name/email
 *   - clicking a card routes to /grading/students/:id/prs
 *   - error banner on API failure
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/composables/useApi', () => {
  const cohortsList = vi.fn();
  const coursesList = vi.fn();
  const cohortMembers = vi.fn();
  const sessionsList = vi.fn();
  return {
    api: {
      grading: {
        cohorts: {
          list: cohortsList,
          members: cohortMembers,
        },
        courses: { list: coursesList },
        sessions: { list: sessionsList },
      },
    },
    __mocks: { cohortsList, coursesList, cohortMembers, sessionsList },
  };
});

const push = vi.fn();
vi.mock('vue-router', async () => {
  const actual = await vi.importActual<any>('vue-router');
  return {
    ...actual,
    useRouter: () => ({ push }),
    useRoute: () => ({ path: '/grading', params: {}, query: {}, name: 'grading-inbox' }),
  };
});

import GradingInboxView from '@/views/GradingInboxView.vue';
import * as apiModule from '@/composables/useApi';
const mocks = (apiModule as any).__mocks;

beforeEach(() => {
  setActivePinia(createPinia());
  push.mockReset();
  mocks.cohortsList.mockReset();
  mocks.coursesList.mockReset();
  mocks.cohortMembers.mockReset();
  mocks.sessionsList.mockReset();
});

describe('GradingInboxView (student browser)', () => {
  it('renders the no-cohorts empty state when the teacher has none assigned', async () => {
    mocks.cohortsList.mockResolvedValue({ data: { count: 0, results: [] } });
    mocks.coursesList.mockResolvedValue({ data: { count: 0, results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(wrapper.find('[data-testid="empty-no-cohorts"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="student-grid"]').exists()).toBe(false);
  });

  it('renders a student card per cohort member', async () => {
    mocks.cohortsList.mockResolvedValue({
      data: {
        results: [
          { id: 1, name: 'MBO-4 ICT Y2', course_count: 1, student_count: 2 },
        ],
      },
    });
    mocks.coursesList.mockResolvedValue({
      data: { results: [{ id: 7, name: 'Programmeren', cohort: 1 }] },
    });
    mocks.cohortMembers.mockResolvedValue({
      data: [
        {
          id: 100, student: 10,
          student_email: 'jan@ex.com', student_name: 'Jan de Boer',
          joined_at: '',
        },
        {
          id: 101, student: 11,
          student_email: 'piet@ex.com', student_name: 'Piet Jansen',
          joined_at: '',
        },
      ],
    });
    mocks.sessionsList.mockResolvedValue({
      data: {
        results: [
          { id: 500, state: 'drafted', student_email: 'jan@ex.com', course_id: 7 },
          { id: 501, state: 'posted', student_email: 'piet@ex.com', course_id: 7 },
        ],
      },
    });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(wrapper.find('[data-testid="student-grid"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="student-card-10"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="student-card-11"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Jan de Boer');
    expect(wrapper.text()).toContain('Piet Jansen');
  });

  it('filters students by the search input (name OR email, case-insensitive)', async () => {
    mocks.cohortsList.mockResolvedValue({
      data: { results: [{ id: 1, name: 'MBO-4', course_count: 0, student_count: 2 }] },
    });
    mocks.coursesList.mockResolvedValue({ data: { results: [] } });
    mocks.cohortMembers.mockResolvedValue({
      data: [
        { id: 100, student: 10, student_email: 'jan@ex.com', student_name: 'Jan de Boer', joined_at: '' },
        { id: 101, student: 11, student_email: 'piet@ex.com', student_name: 'Piet Jansen', joined_at: '' },
      ],
    });
    mocks.sessionsList.mockResolvedValue({ data: { results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    await wrapper.find('[data-testid="student-search"]').setValue('piet');
    await flushPromises();
    expect(wrapper.find('[data-testid="student-card-11"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="student-card-10"]').exists()).toBe(false);
  });

  it('routes to the student PR list when a card is clicked', async () => {
    mocks.cohortsList.mockResolvedValue({
      data: { results: [{ id: 1, name: 'MBO-4', course_count: 0, student_count: 1 }] },
    });
    mocks.coursesList.mockResolvedValue({ data: { results: [] } });
    mocks.cohortMembers.mockResolvedValue({
      data: [
        { id: 100, student: 42, student_email: 'x@ex.com', student_name: 'X', joined_at: '' },
      ],
    });
    mocks.sessionsList.mockResolvedValue({ data: { results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    await wrapper.find('[data-testid="student-card-42"]').trigger('click');
    expect(push).toHaveBeenCalledWith({
      name: 'grading-student-prs',
      params: { id: 42 },
    });
  });

  it('renders the error banner when the cohorts API fails', async () => {
    mocks.cohortsList.mockRejectedValue({
      response: { data: { detail: 'server exploded' } },
    });
    mocks.coursesList.mockResolvedValue({ data: { results: [] } });
    const wrapper = mount(GradingInboxView);
    await flushPromises();
    expect(wrapper.find('[data-testid="error-banner"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('server exploded');
  });
});
