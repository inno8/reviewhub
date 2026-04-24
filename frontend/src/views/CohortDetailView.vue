<script setup lang="ts">
/**
 * CohortDetailView — /org/cohorts/:id
 *
 * Three-tab cohort management for school admins and teachers.
 *
 * Tabs:
 *   Students  — view/add/remove enrolled students via searchable dropdown
 *   Teachers  — view/add/remove assigned teachers via searchable dropdown
 *   Courses   — view courses; admins can create courses (name + teacher)
 *
 * API wires:
 *   GET    /api/grading/cohorts/:id/
 *   GET    /api/grading/cohorts/:id/members/
 *   POST   /api/grading/cohorts/:id/members/      body: { student_id, student_repo_url? }
 *   DELETE /api/grading/cohorts/:id/members/:mid/
 *   GET    /api/grading/cohorts/:id/teachers/
 *   POST   /api/grading/cohorts/:id/teachers/     body: { teacher_id }
 *   DELETE /api/grading/cohorts/:id/teachers/:tid/
 *   GET    /api/grading/courses/?cohort=:id
 *   POST   /api/grading/courses/                  body: { name, cohort, owner }
 *   GET    /api/users/?role=developer              student picker
 *   GET    /api/users/?role=teacher                teacher picker
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';
import AppShell from '@/components/layout/AppShell.vue';

interface Cohort {
  id: number;
  name: string;
  year: string | null;
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
interface TeacherAssignment {
  id: number;
  teacher: number;
  teacher_email: string;
  teacher_name: string;
  added_at: string;
}
interface Course {
  id: number;
  cohort: number | null;
  name: string;
  owner: number;
  owner_email: string;
  owner_name: string | null;
  rubric_name: string | null;
  student_count: number;
  archived_at: string | null;
}
interface OrgUser {
  id: number;
  email: string;
  username: string;
  display_name?: string;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const id = computed(() => Number(route.params.id));

// ── Data ────────────────────────────────────────────────────────────────────
const cohort = ref<Cohort | null>(null);
const members = ref<Member[]>([]);
const teacherAssignments = ref<TeacherAssignment[]>([]);
const courses = ref<Course[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// ── Tab ─────────────────────────────────────────────────────────────────────
type Tab = 'students' | 'teachers' | 'courses';
const activeTab = ref<Tab>('students');

// ── Org user lists (for dropdowns) ──────────────────────────────────────────
const orgStudents = ref<OrgUser[]>([]);
const orgTeachers = ref<OrgUser[]>([]);
const orgUsersLoading = ref(false);

async function loadOrgUsers() {
  if (orgStudents.value.length && orgTeachers.value.length) return; // already loaded
  orgUsersLoading.value = true;
  try {
    const [studRes, teachRes] = await Promise.all([
      api.users.list({ role: 'developer' }),
      api.users.list({ role: 'teacher' }),
    ]);
    orgStudents.value = Array.isArray(studRes.data) ? studRes.data : (studRes.data.results || []);
    orgTeachers.value = Array.isArray(teachRes.data) ? teachRes.data : (teachRes.data.results || []);
  } catch {
    // non-fatal — just leaves dropdowns empty
  } finally {
    orgUsersLoading.value = false;
  }
}

// ── Load cohort data ────────────────────────────────────────────────────────
async function load() {
  loading.value = true;
  error.value = null;
  try {
    // Teachers tab is admin-only — skip that request for teachers to avoid
    // an unnecessary API call (and a potential 403 confusion).
    const requests: Promise<any>[] = [
      api.grading.cohorts.get(id.value),
      api.grading.cohorts.members(id.value),
      api.grading.courses.list({ cohort: id.value }),
    ];
    if (auth.isSchoolAdmin) {
      requests.splice(2, 0, api.grading.cohorts.teachers(id.value));
    }

    if (auth.isSchoolAdmin) {
      const [cRes, mRes, tRes, coursesRes] = await Promise.all(requests);
      cohort.value = cRes.data;
      members.value = Array.isArray(mRes.data) ? mRes.data : (mRes.data.results || []);
      teacherAssignments.value = Array.isArray(tRes.data) ? tRes.data : (tRes.data.results || []);
      const all: Course[] = Array.isArray(coursesRes.data)
        ? coursesRes.data
        : (coursesRes.data.results || []);
      courses.value = all.filter(c => c.cohort === id.value);
    } else {
      const [cRes, mRes, coursesRes] = await Promise.all(requests);
      cohort.value = cRes.data;
      members.value = Array.isArray(mRes.data) ? mRes.data : (mRes.data.results || []);
      teacherAssignments.value = []; // not visible to teachers
      const all: Course[] = Array.isArray(coursesRes.data)
        ? coursesRes.data
        : (coursesRes.data.results || []);
      courses.value = all.filter(c => c.cohort === id.value);
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load cohort';
  } finally {
    loading.value = false;
  }
}

// ── Add Student ─────────────────────────────────────────────────────────────
const showAddStudent = ref(false);
const studentForm = ref({ studentId: null as number | null, repoUrl: '' });
const studentSearch = ref('');
const studentError = ref<string | null>(null);
const addingStudent = ref(false);

const filteredStudents = computed(() => {
  const q = studentSearch.value.toLowerCase();
  const enrolled = new Set(members.value.map(m => m.student));
  return orgStudents.value.filter(u =>
    !enrolled.has(u.id) &&
    (!q || u.email.toLowerCase().includes(q) || (u.username || '').toLowerCase().includes(q))
  );
});

async function addStudent() {
  if (!studentForm.value.studentId) {
    studentError.value = 'Please select a student.';
    return;
  }
  addingStudent.value = true;
  studentError.value = null;
  try {
    await api.grading.cohorts.addMember(id.value, studentForm.value.studentId, studentForm.value.repoUrl);
    studentForm.value = { studentId: null, repoUrl: '' };
    studentSearch.value = '';
    showAddStudent.value = false;
    await load();
  } catch (err: any) {
    studentError.value =
      err?.response?.data?.student?.[0] ||
      err?.response?.data?.detail ||
      JSON.stringify(err?.response?.data || {}) ||
      'Failed to add student';
  } finally {
    addingStudent.value = false;
  }
}

async function removeStudent(m: Member) {
  if (!window.confirm(`Remove ${m.student_email} from this cohort?`)) return;
  try {
    await api.grading.cohorts.removeMember(id.value, m.id);
    await load();
  } catch (err: any) {
    window.alert(err?.response?.data?.detail || 'Failed to remove student');
  }
}

// ── Add Teacher ─────────────────────────────────────────────────────────────
const showAddTeacher = ref(false);
const teacherForm = ref({ teacherId: null as number | null });
const teacherSearch = ref('');
const teacherError = ref<string | null>(null);
const addingTeacher = ref(false);

const filteredTeachers = computed(() => {
  const q = teacherSearch.value.toLowerCase();
  const assigned = new Set(teacherAssignments.value.map(t => t.teacher));
  return orgTeachers.value.filter(u =>
    !assigned.has(u.id) &&
    (!q || u.email.toLowerCase().includes(q) || (u.username || '').toLowerCase().includes(q))
  );
});

async function addTeacher() {
  if (!teacherForm.value.teacherId) {
    teacherError.value = 'Please select a teacher.';
    return;
  }
  addingTeacher.value = true;
  teacherError.value = null;
  try {
    await api.grading.cohorts.addTeacher(id.value, teacherForm.value.teacherId);
    teacherForm.value = { teacherId: null };
    teacherSearch.value = '';
    showAddTeacher.value = false;
    await load();
  } catch (err: any) {
    teacherError.value =
      err?.response?.data?.teacher_id ||
      err?.response?.data?.detail ||
      JSON.stringify(err?.response?.data || {}) ||
      'Failed to add teacher';
  } finally {
    addingTeacher.value = false;
  }
}

async function removeTeacher(ta: TeacherAssignment) {
  if (!window.confirm(`Remove ${ta.teacher_email} from this cohort?`)) return;
  try {
    await api.grading.cohorts.removeTeacher(id.value, ta.id);
    await load();
  } catch (err: any) {
    window.alert(err?.response?.data?.detail || 'Failed to remove teacher');
  }
}

// ── Add Course ───────────────────────────────────────────────────────────────
const showAddCourse = ref(false);
const courseForm = ref({ name: '', ownerId: null as number | null });
const courseSearch = ref('');
const courseError = ref<string | null>(null);
const addingCourse = ref(false);

/** Teachers available for new course: assigned to cohort AND without an active course yet. */
const courseTeacherOptions = computed(() => {
  const q = courseSearch.value.toLowerCase();
  // Teachers who already own an active (non-archived) course in this cohort cannot get another.
  const alreadyHasCourse = new Set(
    courses.value.filter(c => !c.archived_at).map(c => c.owner)
  );
  return teacherAssignments.value.filter(ta =>
    !alreadyHasCourse.has(ta.teacher) &&
    (!q || ta.teacher_email.toLowerCase().includes(q) || (ta.teacher_name || '').toLowerCase().includes(q))
  );
});

