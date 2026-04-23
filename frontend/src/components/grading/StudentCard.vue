<script setup lang="ts">
/**
 * StudentCard — card tile used in the grading inbox student browser.
 *
 * Matches the project-card pattern from DashboardView (teacher view):
 *   bg-surface-container-low / border-outline-variant/10 / rounded-xl
 *   hover:border-primary/40 / hover:bg-surface-container
 *
 * Avatar: renders `avatarUrl` when present, else shows a `person`
 * material-symbols-outlined fallback inside a circular container.
 */
import { computed } from 'vue';

interface Props {
  name: string;
  email: string;
  avatarUrl?: string | null;
  cohortNames?: string[];
  courseNames?: string[];
  pendingCount?: number;
}

const props = withDefaults(defineProps<Props>(), {
  avatarUrl: null,
  cohortNames: () => [],
  courseNames: () => [],
  pendingCount: 0,
});

const initials = computed(() => {
  const source = (props.name || props.email || '?').trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
});

const pendingLabel = computed(() => {
  const n = props.pendingCount || 0;
  if (n === 0) return 'Geen PRs wachtend';
  if (n === 1) return '1 PR wacht op feedback';
  return `${n} PRs wachten op feedback`;
});
</script>

<template>
  <div
    class="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 hover:border-primary/40 hover:bg-surface-container transition-colors cursor-pointer flex flex-col gap-4"
  >
    <div class="flex items-center gap-3">
      <div
        class="w-12 h-12 rounded-full bg-surface-container-highest text-on-surface-variant flex items-center justify-center shrink-0 overflow-hidden"
      >
        <img
          v-if="avatarUrl"
          :src="avatarUrl"
          :alt="name || email"
          class="w-full h-full object-cover"
          data-testid="student-avatar-img"
        />
        <span
          v-else
          class="material-symbols-outlined text-2xl"
          data-testid="student-avatar-icon"
        >
          person
        </span>
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-sm font-bold text-on-surface truncate">{{ name || email }}</div>
        <div class="text-xs text-on-surface-variant truncate">{{ email }}</div>
      </div>
    </div>

    <div
      v-if="cohortNames.length || courseNames.length"
      class="flex flex-wrap gap-1.5"
    >
      <span
        v-for="c in cohortNames"
        :key="`cohort-${c}`"
        class="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-md bg-primary/15 text-primary"
      >
        {{ c }}
      </span>
      <span
        v-for="c in courseNames"
        :key="`course-${c}`"
        class="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-md bg-tertiary/20 text-tertiary"
      >
        {{ c }}
      </span>
    </div>

    <div class="flex items-center justify-between pt-2 border-t border-outline-variant/10">
      <span
        class="text-xs font-medium"
        :class="pendingCount > 0 ? 'text-primary' : 'text-on-surface-variant'"
      >
        {{ pendingLabel }}
      </span>
      <span class="text-primary text-sm font-medium whitespace-nowrap">Bekijk →</span>
    </div>
  </div>
</template>
