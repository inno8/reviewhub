<script setup lang="ts">
/**
 * CohortDetailView — /org/cohorts/:id
 *
 * Cohort detail: members + courses. Admin can add/remove members and create
 * courses inside the cohort.
 *
 * Wires to:
 *   GET  /api/grading/cohorts/:id/
 *   GET  /api/grading/cohorts/:id/members/
 *   POST /api/grading/cohorts/:id/members/
 *   DELETE /api/grading/cohorts/:id/members/:membership_id/
 *   GET  /api/grading/courses/?cohort=...  (client-side filter)
 *
 * Workstream E1 of Nakijken Copilot v1 Scope B1.
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';

interface Cohort {
  id: number;
  name: string;
  year: number | null;
  archived_at: string | null;
  student_count: number;
  course_count: number;
}
interface Member {
  id: number;
  student: number;
  student_email: string;
  student_name: string;
  student_repo_url: string;
  joined_at: string;
}
interface Course {
  id: number;
  cohort: number | null;
  name: string;
  owner: number;
  owner_email: string;
  rubric: number | null;
  rubric_name: string | null;
  student_count: number;
  archived_at: string | null;
}

const route = useRoute();
const router = useRouter();
const id = computed(() => Number(route.params.id));

const cohort = ref<Cohort | null>(null);
const members = ref<Member[]>([]);
const courses = ref<Course[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const showAddMember = ref(false);
const memberForm = ref({ studentId: '', repoUrl: '' });
const memberError = ref<string | null>(null);
const addingMember = ref(false);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const [cRes, mRes, coursesRes] = await Promise.all([
      api.grading.cohorts.get(id.value),
      api.grading.cohorts.members(id.value),
      api.grading.courses.list(),
    ]);
    cohort.value = cRes.data;
    members.value = Array.isArray(mRes.data) ? mRes.data : (mRes.data.results || []);
    const all: Course[] = Array.isArray(coursesRes.data)
      ? coursesRes.data
      : (coursesRes.data.results || []);
    courses.value = all.filter(c => c.cohort === id.value);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load cohort';
  } finally {
    loading.value = false;
  }
}

async function addMember() {
  const sid = parseInt(memberForm.value.studentId, 10);
  if (!sid) {
    memberError.value = 'Student ID required (numeric user ID).';
    return;
  }
  addingMember.value = true;
  memberError.value = null;
  try {
    await api.grading.cohorts.addMember(id.value, sid, memberForm.value.repoUrl);
    memberForm.value = { studentId: '', repoUrl: '' };
    showAddMember.value = false;
    await load();
  } catch (err: any) {
    memberError.value = err?.response?.data?.detail
      || JSON.stringify(err?.response?.data || {})
      || 'Failed to add member';
  } finally {
    addingMember.value = false;
  }
}

async function removeMember(m: Member) {
  if (!window.confirm(`Remove ${m.student_email} from this cohort?`)) return;
  try {
    await api.grading.cohorts.removeMember(id.value, m.id);
    await load();
  } catch (err: any) {
    window.alert(err?.response?.data?.detail || 'Failed to remove member');
  }
}

function openCourse(c: Course) {
  router.push({ name: 'course-detail', params: { id: c.id } });
}

function goBack() { router.push({ name: 'org-cohorts' }); }

onMounted(load);
watch(id, load);
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <header class="flex items-start gap-4 mb-8">
          <button
            class="text-sm text-on-surface-variant hover:text-on-surface transition-colors mt-1"
            @click="goBack"
          >
            ← Cohorts
          </button>
          <div v-if="cohort">
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">
              {{ cohort.name }}
            </h1>
            <p class="text-on-surface-variant mt-2">
              <span v-if="cohort.year">Year {{ cohort.year }} · </span>
              {{ cohort.student_count }} students · {{ cohort.course_count }} courses
              <span v-if="cohort.archived_at"> · Archived</span>
            </p>
          </div>
        </header>

        <div v-if="loading" class="p-12 text-center text-outline">
          <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
          <p class="mt-2 text-sm">Loading cohort…</p>
        </div>
        <div
          v-else-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >
          {{ error }}
        </div>
        <div v-else-if="cohort" class="flex flex-col gap-6">
          <!-- Members -->
          <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">
                Members ({{ members.length }})
              </h2>
              <button
                v-if="!cohort.archived_at"
                class="primary-gradient text-on-primary px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
                @click="showAddMember = true"
                data-testid="add-member-btn"
              >
                <span class="material-symbols-outlined text-sm">person_add</span>
                Add member
              </button>
            </div>
            <div
              v-if="!members.length"
              class="p-8 text-center text-outline text-sm"
            >
              No students enrolled yet.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                    <th class="px-6 py-4">Student</th>
                    <th class="px-6 py-4">Email</th>
                    <th class="px-6 py-4">Repo</th>
                    <th class="px-6 py-4">Joined</th>
                    <th class="px-6 py-4"></th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/5">
                  <tr
                    v-for="m in members"
                    :key="m.id"
                    class="hover:bg-surface-container-high/40 transition-colors"
                  >
                    <td class="px-6 py-4 text-sm text-on-surface">{{ m.student_name || '—' }}</td>
                    <td class="px-6 py-4 text-sm text-on-surface-variant">{{ m.student_email }}</td>
                    <td class="px-6 py-4 text-sm">
                      <a
                        v-if="m.student_repo_url"
                        :href="m.student_repo_url"
                        target="_blank"
                        class="text-primary hover:underline"
                      >
                        {{ m.student_repo_url.split('/').slice(-2).join('/') }}
                      </a>
                      <span v-else class="text-outline">—</span>
                    </td>
                    <td class="px-6 py-4 text-xs text-on-surface-variant">
                      {{ new Date(m.joined_at).toLocaleDateString() }}
                    </td>
                    <td class="px-6 py-4 text-right">
                      <button
                        v-if="!cohort.archived_at"
                        class="text-xs text-error hover:text-error/80 font-semibold transition-colors"
                        @click="removeMember(m)"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- Courses -->
          <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">
                Courses ({{ courses.length }})
              </h2>
            </div>
            <div
              v-if="!courses.length"
              class="p-8 text-center text-outline text-sm"
            >
              No courses in this cohort. Create one from the admin API or the course detail view (coming soon).
            </div>
            <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
              <div
                v-for="c in courses"
                :key="c.id"
                class="bg-surface-container rounded-lg border border-outline-variant/10 p-4 cursor-pointer hover:border-primary/40 transition-colors"
                :class="{ 'opacity-55': c.archived_at }"
                @click="openCourse(c)"
                data-testid="course-card"
              >
                <h3 class="text-sm font-bold text-on-surface m-0 mb-1">{{ c.name }}</h3>
                <p class="text-xs text-on-surface-variant m-0">{{ c.owner_email }}</p>
                <div class="flex flex-wrap gap-2 mt-3">
                  <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container-high text-on-surface-variant">
                    {{ c.student_count }} students
                  </span>
                  <span
                    v-if="c.rubric_name"
                    class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container-high text-on-surface-variant"
                  >
                    Rubric: {{ c.rubric_name }}
                  </span>
                  <span
                    v-if="c.archived_at"
                    class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-on-surface-variant/10 text-on-surface-variant"
                  >
                    Archived
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- Add member modal -->
    <div
      v-if="showAddMember"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
      @click.self="showAddMember = false"
    >
      <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
          <h2 class="text-lg font-bold text-on-surface m-0">Add student to cohort</h2>
          <button
            class="text-outline hover:text-on-surface transition-colors"
            @click="showAddMember = false"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6 space-y-4">
          <p class="text-xs text-on-surface-variant">
            Student must already exist in your organisation. Find the user ID on the Members page or invite them first.
          </p>
          <form @submit.prevent="addMember" class="space-y-4">
            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">Student user ID</label>
              <input
                v-model="memberForm.studentId"
                type="number"
                required
                placeholder="e.g. 42"
                data-testid="student-id-input"
                class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
              />
            </div>
            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">Student repo URL (optional)</label>
              <input
                v-model="memberForm.repoUrl"
                type="url"
                placeholder="https://github.com/student/repo"
                class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
              />
            </div>
            <p v-if="memberError" class="text-sm text-error">{{ memberError }}</p>
            <div class="flex gap-3 pt-2">
              <button
                type="button"
                class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
                @click="showAddMember = false"
              >
                Cancel
              </button>
              <button
                type="submit"
                :disabled="addingMember"
                class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg disabled:opacity-50 transition-all active:scale-95 shadow-lg shadow-primary/20"
              >
                {{ addingMember ? 'Adding…' : 'Add' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </AppShell>
</template>

