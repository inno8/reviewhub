<template>
  <div
    class="flex items-center gap-3 rounded-xl border border-outline-variant/10 bg-surface-container-low px-4 py-3"
    data-testid="student-header-chip"
  >
    <!-- Avatar circle with initials -->
    <div
      class="h-12 w-12 shrink-0 rounded-full bg-surface-container-high flex items-center justify-center text-sm font-bold text-on-surface-variant select-none"
      :aria-label="name"
    >
      {{ initials }}
    </div>

    <!-- Name + handle + subtitle -->
    <div class="min-w-0 flex-1">
      <div class="flex items-baseline gap-2 min-w-0">
        <span class="font-bold text-on-surface truncate">{{ name }}</span>
        <span class="text-xs text-outline truncate">@{{ handle }}</span>
      </div>
      <div class="flex items-center gap-2 mt-0.5 min-w-0">
        <span class="text-xs text-on-surface-variant truncate">{{ opleidingLabel }}</span>
        <span
          v-if="branch"
          class="inline-flex items-center rounded-full bg-surface-container-high px-2 py-0.5 font-mono text-[10px] leading-none text-on-surface-variant max-w-[180px] truncate"
          :title="branch"
        >{{ truncatedBranch }}</span>
      </div>
    </div>

    <!-- Full profile link -->
    <router-link
      v-if="studentId"
      :to="{ name: 'grading-student-profile', params: { id: studentId } }"
      class="shrink-0 text-xs text-primary hover:underline whitespace-nowrap"
      data-testid="student-chip-profile-link"
    >
      Volledig profiel bekijken →
    </router-link>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  name: string;
  email: string;
  branch?: string | null;
  studentId?: number | null;
  cohortName?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  branch: null,
  studentId: null,
  cohortName: null,
});

const handle = computed(() => {
  const local = (props.email || '').split('@')[0] || '';
  return local.replace(/\./g, '-') || 'student';
});

const initials = computed(() => {
  const source = (props.name || props.email || '').trim();
  if (!source) return '?';
  const parts = source.split(/[\s@.-]+/).filter(Boolean);
  if (parts.length === 0) return source.slice(0, 2).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
});

const opleidingLabel = computed(() => {
  // v1: hardcoded. Later: pull from cohort metadata / user profile.
  // If cohort name looks like it carries year info ("Jaar 2" / "J2"), keep default.
  return 'Software Ontwikkelen — Jaar 2';
});

const truncatedBranch = computed(() => {
  const b = props.branch || '';
  return b.length > 20 ? b.slice(0, 19) + '…' : b;
});
</script>