async function addCourse() {
  if (!courseForm.value.name.trim()) {
    courseError.value = 'Course name is required.';
    return;
  }
  if (!courseForm.value.ownerId) {
    courseError.value = 'Assign a teacher.';
    return;
  }
  addingCourse.value = true;
  courseError.value = null;
  try {
    await api.grading.courses.create({
      name: courseForm.value.name.trim(),
      cohort: id.value,
      owner: courseForm.value.ownerId,
    });
    courseForm.value = { name: '', ownerId: null };
    courseSearch.value = '';
    showAddCourse.value = false;
    await load();
  } catch (err: any) {
    courseError.value =
      err?.response?.data?.name?.[0] ||
      err?.response?.data?.owner?.[0] ||
      err?.response?.data?.detail ||
      JSON.stringify(err?.response?.data || {}) ||
      'Failed to create course';
  } finally {
    addingCourse.value = false;
  }
}

function openCourse(c: Course) {
  router.push({ name: 'course-detail', params: { id: c.id } });
}

function goBack() { router.push({ name: 'org-cohorts' }); }

// ── Modal open helpers ───────────────────────────────────────────────────────
function openAddStudent() {
  studentForm.value = { studentId: null, repoUrl: '' };
  studentSearch.value = '';
  studentError.value = null;
  showAddStudent.value = true;
  loadOrgUsers();
}

