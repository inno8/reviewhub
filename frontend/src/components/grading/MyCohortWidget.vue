<script setup lang="ts">
/**
 * MyCohortWidget — student-facing card showing:
 *   - Cohort name
 *   - Teachers (course owners in this cohort)
 *   - Current courses + rubrics
 *
 * Wires to:
 *   GET /api/grading/cohorts/  (student scope → their own cohort)
 *   GET /api/grading/cohorts/:id/members/
 *   GET /api/grading/courses/  (student scope → cohort courses)
 *
 * Workstream E4 of Nakijken Copilot v1 Scope B1.
 *
 * Designed as a standalone card so it can be mounted on the student
 * dashboard once the current DashboardView WIP lands. Mountable on any
 * student page; returns null when the student has no cohort yet.
 */
import { ref, onMounted, computed } from 'vue';
import { api } from '@/composables/useApi';

interface Cohort {
  id: number;
  name: string;
  year: number | null;
  student_count: number;
  course_count: number;
}
interface Course {
  id: number;
  cohort: number | null;
  name: string;
  owner: number;
  owner_email: string;
  rubric_name: string | null;
  archived_at: string | null;
}

const loading = ref(false);
const error = ref<string | null>(null);
const cohort = ref<Cohort | null>(null);
const courses = ref<Course[]>([]);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const { data: cRaw } = await api.grading.cohorts.list();
    const list: Cohort[] = Array.isArray(cRaw) ? cRaw : (cRaw.results || []);
    if (!list.length) { cohort.value = null; return; }
    // Students see at most one cohort (their own); take the first active.
    cohort.value = list[0];

    const { data: coursesRaw } = await api.grading.courses.list();
    const all: Course[] = Array.isArray(coursesRaw)
      ? coursesRaw
      : (coursesRaw.results || []);
    courses.value = all.filter(c => c.cohort === cohort.value!.id && !c.archived_at);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load cohort';
  } finally {
    loading.value = false;
  }
}

/** Unique teacher emails across all courses in this cohort. */
const teachers = computed(() => {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const c of courses.value) {
    if (c.owner_email && !seen.has(c.owner_email)) {
      seen.add(c.owner_email);
      out.push(c.owner_email);
    }
  }
  return out;
});

onMounted(load);
</script>

<template>
  <div
    v-if="loading"
    class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 text-center text-outline text-sm"
  >
    Loading your cohort…
  </div>
  <div
    v-else-if="error"
    class="bg-error/10 border border-error/20 text-error rounded-xl p-6 text-center text-sm"
  >
    {{ error }}
  </div>
  <div
    v-else-if="!cohort"
    class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 text-center"
  >
    <p class="text-on-surface font-medium m-0 mb-1">You're not in a cohort yet</p>
    <p class="text-on-surface-variant text-sm m-0">Ask your school admin to add you to a cohort.</p>
  </div>
  <div
    v-else
    class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-6 flex flex-col gap-5"
    data-testid="my-cohort-widget"
  >
    <header class="flex justify-between items-center border-b border-outline-variant/10 pb-4">
      <h2 class="text-base font-bold text-on-surface m-0">My cohort</h2>
      <span class="bg-primary/15 text-primary px-3 py-1 rounded-md text-xs font-semibold">
        {{ cohort.name }}
      </span>
    </header>

    <!-- Teachers -->
    <section v-if="teachers.length">
      <h3 class="text-[11px] font-bold uppercase tracking-widest text-outline mb-2">Teachers</h3>
      <ul class="list-none p-0 m-0 flex flex-col gap-1.5">
        <li
          v-for="t in teachers"
          :key="t"
          class="flex items-center gap-2 text-sm text-on-surface-variant"
        >
          <span class="material-symbols-outlined text-base text-outline">person</span>
          {{ t }}
        </li>
      </ul>
    </section>

    <!-- Courses + rubrics -->
    <section>
      <h3 class="text-[11px] font-bold uppercase tracking-widest text-outline mb-2">Current courses</h3>
      <div v-if="!courses.length" class="text-on-surface-variant text-sm">No active courses yet.</div>
      <ul v-else class="list-none p-0 m-0 flex flex-col gap-2">
        <li
          v-for="c in courses"
          :key="c.id"
          class="px-3 py-2.5 bg-surface-container rounded-lg border-l-2 border-primary/60"
        >
          <div class="text-sm font-semibold text-on-surface">{{ c.name }}</div>
          <div class="mt-1 text-xs">
            <span v-if="c.rubric_name" class="text-tertiary">
              Rubric: {{ c.rubric_name }}
            </span>
            <span v-else class="text-outline">No rubric assigned</span>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>
