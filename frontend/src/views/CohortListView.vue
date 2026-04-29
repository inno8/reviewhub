<script setup lang="ts">
/**
 * CohortListView — /org/cohorts
 *
 * Admin-facing list of cohorts with create + archive actions.
 * Wires to /api/grading/cohorts/ (Workstream C CRUD).
 *
 * Workstream E1 of Nakijken Copilot v1 Scope B1.
 */
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';
import AppShell from '@/components/layout/AppShell.vue';

// Cohort write actions (create / archive) are admin-only on the backend
// (CohortViewSet.get_permissions returns IsOrgAdmin for these). The shared
// `isAdmin` computed includes teachers — we want strict school-admin or
// platform superuser here, so derive a tighter check.
const auth = useAuthStore();
const { isSchoolAdmin, isSuperuser } = storeToRefs(auth);
const canWriteCohorts = computed(() => isSchoolAdmin.value || isSuperuser.value);

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
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <header class="flex flex-wrap gap-4 justify-between items-end mb-8">
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">Cohorten</h1>
            <p class="text-on-surface-variant mt-2 max-w-xl">
              Klassen van studenten. Vakken horen bij een cohort.
            </p>
          </div>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-xs text-on-surface-variant cursor-pointer">
              <input
                type="checkbox"
                v-model="includeArchived"
                @change="load"
                class="h-4 w-4 rounded border-outline-variant bg-surface-container text-primary"
              />
              Toon gearchiveerd
            </label>
            <button
              v-if="canWriteCohorts"
              @click="showCreate = true"
              class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
              data-testid="new-cohort-btn"
            >
              <span class="material-symbols-outlined text-sm">add</span>
              Nieuw cohort
            </button>
          </div>
        </header>

        <div v-if="loading" class="p-12 text-center text-outline">
          <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
          <p class="mt-2 text-sm">Cohorten laden…</p>
        </div>
        <div
          v-else-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >
          {{ error }}
        </div>
        <div
          v-else-if="!cohorts.length"
          class="p-12 text-center text-outline text-sm bg-surface-container-low rounded-xl border border-outline-variant/10"
        >
          <span class="material-symbols-outlined text-3xl mb-2 block opacity-40">groups_2</span>
          Nog geen cohorten. Maak er een aan om studenten en vakken te organiseren.
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="c in cohorts"
            :key="c.id"
            class="bg-surface-container-low rounded-xl border border-outline-variant/10 p-5 cursor-pointer hover:border-primary/40 transition-colors"
            :class="{ 'opacity-55': c.archived_at }"
            @click="openCohort(c)"
            data-testid="cohort-card"
          >
            <div class="flex justify-between items-baseline mb-3">
              <h2 class="text-base font-bold text-on-surface m-0">{{ c.name }}</h2>
              <span
                v-if="c.archived_at"
                class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-on-surface-variant/10 text-on-surface-variant border border-outline-variant/20"
              >
                Gearchiveerd
              </span>
            </div>
            <div class="flex flex-wrap gap-2 mb-3">
              <span
                v-if="c.year"
                class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container text-on-surface-variant"
              >
Jaar {{ c.year }}
              </span>
              <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container text-on-surface-variant">
                {{ c.student_count }} studenten
              </span>
              <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-surface-container text-on-surface-variant">
                {{ c.course_count }} courses
              </span>
            </div>
            <div
              v-if="!c.archived_at && canWriteCohorts"
              class="flex gap-2 border-t border-outline-variant/10 pt-3 mt-2"
            >
              <button
                class="text-xs text-error hover:text-error/80 font-semibold transition-colors"
                @click.stop="archiveCohort(c)"
                data-testid="archive-btn"
              >
                Archive
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create modal -->
    <div
      v-if="showCreate && canWriteCohorts"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
      @click.self="showCreate = false"
    >
      <div class="glass-panel w-full max-w-md rounded-xl overflow-hidden shadow-2xl">
        <div class="px-6 py-4 border-b border-outline-variant/10 flex justify-between items-center">
          <h2 class="text-lg font-bold text-on-surface m-0">New cohort</h2>
          <button
            class="text-outline hover:text-on-surface transition-colors"
            @click="showCreate = false"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <form @submit.prevent="createCohort" class="p-6 space-y-4">
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Name</label>
            <input
              v-model="createForm.name"
              placeholder="2025 Software Track"
              data-testid="cohort-name-input"
              required
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
            />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Year (optional)</label>
            <input
              v-model.number="createForm.year"
              type="number"
              placeholder="2025"
              min="2000"
              max="2100"
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
            />
          </div>
          <p v-if="createError" class="text-sm text-error">{{ createError }}</p>
          <div class="flex gap-3 pt-2">
            <button
              type="button"
              class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors"
              @click="showCreate = false"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="creating"
              data-testid="submit-cohort"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg disabled:opacity-50 transition-all active:scale-95 shadow-lg shadow-primary/20"
            >
              {{ creating ? 'Creating…' : 'Create cohort' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppShell>
</template>