function openAddTeacher() {
  teacherForm.value = { teacherId: null };
  teacherSearch.value = '';
  teacherError.value = null;
  showAddTeacher.value = true;
  loadOrgUsers();
}

function openAddCourse() {
  courseForm.value = { name: '', ownerId: null };
  courseSearch.value = '';
  courseError.value = null;
  showAddCourse.value = true;
  // teachers list already loaded via load()
}

onMounted(load);
watch(id, load);
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">

        <!-- Header -->
        <header class="flex items-start gap-4 mb-8">
          <button
            class="text-sm text-on-surface-variant hover:text-on-surface transition-colors mt-1"
            @click="goBack"
          >
            ← Cohorts
          </button>
          <div v-if="cohort" class="flex-1">
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">
              {{ cohort.name }}
            </h1>
            <p class="text-on-surface-variant mt-2">
              <span v-if="cohort.year">Year {{ cohort.year }} · </span>
              {{ cohort.student_count }} students · {{ cohort.course_count }} courses
              <span v-if="cohort.archived_at"> · Archived</span>
            </p>
          </div>
          <router-link
            v-if="cohort"
            :to="{ name: 'grading-cohort-overview', params: { id: cohort.id } }"
            class="bg-surface-container hover:bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors shrink-0"
          >
            Klas-overzicht
            <span class="material-symbols-outlined text-sm">arrow_forward</span>
          </router-link>
        </header>

        <div v-if="loading" class="p-12 text-center text-outline">
          <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
          <p class="mt-2 text-sm">Loading cohort…</p>
        </div>
        <div v-else-if="error" class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm">
          {{ error }}
        </div>

        <div v-else-if="cohort">
          <!-- Tabs -->
          <div class="flex gap-1 mb-6 bg-surface-container p-1 rounded-xl w-fit">
            <button
              v-for="tab in (auth.isSchoolAdmin ? ['students', 'teachers', 'courses'] : ['students', 'courses']) as Tab[]"
              :key="tab"
              :class="[
                'px-5 py-2 rounded-lg text-sm font-bold transition-all capitalize',
                activeTab === tab
                  ? 'bg-surface-container-highest text-primary shadow-sm'
                  : 'text-outline hover:text-on-surface'
              ]"
              @click="activeTab = tab"
            >
              {{ tab }}
              <span class="ml-1.5 text-xs font-normal opacity-70">
                {{ tab === 'students' ? members.length : tab === 'teachers' ? teacherAssignments.length : courses.length }}
              </span>
            </button>
          </div>

          <!-- ─── Students tab ─── -->
          <section v-show="activeTab === 'students'" class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">
                Students
                <span class="ml-2 text-sm font-normal text-outline">({{ members.length }})</span>
              </h2>
              <button
                v-if="!cohort.archived_at && auth.isSchoolAdmin"
                class="primary-gradient text-on-primary px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
                @click="openAddStudent"
              >
                <span class="material-symbols-outlined text-sm">person_add</span>
                Add student
              </button>
            </div>

            <div v-if="!members.length" class="p-8 text-center text-outline text-sm">
              No students enrolled yet.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                    <th class="px-6 py-4">Name</th>
                    <th class="px-6 py-4">Email</th>
                    <th class="px-6 py-4">Joined</th>
                    <th v-if="auth.isSchoolAdmin" class="px-6 py-4"></th>
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
                    <td class="px-6 py-4 text-xs text-on-surface-variant">
                      {{ new Date(m.joined_at).toLocaleDateString() }}
                    </td>
                    <td v-if="auth.isSchoolAdmin" class="px-6 py-4 text-right">
                      <button
                        v-if="!cohort.archived_at"
                        class="text-xs text-error hover:text-error/80 font-semibold transition-colors"
                        @click="removeStudent(m)"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- ─── Teachers tab ─── -->
          <section v-show="activeTab === 'teachers'" class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">
                Teachers
                <span class="ml-2 text-sm font-normal text-outline">({{ teacherAssignments.length }})</span>
              </h2>
              <button
                v-if="!cohort.archived_at && auth.isSchoolAdmin"
                class="primary-gradient text-on-primary px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
                @click="openAddTeacher"
              >
                <span class="material-symbols-outlined text-sm">person_add</span>
                Add teacher
              </button>
            </div>

            <div v-if="!teacherAssignments.length" class="p-8 text-center text-outline text-sm">
              No teachers assigned yet. Add teachers before creating courses.
            </div>
            <div v-else class="overflow-x-auto">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                    <th class="px-6 py-4">Name</th>
                    <th class="px-6 py-4">Email</th>
                    <th class="px-6 py-4">Added</th>
                    <th v-if="auth.isSchoolAdmin" class="px-6 py-4"></th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/5">
                  <tr
                    v-for="ta in teacherAssignments"
                    :key="ta.id"
                    class="hover:bg-surface-container-high/40 transition-colors"
                  >
                    <td class="px-6 py-4 text-sm text-on-surface">{{ ta.teacher_name || '—' }}</td>
                    <td class="px-6 py-4 text-sm text-on-surface-variant">{{ ta.teacher_email }}</td>
                    <td class="px-6 py-4 text-xs text-on-surface-variant">
                      {{ new Date(ta.added_at).toLocaleDateString() }}
                    </td>
                    <td v-if="auth.isSchoolAdmin" class="px-6 py-4 text-right">
                      <button
                        v-if="!cohort.archived_at"
                        class="text-xs text-error hover:text-error/80 font-semibold transition-colors"
                        @click="removeTeacher(ta)"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- ─── Courses tab ─── -->
          <section v-show="activeTab === 'courses'" class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">
                Courses
                <span class="ml-2 text-sm font-normal text-outline">({{ courses.length }})</span>
              </h2>
              <button
                v-if="!cohort.archived_at && auth.isSchoolAdmin"
                class="primary-gradient text-on-primary px-4 py-2 rounded-lg font-bold text-sm flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
                @click="openAddCourse"
                :disabled="teacherAssignments.length === 0"
                :title="teacherAssignments.length === 0 ? 'Add at least one teacher to the cohort first' : undefined"
              >
                <span class="material-symbols-outlined text-sm">add</span>
                Add course
              </button>
            </div>

            <div v-if="!courses.length" class="p-8 text-center text-outline text-sm">
              <p>No courses yet.</p>
              <p v-if="teacherAssignments.length === 0" class="mt-1 text-xs">
                First add teachers to this cohort, then create courses.
              </p>
            </div>
            <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
              <div
                v-for="c in courses"
                :key="c.id"
                class="bg-surface-container rounded-lg border border-outline-variant/10 p-4 cursor-pointer hover:border-primary/40 transition-colors"
                :class="{ 'opacity-55': c.archived_at }"
                @click="openCourse(c)"
              >
                <h3 class="text-sm font-bold text-on-surface m-0 mb-1">{{ c.name }}</h3>
                <p class="text-xs text-on-surface-variant m-0">
                  <span class="material-symbols-outlined text-[12px] align-middle mr-0.5">person</span>
                  {{ c.owner_name || c.owner_email }}
                </p>
                <div class="flex flex-wrap gap-2 mt-3">
                  <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container-high text-on-surface-variant">
                    {{ c.student_count }} students
                  </span>
                  <span
                    v-if="c.rubric_name"
                    class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container-high text-on-surface-variant"
                  >
                    {{ c.rubric_name }}
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

    <!-- ══════════════════ Add Student Modal ══════════════════ -->
    <div
      v-if="showAddStudent"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
      @click.self="showAddStudent = false"
    >
      <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
          <h2 class="text-lg font-bold text-on-surface m-0">Add student</h2>
          <button class="text-outline hover:text-on-surface transition-colors" @click="showAddStudent = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Search students</label>
            <input
              v-model="studentSearch"
              type="text"
              placeholder="Name or email…"
              autofocus
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
            />
          </div>

          <div v-if="orgUsersLoading" class="text-center py-4">
            <span class="material-symbols-outlined animate-spin text-primary">progress_activity</span>
          </div>
          <div v-else class="max-h-56 overflow-y-auto rounded-lg border border-outline-variant/20 divide-y divide-outline-variant/10">
            <button
              v-for="u in filteredStudents"
              :key="u.id"
              type="button"
              class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-container-high/50 transition-colors"
              :class="studentForm.studentId === u.id ? 'bg-primary/10' : ''"
              @click="studentForm.studentId = u.id"
            >
              <span
                class="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center text-primary text-xs font-bold shrink-0"
              >
                {{ (u.username || u.email)[0].toUpperCase() }}
              </span>
              <div>
                <p class="text-sm text-on-surface leading-tight">{{ u.username || u.email.split('@')[0] }}</p>
                <p class="text-xs text-outline">{{ u.email }}</p>
              </div>
              <span v-if="studentForm.studentId === u.id" class="ml-auto text-primary material-symbols-outlined text-lg">check_circle</span>
            </button>
            <p v-if="filteredStudents.length === 0 && !orgUsersLoading" class="text-xs text-outline px-4 py-3">
              No more students to add.
            </p>
          </div>

          <p v-if="studentError" class="text-sm text-error">{{ studentError }}</p>
          <div class="flex gap-3 pt-2">
            <button
              type="button"
              class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
              @click="showAddStudent = false"
            >
              Cancel
            </button>
            <button
              type="button"
              :disabled="addingStudent || !studentForm.studentId"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg disabled:opacity-50 transition-all active:scale-95 shadow-lg shadow-primary/20"
              @click="addStudent"
            >
              {{ addingStudent ? 'Adding…' : 'Add' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════ Add Teacher Modal ══════════════════ -->
    <div
      v-if="showAddTeacher"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
      @click.self="showAddTeacher = false"
    >
      <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
          <h2 class="text-lg font-bold text-on-surface m-0">Add teacher</h2>
          <button class="text-outline hover:text-on-surface transition-colors" @click="showAddTeacher = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Search teachers</label>
            <input
              v-model="teacherSearch"
              type="text"
              placeholder="Name or email…"
              autofocus
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
            />
          </div>

          <div v-if="orgUsersLoading" class="text-center py-4">
            <span class="material-symbols-outlined animate-spin text-primary">progress_activity</span>
          </div>
          <div v-else class="max-h-56 overflow-y-auto rounded-lg border border-outline-variant/20 divide-y divide-outline-variant/10">
            <button
              v-for="u in filteredTeachers"
              :key="u.id"
              type="button"
              class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-container-high/50 transition-colors"
              :class="teacherForm.teacherId === u.id ? 'bg-primary/10' : ''"
              @click="teacherForm.teacherId = u.id"
            >
              <span class="w-7 h-7 rounded-full bg-tertiary/15 flex items-center justify-center text-tertiary text-xs font-bold shrink-0">
                {{ (u.username || u.email)[0].toUpperCase() }}
              </span>
              <div>
                <p class="text-sm text-on-surface leading-tight">{{ u.username || u.email.split('@')[0] }}</p>
                <p class="text-xs text-outline">{{ u.email }}</p>
              </div>
              <span v-if="teacherForm.teacherId === u.id" class="ml-auto text-primary material-symbols-outlined text-lg">check_circle</span>
            </button>
            <p v-if="filteredTeachers.length === 0 && !orgUsersLoading" class="text-xs text-outline px-4 py-3">
              No more teachers to add.
            </p>
          </div>

          <p v-if="teacherError" class="text-sm text-error">{{ teacherError }}</p>
          <div class="flex gap-3 pt-2">
            <button
              type="button"
              class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
              @click="showAddTeacher = false"
            >
              Cancel
            </button>
            <button
              type="button"
              :disabled="addingTeacher || !teacherForm.teacherId"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg disabled:opacity-50 transition-all active:scale-95 shadow-lg shadow-primary/20"
              @click="addTeacher"
            >
              {{ addingTeacher ? 'Adding…' : 'Add' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════ Add Course Modal ══════════════════ -->
    <div
      v-if="showAddCourse"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
      @click.self="showAddCourse = false"
    >
      <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
          <h2 class="text-lg font-bold text-on-surface m-0">Add course</h2>
          <button class="text-outline hover:text-on-surface transition-colors" @click="showAddCourse = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Course name</label>
            <input
              v-model="courseForm.name"
              type="text"
              required
              placeholder="e.g. Frontend Development"
              autofocus
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
            />
          </div>

          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Assign teacher</label>
            <input
              v-model="courseSearch"
              type="text"
              placeholder="Search by name or email…"
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm mb-2"
            />
            <div class="max-h-48 overflow-y-auto rounded-lg border border-outline-variant/20 divide-y divide-outline-variant/10">
              <button
                v-for="ta in courseTeacherOptions"
                :key="ta.id"
                type="button"
                class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-container-high/50 transition-colors"
                :class="courseForm.ownerId === ta.teacher ? 'bg-primary/10' : ''"
                @click="courseForm.ownerId = ta.teacher"
              >
                <span class="w-7 h-7 rounded-full bg-tertiary/15 flex items-center justify-center text-tertiary text-xs font-bold shrink-0">
                  {{ (ta.teacher_name || ta.teacher_email)[0].toUpperCase() }}
                </span>
                <div>
                  <p class="text-sm text-on-surface leading-tight">{{ ta.teacher_name || ta.teacher_email.split('@')[0] }}</p>
                  <p class="text-xs text-outline">{{ ta.teacher_email }}</p>
                </div>
                <span v-if="courseForm.ownerId === ta.teacher" class="ml-auto text-primary material-symbols-outlined text-lg">check_circle</span>
              </button>
              <p v-if="courseTeacherOptions.length === 0" class="text-xs text-outline px-4 py-3">
                No teachers in this cohort. Add teachers first.
              </p>
            </div>
          </div>

          <p v-if="courseError" class="text-sm text-error">{{ courseError }}</p>
          <div class="flex gap-3 pt-2">
            <button
              type="button"
              class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
              @click="showAddCourse = false"
            >
              Cancel
            </button>
            <button
              type="button"
              :disabled="addingCourse || !courseForm.name.trim() || !courseForm.ownerId"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg disabled:opacity-50 transition-all active:scale-95 shadow-lg shadow-primary/20"
              @click="addCourse"
            >
              {{ addingCourse ? 'Creating…' : 'Create course' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>
