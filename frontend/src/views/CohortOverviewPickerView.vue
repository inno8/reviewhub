<script setup lang="ts">
/**
 * CohortOverviewPickerView — /grading/klas-overzicht
 *
 * Nav shim between the sidebar "Klas-overzicht" button and the real
 * per-cohort overview at /grading/cohorts/:id/overview.
 *
 * Behaviour:
 *   - 1 cohort  → immediate router.replace to /grading/cohorts/<id>/overview
 *   - 2+ cohorts → small picker list with student counts
 *   - 0 cohorts → empty state
 *
 * Teachers in the seeded demo data usually have exactly one cohort, so the
 * picker is mostly defensive — but it keeps the UI honest for teachers who
 * teach multiple klassen.
 */
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';

interface Cohort {
  id: number;
  name: string;
  year?: string | null;
  student_count?: number;
}

const router = useRouter();
const cohorts = ref<Cohort[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    const { data } = await api.grading.cohorts.list();
    const list = Array.isArray(data) ? data : (data.results || []);
    cohorts.value = list;
    if (list.length === 1) {
      router.replace(`/grading/cohorts/${list[0].id}/overview`);
      return;
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Kon klassen niet laden.';
  } finally {
    loading.value = false;
  }
});

function open(id: number) {
  router.push(`/grading/cohorts/${id}/overview`);
}
</script>

<template>
  <AppShell>
    <div class="p-6 flex-1">
      <div class="max-w-[1100px] mx-auto flex flex-col gap-6">
        <header class="flex flex-col gap-1">
          <h1 class="text-2xl font-bold text-on-surface m-0">Klas-overzicht</h1>
          <p class="text-sm text-on-surface-variant m-0">
            Kies een klas om het overzicht te openen.
          </p>
        </header>

        <div v-if="loading" class="flex flex-col gap-2">
          <div
            v-for="n in 3"
            :key="n"
            class="h-20 rounded-xl bg-surface-container-low animate-pulse"
          ></div>
        </div>

        <div
          v-else-if="error"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >{{ error }}</div>

        <div
          v-else-if="!cohorts.length"
          class="bg-surface-container-low border border-outline-variant/10 rounded-xl p-10 text-center flex flex-col gap-2"
        >
          <span
            class="material-symbols-outlined text-4xl text-outline mx-auto"
            aria-hidden="true"
          >groups_2</span>
          <p class="text-on-surface font-semibold m-0">
            Je hebt nog geen klas toegewezen
          </p>
          <p class="text-sm text-on-surface-variant m-0">
            Vraag je schoolbeheerder om je aan een klas te koppelen.
          </p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            v-for="c in cohorts"
            :key="c.id"
            type="button"
            @click="open(c.id)"
            class="text-left bg-surface-container-low border border-outline-variant/10 hover:border-primary/40 hover:bg-surface-container rounded-xl p-5 flex flex-col gap-3 transition-colors"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="flex flex-col min-w-0">
                <span class="text-base font-bold text-on-surface truncate">
                  {{ c.name }}
                </span>
                <span v-if="c.year" class="text-xs text-on-surface-variant">
                  {{ c.year }}
                </span>
              </div>
              <span
                class="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-widest bg-primary/15 text-primary shrink-0"
              >
                {{ c.student_count ?? 0 }} studenten
              </span>
            </div>
            <span class="text-primary text-sm font-medium">
              Open klas-overzicht →
            </span>
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>
