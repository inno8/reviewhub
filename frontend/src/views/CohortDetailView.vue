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
  <div class="cohort-detail">
    <header class="page-header">
      <button class="btn-ghost" @click="goBack">← Cohorts</button>
      <div v-if="cohort" class="header-meta">
        <h1>{{ cohort.name }}</h1>
        <p class="muted">
          <span v-if="cohort.year">Year {{ cohort.year }} · </span>
          {{ cohort.student_count }} students · {{ cohort.course_count }} courses
          <span v-if="cohort.archived_at"> · Archived</span>
        </p>
      </div>
    </header>

    <div v-if="loading" class="loading">Loading cohort…</div>
    <div v-else-if="error" class="error-banner">{{ error }}</div>
    <div v-else-if="cohort" class="detail-body">
      <!-- Members -->
      <section class="card">
        <div class="card-head">
          <h2>Members ({{ members.length }})</h2>
          <button
            v-if="!cohort.archived_at"
            class="btn-primary"
            @click="showAddMember = true"
            data-testid="add-member-btn"
          >
            + Add member
          </button>
        </div>
        <div v-if="!members.length" class="empty">
          No students enrolled yet.
        </div>
        <table v-else class="table">
          <thead>
            <tr>
              <th>Student</th>
              <th>Email</th>
              <th>Repo</th>
              <th>Joined</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in members" :key="m.id">
              <td>{{ m.student_name || '—' }}</td>
              <td>{{ m.student_email }}</td>
              <td>
                <a v-if="m.student_repo_url" :href="m.student_repo_url" target="_blank" class="link">
                  {{ m.student_repo_url.split('/').slice(-2).join('/') }}
                </a>
                <span v-else class="muted">—</span>
              </td>
              <td class="muted">{{ new Date(m.joined_at).toLocaleDateString() }}</td>
              <td class="row-actions">
                <button
                  v-if="!cohort.archived_at"
                  class="btn-ghost btn-danger"
                  @click="removeMember(m)"
                >
                  Remove
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Courses -->
      <section class="card">
        <div class="card-head">
          <h2>Courses ({{ courses.length }})</h2>
        </div>
        <div v-if="!courses.length" class="empty">
          No courses in this cohort. Create one from the admin API or the course detail view (coming soon).
        </div>
        <div v-else class="course-grid">
          <div
            v-for="c in courses"
            :key="c.id"
            class="course-card"
            :class="{ archived: c.archived_at }"
            @click="openCourse(c)"
            data-testid="course-card"
          >
            <h3>{{ c.name }}</h3>
            <p class="muted">{{ c.owner_email }}</p>
            <div class="card-meta">
              <span class="pill">{{ c.student_count }} students</span>
              <span v-if="c.rubric_name" class="pill">Rubric: {{ c.rubric_name }}</span>
              <span v-if="c.archived_at" class="pill archived-pill">Archived</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Add member modal -->
    <div v-if="showAddMember" class="modal-backdrop" @click.self="showAddMember = false">
      <div class="modal">
        <h2>Add student to cohort</h2>
        <p class="muted tiny">
          Student must already exist in your organisation.
          Find the user ID on the Members page or invite them first.
        </p>
        <form @submit.prevent="addMember" class="form">
          <label>
            Student user ID
            <input
              v-model="memberForm.studentId"
              type="number"
              required
              placeholder="e.g. 42"
              data-testid="student-id-input"
            />
          </label>
          <label>
            Student repo URL (optional)
            <input
              v-model="memberForm.repoUrl"
              type="url"
              placeholder="https://github.com/student/repo"
            />
          </label>
          <p v-if="memberError" class="error-inline">{{ memberError }}</p>
          <div class="form-actions">
            <button type="button" class="btn-ghost" @click="showAddMember = false">Cancel</button>
            <button type="submit" class="btn-primary" :disabled="addingMember">
              {{ addingMember ? 'Adding…' : 'Add' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cohort-detail {
  max-width: 1200px;
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
.tiny { font-size: 0.75rem; }

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

.loading, .empty {
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

.detail-body { display: flex; flex-direction: column; gap: 1.2rem; }

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

.table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.table th {
  text-align: left;
  padding: 0.4rem 0.6rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: rgb(148 163 184);
  border-bottom: 1px solid rgb(30 41 59);
}
.table td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid rgb(30 41 59 / 0.5);
  color: rgb(203 213 225);
}
.row-actions { text-align: right; }

.link { color: rgb(147 197 253); text-decoration: none; }
.link:hover { text-decoration: underline; }

.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.8rem;
}
.course-card {
  background: rgb(30 41 59 / 0.4);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  padding: 0.8rem 1rem;
  cursor: pointer;
  transition: border-color 0.15s;
}
.course-card:hover { border-color: rgb(59 130 246 / 0.5); }
.course-card.archived { opacity: 0.55; }
.course-card h3 {
  font-size: 0.95rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0 0 0.3rem 0;
}

.card-meta { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.5rem; }
.pill {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.7rem;
  font-weight: 500;
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}
.archived-pill { background: rgb(100 116 139 / 0.3); }

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
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
}
.modal h2 { font-size: 1.1rem; font-weight: 600; color: rgb(241 245 249); margin: 0 0 0.4rem 0; }

.form { display: flex; flex-direction: column; gap: 0.8rem; margin-top: 0.8rem; }
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
.form-actions { display: flex; justify-content: flex-end; gap: 0.6rem; margin-top: 0.6rem; }
.error-inline { color: rgb(252 165 165); font-size: 0.8rem; margin: 0; }
</style>
