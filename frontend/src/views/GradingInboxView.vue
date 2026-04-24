<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-7xl mx-auto">
        <header class="flex flex-wrap gap-4 justify-between items-end mb-8">
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">Nakijken</h1>
            <p class="text-sm text-on-surface-variant mt-2">
              Je studenten in de klassen die aan jou zijn toegewezen.
              <span v-if="totalPendingCount > 0" class="text-primary font-semibold">
                {{ totalPendingCount }} PR{{ totalPendingCount === 1 ? '' : 's' }} wacht op feedback.
              </span>
            </p>
          </div>
          <button
            @click="refresh"
            :disabled="loading"
            class="bg-surface-container hover:bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-medium border border-outline-variant/20 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            data-testid="refresh-btn"
          >
            <span v-if="loading">Laden…</span>
            <span v-else>Vernieuwen</span>
          </button>
        </header>

        <!-- Search + filters -->
        <div
          class="flex flex-wrap gap-4 items-end px-4 py-3 bg-surface-container-low border border-outline-variant/10 rounded-xl mb-6"
        >
          <label class="flex flex-col text-xs text-on-surface-variant flex-1 min-w-[220px]">
            <span class="mb-1 uppercase tracking-widest font-semibold">Zoeken</span>
            <input
              v-model="search"
              type="text"
              placeholder="Zoek op naam of e-mail"
              class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1.5 px-2 focus:ring-1 focus:ring-primary/50 focus:outline-none"
              data-testid="student-search"
            />
          </label>

          <label class="flex flex-col text-xs text-on-surface-variant">
            <span class="mb-1 uppercase tracking-widest font-semibold">Klas</span>
            <select
              v-model="selectedCohort"
              class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1.5 px-2 min-w-[180px] focus:ring-1 focus:ring-primary/50 focus:outline-none"
              data-testid="filter-cohort"
            >
              <option :value="null">Alle klassen</option>
              <option v-for="c in cohorts" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </label>

          <label class="flex flex-col text-xs text-on-surface-variant">
            <span class="mb-1 uppercase tracking-widest font-semibold">Vak</span>
            <select
              v-model="selectedCourse"
              class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1.5 px-2 min-w-[180px] focus:ring-1 focus:ring-primary/50 focus:outline-none"
              data-testid="filter-course"
            >
              <option :value="null">Alle vakken</option>
              <option v-for="c in courses" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </label>

          <label class="flex flex-col text-xs text-on-surface-variant">
            <span class="mb-1 uppercase tracking-widest font-semibold">Sorteer</span>
            <select
              v-model="sortMode"
              class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1.5 px-2 min-w-[180px] focus:ring-1 focus:ring-primary/50 focus:outline-none"
              data-testid="sort-mode"
            >
              <option value="urgent">Meest urgent eerst</option>
              <option value="alpha">Op naam (A-Z)</option>
            </select>
          </label>
        </div>

        <div
          v-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm mb-4"
          data-testid="error-banner"
        >
          {{ error }}
        </div>

        <!-- Loading skeletons -->
        <div
          v-if="loading && students.length === 0"
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
        >
          <div
            v-for="n in 6"
            :key="n"
            class="h-44 bg-surface-container-low rounded-xl animate-pulse"
          ></div>
        </div>

        <!-- No cohorts assigned -->
        <div
          v-else-if="!loading && cohorts.length === 0"
          class="glass-panel p-12 text-center rounded-xl"
          data-testid="empty-no-cohorts"
        >
          <h2 class="text-xl font-semibold text-on-surface mb-2">Nog geen klassen toegewezen.</h2>
          <p class="text-on-surface-variant">
            Vraag de beheerder om je aan een klas of vak te koppelen — dan verschijnen je studenten hier.
          </p>
        </div>

        <!-- No students match filters -->
        <div
          v-else-if="filteredStudents.length === 0"
          class="glass-panel p-12 text-center rounded-xl"
          data-testid="empty-no-results"
        >
          <h2 class="text-xl font-semibold text-on-surface mb-2">Geen studenten gevonden.</h2>
          <p class="text-on-surface-variant">
            Pas de zoekopdracht of filters aan om andere studenten te zien.
          </p>
        </div>

        <!-- Student grid -->
        <div
          v-else
          class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          data-testid="student-grid"
        >
          <div
            v-for="s in filteredStudents"
            :key="s.id"
            @click="openStudent(s.id)"
            :data-testid="`student-card-${s.id}`"
          >
            <StudentCard
              :name="s.name"
              :email="s.email"
              :avatar-url="s.avatarUrl"
              :cohort-names="s.cohortNames"
              :course-names="s.courseNames"
              :pending-count="s.pendingCount"
            />
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';
import StudentCard from '@/components/grading/StudentCard.vue';

