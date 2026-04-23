<script setup lang="ts">
/**
 * CourseDetailView — /org/courses/:id
 *
 * Course detail for teachers and admins.
 *
 * Sections:
 *   Details      — name, teacher, rubric, source control, created date
 *   Students     — read-only list pulled from cohort memberships
 *   Edit (admin) — rename course, change branch pattern, reassign teacher
 *                  Teacher picker filtered to cohort's assigned teachers.
 *
 * API wires:
 *   GET   /api/grading/courses/:id/
 *   PATCH /api/grading/courses/:id/          name, target_branch_pattern, owner
 *   POST  /api/grading/courses/:id/archive/
 *   GET   /api/grading/cohorts/:cohortId/members/   (student list)
 *   GET   /api/grading/cohorts/:cohortId/teachers/  (teacher picker)
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';
import AppShell from '@/components/layout/AppShell.vue';

interface Course {
  id: number;
  cohort: number | null;
  cohort_name: string | null;
  name: string;
  owner: number;
  owner_email: string;
  owner_name: string | null;
  rubric: number | null;
  rubric_name: string | null;
  source_control_type: string;
  target_branch_pattern: string;
  archived_at: string | null;
  student_count: number;
  created_at: string;
}
interface Member {
  id: number;
  student: number;
  student_email: string;
  student_name: string;
  student_repo_url: string | null;
  joined_at: string;
}
interface TeacherAssignment {
  id: number;
  teacher: number;
  teacher_email: string;
  teacher_name: string;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const id = computed(() => Number(route.params.id));

const course = ref<Course | null>(null);
const students = ref<Member[]>([]);
const cohortTeachers = ref<TeacherAssignment[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// Edit form
const saveBusy = ref(false);
const editName = ref('');
const editBranchPattern = ref('');
const editOwnerId = ref<number | null>(null);
const teacherSearch = ref('');
const saveError = ref<string | null>(null);

const filteredTeachers = computed(() => {
  const q = teacherSearch.value.toLowerCase();
  if (!q) return cohortTeachers.value;
  return cohortTeachers.value.filter(t =>
    t.teacher_email.toLowerCase().includes(q) ||
    (t.teacher_name || '').toLowerCase().includes(q)
  );
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const { data } = await api.grading.courses.get(id.value);
    course.value = data;
    editName.value = data.name;
    editBranchPattern.value = data.target_branch_pattern;
    editOwnerId.value = data.owner;

    // Load cohort students and teacher options
    if (data.cohort) {
      const [membersRes, teachersRes] = await Promise.all([
        api.grading.cohorts.members(data.cohort),
        api.grading.cohorts.teachers(data.cohort),
      ]);
      students.value = Array.isArray(membersRes.data)
        ? membersRes.data
        : (membersRes.data.results || []);
      cohortTeachers.value = Array.isArray(teachersRes.data)
        ? teachersRes.data
        : (teachersRes.data.results || []);
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load course';
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!course.value) return;
  saveBusy.value = true;
  saveError.value = null;
  try {
    const payload: any = {
      name: editName.value,
      target_branch_pattern: editBranchPattern.value,
    };
    if (editOwnerId.value && editOwnerId.value !== course.value.owner) {
      payload.owner = editOwnerId.value;
    }
    await api.grading.courses.update(id.value, payload);
    await load();
  } catch (err: any) {
    saveError.value =
      err?.response?.data?.owner?.[0] ||
      err?.response?.data?.name?.[0] ||
      err?.response?.data?.detail ||
      'Failed to save';
  } finally {
    saveBusy.value = false;
  }
}

async function archive() {
  if (!course.value) return;
  if (!window.confirm(`Archive course "${course.value.name}"?`)) return;
  try {
    await api.grading.courses.archive(id.value);
    await load();
  } catch (err: any) {
    window.alert(err?.response?.data?.detail || 'Failed to archive');
  }
}

function goToCohort() {
  if (course.value?.cohort) {
    router.push({ name: 'cohort-detail', params: { id: course.value.cohort } });
  } else {
    router.push({ name: 'org-cohorts' });
  }
}

onMounted(load);
watch(id, load);
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-4xl mx-auto">

        <!-- Header -->
        <header class="flex items-start gap-4 mb-8">
          <button
            class="text-sm text-on-surface-variant hover:text-on-surface transition-colors mt-1"
            @click="goToCohort"
          >
            ← {{ course?.cohort_name || 'Cohort' }}
          </button>
          <div v-if="course">
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">
              {{ course.name }}
            </h1>
            <p class="text-on-surface-variant mt-2">
              <span v-if="course.cohort_name">{{ course.cohort_name }} · </span>
              {{ course.student_count }} students
              <span v-if="course.archived_at"> · Archived</span>
            </p>
          </div>
        </header>

        <div v-if="loading" class="p-12 text-center text-outline">
          <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
          <p class="mt-2 text-sm">Loading course…</p>
        </div>
        <div v-else-if="error" class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm">
          {{ error }}
        </div>

        <div v-else-if="course" class="flex flex-col gap-6">

          <!-- ─── Details card ─── -->
          <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">Details</h2>
              <button
                v-if="!course.archived_at && auth.isSchoolAdmin"
                class="text-xs text-error hover:text-error/80 font-semibold transition-colors"
                @click="archive"
              >
                Archive
              </button>
            </div>

            <dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-3 px-6 py-5 text-sm">
              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Teacher</dt>
              <dd class="m-0 text-on-surface">{{ course.owner_name || course.owner_email }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Rubric</dt>
              <dd class="m-0 text-on-surface">{{ course.rubric_name || '— (no rubric assigned)' }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Source control</dt>
              <dd class="m-0 text-on-surface capitalize">{{ course.source_control_type.replace('_', ' ') }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Branch pattern</dt>
              <dd class="m-0 font-mono text-on-surface text-xs">{{ course.target_branch_pattern }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Created</dt>
              <dd class="m-0 text-on-surface">{{ new Date(course.created_at).toLocaleDateString() }}</dd>
            </dl>
          </section>

          <!-- ─── Students card ─── -->
          <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">
                Students
                <span class="ml-2 text-sm font-normal text-outline">({{ students.length }})</span>
              </h2>
              <p class="text-xs text-on-surface-variant mt-1">
                All students enrolled in {{ course.cohort_name || 'this cohort' }}.
                Manage enrolment from the cohort page.
              </p>
            </div>

            <div v-if="!course.cohort" class="p-6 text-sm text-outline">
              This course is not linked to a cohort.
            </div>
            <div v-else-if="!students.length" class="p-6 text-sm text-outline">
              No students enrolled in this cohort yet.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                    <th class="px-6 py-3">Name</th>
                    <th class="px-6 py-3">Email</th>
                    <th class="px-6 py-3">Repo</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/5">
                  <tr
                    v-for="s in students"
                    :key="s.id"
                    class="hover:bg-surface-container-high/40 transition-colors"
                  >
                    <td class="px-6 py-3 text-sm text-on-surface">{{ s.student_name || '—' }}</td>
                    <td class="px-6 py-3 text-sm text-on-surface-variant">{{ s.student_email }}</td>
                    <td class="px-6 py-3 text-sm">
                      <a
                        v-if="s.student_repo_url"
                        :href="s.student_repo_url"
                        target="_blank"
                        class="text-primary hover:underline text-xs font-mono"
                      >
                        {{ s.student_repo_url.split('/').slice(-2).join('/') }}
                      </a>
                      <span v-else class="text-outline text-xs">— not set</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- ─── Edit card (admin only) ─── -->
          <section
            v-if="!course.archived_at && auth.isSchoolAdmin"
            class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden"
          >
            <div class="px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">Edit</h2>
            </div>
            <form @submit.prevent="save" class="px-6 py-5 space-y-5">

              <div class="space-y-1.5">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Course name</label>
                <input
                  v-model="editName"
                  required
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
                />
              </div>

              <div class="space-y-1.5">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Target branch pattern</label>
                <input
                  v-model="editBranchPattern"
                  placeholder="main"
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
                />
              </div>

              <!-- Teacher reassignment -->
              <div class="space-y-2">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Assign teacher</label>
                <p class="text-xs text-on-surface-variant">
                  Only teachers assigned to {{ course.cohort_name || 'this cohort' }} are shown.
                </p>
                <input
                  v-model="teacherSearch"
                  type="text"
                  placeholder="Filter teachers…"
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm"
                />
                <div class="max-h-44 overflow-y-auto rounded-lg border border-outline-variant/20 divide-y divide-outline-variant/10">
                  <button
                    v-for="ta in filteredTeachers"
                    :key="ta.id"
                    type="button"
                    class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-container-high/50 transition-colors"
                    :class="editOwnerId === ta.teacher ? 'bg-primary/10' : ''"
                    @click="editOwnerId = ta.teacher"
                  >
                    <span class="w-7 h-7 rounded-full bg-tertiary/15 flex items-center justify-center text-tertiary text-xs font-bold shrink-0">
                      {{ (ta.teacher_name || ta.teacher_email)[0].toUpperCase() }}
                    </span>
                    <div>
                      <p class="text-sm text-on-surface leading-tight">{{ ta.teacher_name || ta.teacher_email.split('@')[0] }}</p>
                      <p class="text-xs text-outline">{{ ta.teacher_email }}</p>
                    </div>
                    <span v-if="editOwnerId === ta.teacher" class="ml-auto text-primary material-symbols-outlined text-lg">check_circle</span>
                  </button>
                  <p v-if="filteredTeachers.length === 0" class="text-xs text-outline px-4 py-3">
                    No teachers assigned to this cohort.
                    <router-link
                      v-if="course.cohort"
                      :to="{ name: 'cohort-detail', params: { id: course.cohort } }"
                      class="text-primary font-semibold"
                    >
                      Add teachers to the cohort first.
                    </router-link>
                  </p>
                </div>
              </div>

              <p v-if="saveError" class="text-sm text-error">{{ saveError }}</p>
              <div class="flex justify-end">
                <button
                  type="submit"
                  :disabled="saveBusy"
                  class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold disabled:opacity-50 transition-all active:scale-95 shadow-lg shadow-primary/20"
                >
                  {{ saveBusy ? 'Saving…' : 'Save' }}
                </button>
              </div>
            </form>
          </section>

        </div>
      </div>
    </div>
  </AppShell>
</template>
