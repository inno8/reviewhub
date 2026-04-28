<script setup lang="ts">
/**
 * TeacherStudentListView — /grading/students
 *
 * Roster-oriented list of every student this teacher is responsible for,
 * across all their cohorts. Different from /grading (PR-queue-oriented).
 *
 * Each card → /grading/students/:id (TeacherStudentProfileView).
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';

interface StudentRow {
  id: number;
  email: string;
  name: string;
  handle: string | null;
  cohort_id: number;
  cohort_name: string;
  pr_count: number;
  prs_waiting_feedback: number;
  avg_score: number | null;
}

const router = useRouter();
const rows = ref<StudentRow[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const search = ref('');
const cohortFilter = ref<number | 'all'>('all');

onMounted(async () => {
  try {
    const { data } = await api.grading.students.list();
    rows.value = data?.results || [];
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Kon studenten niet laden.';
  } finally {
    loading.value = false;
  }
});

const cohorts = computed(() => {
  const seen = new Map<number, string>();
  for (const r of rows.value) {
    if (!seen.has(r.cohort_id)) seen.set(r.cohort_id, r.cohort_name);
  }
  return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
});

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  return rows.value.filter((r) => {
    if (cohortFilter.value !== 'all' && r.cohort_id !== cohortFilter.value) {
      return false;
    }
    if (!q) return true;
    return (
      (r.name || '').toLowerCase().includes(q)
      || (r.email || '').toLowerCase().includes(q)
      || (r.handle || '').toLowerCase().includes(q)
    );
  });
});

function initials(name: string, email: string): string {
  const src = (name || email || '?').trim();
  const parts = src.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return src.slice(0, 2).toUpperCase();
}

function open(id: number) {
  router.push({ name: 'grading-student-profile', params: { id } });
}

function metaLine(r: StudentRow): string {
  const total = r.pr_count || 0;
  const waiting = r.prs_waiting_feedback || 0;
  const totalLabel = `${total} PR${total === 1 ? '' : 's'} total`;
  return `${totalLabel} · ${waiting} wachten`;
}
</script>

<template>
  <AppShell>
    <div class="p-6 flex-1">
      <div class="max-w-[1200px] mx-auto flex flex-col gap-5">
        <header class="flex flex-col gap-1">
          <h1 class="text-2xl font-bold text-on-surface m-0">Studenten</h1>
          <p class="text-sm text-on-surface-variant m-0">
            Alle studenten in jouw klassen — klik voor het volledige profiel.
          </p>
        </header>

        <!-- Filters -->
        <div class="flex flex-wrap items-center gap-3">
          <div class="relative flex-1 min-w-[220px] max-w-[320px]">
            <span
              class="material-symbols-outlined text-lg text-outline absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            >search</span>
            <input
              v-model="search"
              type="search"
              placeholder="Zoek op naam of e-mail…"
              class="w-full pl-10 pr-3 py-2 rounded-lg bg-surface-container-lowest border border-outline-variant/20 text-sm text-on-surface focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
          </div>
          <select
            v-model="cohortFilter"
            class="bg-surface-container-lowest border border-outline-variant/20 rounded-lg text-sm text-on-surface px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary/50"
          >
            <option value="all">Alle klassen</option>
            <option v-for="c in cohorts" :key="c.id" :value="c.id">
              {{ c.name }}
            </option>
          </select>
          <span class="text-xs text-outline ml-auto tabular-nums">
            {{ filtered.length }} / {{ rows.length }} studenten
          </span>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="n in 6"
            :key="n"
            class="h-36 rounded-xl bg-surface-container-low animate-pulse"
          ></div>
        </div>

        <!-- Error -->
        <div
          v-else-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >{{ error }}</div>

        <!-- Empty -->
        <div
          v-else-if="!rows.length"
          class="bg-surface-container-low border border-outline-variant/10 rounded-xl p-10 text-center flex flex-col gap-2"
        >
          <span
            class="material-symbols-outlined text-4xl text-outline mx-auto"
            aria-hidden="true"
          >person</span>
          <p class="text-on-surface font-semibold m-0">
            Nog geen studenten om weer te geven.
          </p>
          <p class="text-sm text-on-surface-variant m-0">
            Vraag je schoolbeheerder om studenten aan je klas te koppelen.
          </p>
        </div>

        <!-- Filtered empty -->
        <div
          v-else-if="!filtered.length"
          class="text-sm text-outline py-6 text-center"
        >
          Geen studenten gevonden met deze filter.
        </div>

        <!-- Grid -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <button
            v-for="r in filtered"
            :key="r.id"
            type="button"
            @click="open(r.id)"
            class="text-left bg-surface-container-low p-5 rounded-xl border border-outline-variant/10 hover:border-primary/40 hover:bg-surface-container transition-colors flex flex-col gap-4"
            :data-testid="`student-card-${r.id}`"
          >
            <div class="flex items-center gap-3">
              <div
                class="w-11 h-11 rounded-full bg-surface-container-highest text-on-surface-variant flex items-center justify-center shrink-0 font-bold text-sm"
              >
                {{ initials(r.name, r.email) }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-bold text-on-surface truncate">
                  {{ r.name || r.email }}
                </div>
                <div class="text-xs text-on-surface-variant truncate">
                  <span v-if="r.handle">@{{ r.handle }} · </span>{{ r.email }}
                </div>
              </div>
            </div>

            <div class="flex flex-wrap gap-1.5">
              <span
                class="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-md bg-primary/15 text-primary"
              >
                {{ r.cohort_name }}
              </span>
            </div>

            <div class="flex items-center justify-between pt-2 border-t border-outline-variant/10">
              <span
                class="text-xs font-medium"
                :class="r.prs_waiting_feedback > 0 ? 'text-primary' : 'text-on-surface-variant'"
              >
                {{ metaLine(r) }}
              </span>
              <span class="text-primary text-sm font-medium whitespace-nowrap">
                Bekijk profiel →
              </span>
            </div>
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>
