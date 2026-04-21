<script setup lang="ts">
/**
 * CourseDetailView — /org/courses/:id
 *
 * Course detail: name, owner, rubric, cohort, archive action.
 * Teacher or admin can view; admin can reassign owner.
 *
 * Workstream E1 of Nakijken Copilot v1 Scope B1.
 */
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';

interface Course {
  id: number;
  cohort: number | null;
  cohort_name: string | null;
  name: string;
  owner: number;
  owner_email: string;
  rubric: number | null;
  rubric_name: string | null;
  source_control_type: string;
  target_branch_pattern: string;
  archived_at: string | null;
  student_count: number;
  created_at: string;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const id = computed(() => Number(route.params.id));

const course = ref<Course | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

const saveBusy = ref(false);
const editName = ref('');
const editBranchPattern = ref('');

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const { data } = await api.grading.courses.get(id.value);
    course.value = data;
    editName.value = data.name;
    editBranchPattern.value = data.target_branch_pattern;
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load course';
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!course.value) return;
  saveBusy.value = true;
  try {
    await api.grading.courses.update(id.value, {
      name: editName.value,
      target_branch_pattern: editBranchPattern.value,
    });
    await load();
  } catch (err: any) {
    window.alert(err?.response?.data?.detail || 'Failed to save');
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
  <div class="course-detail">
    <header class="page-header">
      <button class="btn-ghost" @click="goToCohort">← Cohort</button>
      <div v-if="course" class="header-meta">
        <h1>{{ course.name }}</h1>
        <p class="muted">
          <span v-if="course.cohort_name">{{ course.cohort_name }} · </span>
          {{ course.student_count }} students
          <span v-if="course.archived_at"> · Archived</span>
        </p>
      </div>
    </header>

    <div v-if="loading" class="loading">Loading course…</div>
    <div v-else-if="error" class="error-banner">{{ error }}</div>
    <div v-else-if="course" class="detail-body">
      <section class="card">
        <div class="card-head">
          <h2>Details</h2>
          <div class="head-actions">
            <button
              v-if="!course.archived_at"
              class="btn-ghost btn-danger"
              @click="archive"
            >
              Archive
            </button>
          </div>
        </div>

        <dl class="kv">
          <dt>Owner</dt>
          <dd>{{ course.owner_email }}</dd>

          <dt>Rubric</dt>
          <dd>{{ course.rubric_name || '— (no rubric assigned)' }}</dd>

          <dt>Source control</dt>
          <dd>{{ course.source_control_type }}</dd>

          <dt>Created</dt>
          <dd>{{ new Date(course.created_at).toLocaleDateString() }}</dd>
        </dl>

        <div class="edit-form" v-if="!course.archived_at && auth.isSchoolAdmin">
          <h3>Edit</h3>
          <form @submit.prevent="save" class="form">
            <label>
              Name
              <input v-model="editName" required />
            </label>
            <label>
              Target branch pattern
              <input v-model="editBranchPattern" placeholder="main" />
            </label>
            <div class="form-actions">
              <button type="submit" class="btn-primary" :disabled="saveBusy">
                {{ saveBusy ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </form>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.course-detail {
  max-width: 900px;
  margin: 0 auto;
  padding: 1.5rem;
  color: rgb(226 232 240);
}

.page-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.page-header h1 { font-size: 1.4rem; font-weight: 600; color: rgb(241 245 249); margin: 0; }
.muted { color: rgb(148 163 184); font-size: 0.85rem; }

.btn-ghost {
  background: transparent;
  border: 1px solid rgb(51 65 85);
  color: rgb(203 213 225);
  padding: 0.35rem 0.8rem;
  border-radius: 0.35rem;
  font-size: 0.8rem;
  cursor: pointer;
}
.btn-ghost:hover { background: rgb(30 41 59); }
.btn-ghost.btn-danger { color: rgb(252 165 165); border-color: rgb(127 29 29); }

.btn-primary {
  background: rgb(59 130 246);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 0.4rem;
  font-size: 0.85rem;
  cursor: pointer;
  font-weight: 500;
}
.btn-primary:hover { background: rgb(37 99 235); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.loading {
  text-align: center;
  padding: 2rem 1rem;
  color: rgb(148 163 184);
}
.error-banner {
  background: rgb(239 68 68 / 0.08);
  border: 1px solid rgb(239 68 68 / 0.3);
  color: rgb(252 165 165);
  border-radius: 0.5rem;
  padding: 0.8rem 1rem;
}

.card {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem 1.2rem;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1px solid rgb(30 41 59);
  padding-bottom: 0.6rem;
  margin-bottom: 0.8rem;
}
.card-head h2 { font-size: 1rem; font-weight: 600; color: rgb(241 245 249); margin: 0; }

.kv {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.4rem 1rem;
  font-size: 0.85rem;
  margin: 0;
}
.kv dt {
  font-weight: 600;
  color: rgb(148 163 184);
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  align-self: center;
}
.kv dd {
  margin: 0;
  color: rgb(226 232 240);
}

.edit-form {
  margin-top: 1.2rem;
  padding-top: 1rem;
  border-top: 1px solid rgb(30 41 59);
}
.edit-form h3 {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgb(148 163 184);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 0.6rem 0;
}

.form { display: flex; flex-direction: column; gap: 0.7rem; }
.form label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.8rem;
  color: rgb(148 163 184);
}
.form input {
  background: rgb(30 41 59);
  border: 1px solid rgb(51 65 85);
  border-radius: 0.35rem;
  padding: 0.5rem 0.6rem;
  color: rgb(226 232 240);
  font-size: 0.85rem;
}
.form input:focus { outline: none; border-color: rgb(59 130 246); }
.form-actions { display: flex; justify-content: flex-end; gap: 0.6rem; }
</style>
