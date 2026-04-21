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
  <div v-if="loading" class="mcw mcw-loading">Loading your cohort…</div>
  <div v-else-if="error" class="mcw mcw-error">{{ error }}</div>
  <div v-else-if="!cohort" class="mcw mcw-empty">
    <p class="title">You're not in a cohort yet</p>
    <p class="muted">Ask your school admin to add you to a cohort.</p>
  </div>
  <div v-else class="mcw" data-testid="my-cohort-widget">
    <header class="mcw-head">
      <h2>My cohort</h2>
      <span class="pill">{{ cohort.name }}</span>
    </header>

    <!-- Teachers -->
    <section v-if="teachers.length" class="block">
      <h3>Teachers</h3>
      <ul class="teacher-list">
        <li v-for="t in teachers" :key="t" class="teacher-item">
          <span class="material-symbols-outlined icon">person</span>
          {{ t }}
        </li>
      </ul>
    </section>

    <!-- Courses + rubrics -->
    <section class="block">
      <h3>Current courses</h3>
      <div v-if="!courses.length" class="muted">No active courses yet.</div>
      <ul v-else class="course-list">
        <li v-for="c in courses" :key="c.id" class="course-item">
          <div class="course-name">{{ c.name }}</div>
          <div class="course-meta">
            <span v-if="c.rubric_name" class="rubric-tag">
              Rubric: {{ c.rubric_name }}
            </span>
            <span v-else class="muted tiny">No rubric assigned</span>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.mcw {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem 1.2rem;
  color: rgb(226 232 240);
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mcw-loading, .mcw-error, .mcw-empty {
  text-align: center;
  color: rgb(148 163 184);
  font-size: 0.85rem;
}
.mcw-error { color: rgb(252 165 165); }
.mcw-empty .title { color: rgb(226 232 240); font-weight: 500; margin: 0 0 0.4rem 0; }

.mcw-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1px solid rgb(30 41 59);
  padding-bottom: 0.6rem;
}
.mcw-head h2 {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}
.pill {
  background: rgb(59 130 246 / 0.15);
  color: rgb(147 197 253);
  padding: 0.2rem 0.6rem;
  border-radius: 0.35rem;
  font-size: 0.8rem;
  font-weight: 500;
}

.block h3 {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(148 163 184);
  margin: 0 0 0.5rem 0;
}

.teacher-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.teacher-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: rgb(203 213 225);
}
.icon {
  font-size: 1rem;
  color: rgb(148 163 184);
}

.course-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.course-item {
  padding: 0.5rem 0.7rem;
  background: rgb(30 41 59 / 0.4);
  border-radius: 0.4rem;
  border-left: 3px solid rgb(59 130 246 / 0.6);
}
.course-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: rgb(226 232 240);
}
.course-meta { margin-top: 0.2rem; font-size: 0.75rem; }
.rubric-tag { color: rgb(134 239 172); }
.muted { color: rgb(148 163 184); }
.tiny { font-size: 0.7rem; }
</style>
