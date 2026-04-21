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
import AppShell from '@/components/layout/AppShell.vue';

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
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-4xl mx-auto">
        <header class="flex items-start gap-4 mb-8">
          <button
            class="text-sm text-on-surface-variant hover:text-on-surface transition-colors mt-1"
            @click="goToCohort"
          >
            ← Cohort
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
        <div
          v-else-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >
          {{ error }}
        </div>
        <div v-else-if="course" class="flex flex-col gap-6">
          <section class="bg-surface-container-low rounded-xl border border-outline-variant/10 overflow-hidden">
            <div class="flex justify-between items-center px-6 py-4 border-b border-outline-variant/10">
              <h2 class="text-base font-bold text-on-surface m-0">Details</h2>
              <button
                v-if="!course.archived_at"
                class="text-xs text-error hover:text-error/80 font-semibold transition-colors"
                @click="archive"
              >
                Archive
              </button>
            </div>

            <dl class="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-3 px-6 py-5 text-sm">
              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Owner</dt>
              <dd class="m-0 text-on-surface">{{ course.owner_email }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Rubric</dt>
              <dd class="m-0 text-on-surface">{{ course.rubric_name || '— (no rubric assigned)' }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Source control</dt>
              <dd class="m-0 text-on-surface">{{ course.source_control_type }}</dd>

              <dt class="font-bold uppercase tracking-widest text-[10px] text-outline self-center">Created</dt>
              <dd class="m-0 text-on-surface">{{ new Date(course.created_at).toLocaleDateString() }}</dd>
            </dl>

            <div
              v-if="!course.archived_at && auth.isSchoolAdmin"
              class="px-6 py-5 border-t border-outline-variant/10"
            >
              <h3 class="text-xs font-bold uppercase tracking-widest text-outline mb-3">Edit</h3>
              <form @submit.prevent="save" class="space-y-4">
                <div class="space-y-1.5">
                  <label class="text-xs font-bold uppercase tracking-widest text-outline">Name</label>
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
            </div>
          </section>
        </div>
      </div>
    </div>
  </AppShell>
</template>

