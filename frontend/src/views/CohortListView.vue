<script setup lang="ts">
/**
 * CohortListView — /org/cohorts
 *
 * Admin-facing list of cohorts with create + archive actions.
 * Wires to /api/grading/cohorts/ (Workstream C CRUD).
 *
 * Workstream E1 of Nakijken Copilot v1 Scope B1.
 */
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';

interface Cohort {
  id: number;
  name: string;
  year: number | null;
  starts_at: string | null;
  ends_at: string | null;
  archived_at: string | null;
  student_count: number;
  course_count: number;
  created_at: string;
}

const router = useRouter();
const cohorts = ref<Cohort[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const includeArchived = ref(false);

const showCreate = ref(false);
const createForm = ref({ name: '', year: null as number | null });
const creating = ref(false);
const createError = ref<string | null>(null);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const params: Record<string, string> = {};
    if (includeArchived.value) params.include_archived = 'true';
    const { data } = await api.grading.cohorts.list(params);
    cohorts.value = Array.isArray(data) ? data : (data.results || []);
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load cohorts';
    cohorts.value = [];
  } finally {
    loading.value = false;
  }
}

async function createCohort() {
  if (!createForm.value.name.trim()) return;
  creating.value = true;
  createError.value = null;
  try {
    const payload: Record<string, unknown> = { name: createForm.value.name.trim() };
    if (createForm.value.year) payload.year = createForm.value.year;
    await api.grading.cohorts.create(payload);
    showCreate.value = false;
    createForm.value = { name: '', year: null };
    await load();
  } catch (err: any) {
    createError.value = err?.response?.data?.detail
      || JSON.stringify(err?.response?.data || {})
      || 'Failed to create';
  } finally {
    creating.value = false;
  }
}

async function archiveCohort(c: Cohort) {
  if (!window.confirm(`Archive cohort "${c.name}"? Grading history stays queryable.`)) return;
  try {
    await api.grading.cohorts.archive(c.id);
    await load();
  } catch (err: any) {
    window.alert(err?.response?.data?.detail || 'Failed to archive');
  }
}

function openCohort(c: Cohort) {
  router.push({ name: 'cohort-detail', params: { id: c.id } });
}

onMounted(load);
</script>

<template>
  <div class="cohort-list">
    <header class="page-header">
      <div>
        <h1>Cohorts</h1>
        <p class="muted">Groups of students. Courses belong to a cohort.</p>
      </div>
      <div class="header-actions">
        <label class="archived-toggle">
          <input type="checkbox" v-model="includeArchived" @change="load" />
          Include archived
        </label>
        <button class="btn-primary" @click="showCreate = true" data-testid="new-cohort-btn">
          + New cohort
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading">Loading cohorts…</div>
    <div v-else-if="error" class="error-banner">{{ error }}</div>
    <div v-else-if="!cohorts.length" class="empty">
      <p>No cohorts yet. Create one to start grouping students and courses.</p>
    </div>
    <div v-else class="cohort-grid">
      <div
        v-for="c in cohorts"
        :key="c.id"
        class="cohort-card"
        :class="{ archived: c.archived_at }"
        @click="openCohort(c)"
        data-testid="cohort-card"
      >
        <div class="card-head">
          <h2>{{ c.name }}</h2>
          <span v-if="c.archived_at" class="badge archived-badge">Archived</span>
        </div>
        <div class="card-meta">
          <span v-if="c.year" class="pill">Year {{ c.year }}</span>
          <span class="pill">{{ c.student_count }} students</span>
          <span class="pill">{{ c.course_count }} courses</span>
        </div>
        <div class="card-actions" v-if="!c.archived_at">
          <button
            class="btn-ghost btn-danger"
            @click.stop="archiveCohort(c)"
            data-testid="archive-btn"
          >
            Archive
          </button>
        </div>
      </div>
    </div>

    <!-- Create modal (minimal inline) -->
    <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
      <div class="modal">
        <h2>New cohort</h2>
        <form @submit.prevent="createCohort" class="form">
          <label>
            Name
            <input
              v-model="createForm.name"
              placeholder="2025 Software Track"
              data-testid="cohort-name-input"
              required
            />
          </label>
          <label>
            Year (optional)
            <input
              v-model.number="createForm.year"
              type="number"
              placeholder="2025"
              min="2000"
              max="2100"
            />
          </label>
          <p v-if="createError" class="error-inline">{{ createError }}</p>
          <div class="form-actions">
            <button type="button" class="btn-ghost" @click="showCreate = false">
              Cancel
            </button>
            <button type="submit" class="btn-primary" :disabled="creating" data-testid="submit-cohort">
              {{ creating ? 'Creating…' : 'Create cohort' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cohort-list {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
  color: rgb(226 232 240);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1.5rem;
  gap: 1rem;
}
.page-header h1 {
  font-size: 1.5rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}
.muted {
  color: rgb(148 163 184);
  font-size: 0.85rem;
  margin: 0.25rem 0 0 0;
}

.header-actions {
  display: flex;
  gap: 0.8rem;
  align-items: center;
}
.archived-toggle {
  font-size: 0.8rem;
  color: rgb(148 163 184);
  display: flex;
  gap: 0.4rem;
  align-items: center;
  cursor: pointer;
}

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
.btn-ghost.btn-danger:hover { background: rgb(127 29 29 / 0.3); }

.loading, .empty {
  text-align: center;
  padding: 3rem 1rem;
  color: rgb(148 163 184);
}
.error-banner {
  background: rgb(239 68 68 / 0.08);
  border: 1px solid rgb(239 68 68 / 0.3);
  color: rgb(252 165 165);
  border-radius: 0.5rem;
  padding: 0.8rem 1rem;
}

.cohort-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}
.cohort-card {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.75rem;
  padding: 1rem 1.1rem;
  cursor: pointer;
  transition: border-color 0.15s;
}
.cohort-card:hover { border-color: rgb(59 130 246 / 0.5); }
.cohort-card.archived { opacity: 0.55; }

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.6rem;
}
.card-head h2 {
  font-size: 1rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}

.badge, .pill {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.7rem;
  font-weight: 500;
}
.archived-badge {
  background: rgb(100 116 139 / 0.3);
  color: rgb(203 213 225);
}
.card-meta { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.6rem; }
.pill {
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}

.card-actions {
  display: flex;
  gap: 0.4rem;
  border-top: 1px solid rgb(30 41 59 / 0.5);
  padding-top: 0.6rem;
  margin-top: 0.4rem;
}

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.75rem;
  padding: 1.5rem;
  width: min(440px, 90vw);
  color: rgb(226 232 240);
}
.modal h2 {
  font-size: 1.1rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0 0 1rem 0;
}

.form { display: flex; flex-direction: column; gap: 0.8rem; }
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

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.error-inline {
  color: rgb(252 165 165);
  font-size: 0.8rem;
  margin: 0;
}
</style>