interface Cohort {
  id: number;
  name: string;
  course_count?: number;
  student_count?: number;
}
interface Course {
  id: number;
  name: string;
  cohort?: number | null;
}
interface Member {
  id: number;
  student: number;
  student_email: string;
  student_name: string;
  student_avatar_url?: string | null;
  joined_at: string;
}
interface SessionRow {
  id: number;
  state: string;
  student_email: string;
  course_id: number;
}
interface StudentRow {
  id: number;
  name: string;
  email: string;
  avatarUrl: string | null;
  cohortIds: number[];
  cohortNames: string[];
  courseIds: number[];
  courseNames: string[];
  pendingCount: number;
}

const router = useRouter();

const cohorts = ref<Cohort[]>([]);
const courses = ref<Course[]>([]);
const students = ref<StudentRow[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

const search = ref('');
const selectedCohort = ref<number | null>(null);
const selectedCourse = ref<number | null>(null);
const sortMode = ref<'urgent' | 'alpha'>('urgent');

function unwrap<T>(data: any): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as T[];
  if (Array.isArray(data.results)) return data.results as T[];
  return [];
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    // Teacher-scoped cohorts + courses are returned by the backend's
    // queryset filtering (see CohortViewSet.get_queryset / CourseViewSet).
    const [cohortsRes, coursesRes] = await Promise.all([
      api.grading.cohorts.list(),
      api.grading.courses.list(),
    ]);
    cohorts.value = unwrap<Cohort>(cohortsRes.data);
    courses.value = unwrap<Course>(coursesRes.data);

    if (cohorts.value.length === 0) {
      students.value = [];
      return;
    }

    // Fetch members per cohort + pending sessions in parallel.
    const membersPromises = cohorts.value.map(c =>
      api.grading.cohorts.members(c.id).then(r => ({ cohort: c, members: unwrap<Member>(r.data) }))
    );
    const sessionsPromise = api.grading.sessions.list().then(r => unwrap<SessionRow>(r.data));

    const [perCohort, sessions] = await Promise.all([
      Promise.all(membersPromises),
      sessionsPromise,
    ]);

    // Aggregate pending counts by student email.
    const PENDING_STATES = new Set(['pending', 'drafted', 'reviewing', 'partial']);
    const pendingByEmail = new Map<string, number>();
    for (const s of sessions) {
      if (!PENDING_STATES.has(s.state)) continue;
      pendingByEmail.set(s.student_email, (pendingByEmail.get(s.student_email) || 0) + 1);
    }

    // Build courses-by-cohort index to tag each student with courses of
    // the cohorts they belong to.
    const coursesByCohort = new Map<number, Course[]>();
    for (const co of courses.value) {
      if (co.cohort == null) continue;
      const arr = coursesByCohort.get(co.cohort) || [];
      arr.push(co);
      coursesByCohort.set(co.cohort, arr);
    }

    // De-dupe students across cohorts (a student's cohort is OneToOne per
    // CLAUDE.md, but defensive aggregation keeps us safe if that changes).
    const byId = new Map<number, StudentRow>();
    for (const { cohort, members } of perCohort) {
      const cohortCourses = coursesByCohort.get(cohort.id) || [];
      for (const m of members) {
        const existing = byId.get(m.student);
        const avatarUrl = (m as any).student_avatar_url || null;
        if (existing) {
          if (!existing.cohortIds.includes(cohort.id)) {
            existing.cohortIds.push(cohort.id);
            existing.cohortNames.push(cohort.name);
          }
          for (const co of cohortCourses) {
            if (!existing.courseIds.includes(co.id)) {
              existing.courseIds.push(co.id);
              existing.courseNames.push(co.name);
            }
          }
        } else {
          byId.set(m.student, {
            id: m.student,
            name: m.student_name || m.student_email,
            email: m.student_email,
            avatarUrl,
            cohortIds: [cohort.id],
            cohortNames: [cohort.name],
            courseIds: cohortCourses.map(co => co.id),
            courseNames: cohortCourses.map(co => co.name),
            pendingCount: pendingByEmail.get(m.student_email) || 0,
          });
        }
      }
    }

    students.value = Array.from(byId.values());
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Kon studenten niet laden';
    students.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function refresh() {
  load();
}

function openStudent(id: number) {
  router.push({ name: 'grading-student-prs', params: { id } });
}

const filteredStudents = computed<StudentRow[]>(() => {
  const q = search.value.trim().toLowerCase();
  const filtered = students.value.filter(s => {
    if (q && !s.name.toLowerCase().includes(q) && !s.email.toLowerCase().includes(q)) {
      return false;
    }
    if (selectedCohort.value && !s.cohortIds.includes(selectedCohort.value)) return false;
    if (selectedCourse.value && !s.courseIds.includes(selectedCourse.value)) return false;
    return true;
  });
  const sorted = filtered.slice();
  if (sortMode.value === 'alpha') {
    sorted.sort((a, b) => a.name.localeCompare(b.name));
  } else {
    // "Meest urgent eerst" — most pending PRs first, tie-break on name.
    sorted.sort((a, b) => {
      if (a.pendingCount !== b.pendingCount) return b.pendingCount - a.pendingCount;
      return a.name.localeCompare(b.name);
    });
  }
  return sorted;
});

const totalPendingCount = computed(() =>
  students.value.reduce((sum, s) => sum + s.pendingCount, 0),
);
</script>
