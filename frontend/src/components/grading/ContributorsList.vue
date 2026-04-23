<template>
  <section
    class="mb-8 px-5 py-4 bg-surface-container-low rounded-xl border border-outline-variant/10"
    data-testid="contributors-section"
  >
    <h2 class="text-base font-bold text-on-surface m-0 mb-3">
      Contributors ({{ contributors.length }})
    </h2>
    <ul class="list-none p-0 m-0 flex flex-col gap-2">
      <li
        v-for="c in sortedContributors"
        :key="c.id"
        class="flex items-center gap-3 px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/10"
        :data-testid="`contributor-${c.user}`"
      >
        <button
          type="button"
          class="w-9 h-9 rounded-full bg-surface-container-highest text-on-surface border border-outline-variant/20 text-xs font-bold tracking-wide cursor-pointer flex-shrink-0 inline-flex items-center justify-center hover:bg-outline-variant transition-colors"
          :title="`View ${c.user_name || c.user_email}'s profile`"
          @click="goToProfile(c.user)"
        >
          {{ initials(c.user_name || c.user_email) }}
        </button>
        <div class="flex-1 min-w-0 flex flex-col gap-1">
          <div class="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              class="bg-transparent border-none p-0 text-primary cursor-pointer text-sm font-semibold text-left hover:underline"
              @click="goToProfile(c.user)"
              :data-testid="`contributor-link-${c.user}`"
            >
              {{ c.user_name || c.user_email }}
            </button>
            <span
              v-if="c.is_primary_author"
              class="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/15 text-primary border border-primary/20 font-semibold"
            >
              Primary author
            </span>
          </div>
          <div class="flex gap-1.5 flex-wrap">
            <span class="text-[11px] px-1.5 py-0.5 rounded bg-tertiary/15 text-tertiary font-medium">
              {{ formatPct(c.contribution_fraction) }}
            </span>
            <span class="text-[11px] px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant">
              {{ c.commits_count }} commits
            </span>
            <span class="text-[11px] px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant">
              {{ c.lines_changed }} lines
            </span>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { SubmissionContributor } from '@/stores/grading';

const props = defineProps<{
  contributors: SubmissionContributor[];
}>();

const router = useRouter();

const sortedContributors = computed(() =>
  [...props.contributors].sort((a, b) => {
    // Primary author first; then by contribution_fraction desc.
    if (a.is_primary_author !== b.is_primary_author) {
      return a.is_primary_author ? -1 : 1;
    }
    return (b.contribution_fraction ?? 0) - (a.contribution_fraction ?? 0);
  }),
);

function initials(label: string): string {
  if (!label) return '?';
  const parts = label.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 0) return label.slice(0, 2).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function formatPct(fraction: number): string {
  const pct = Math.round((fraction ?? 0) * 100);
  return `${pct}%`;
}

function goToProfile(userId: number) {
  router.push({ name: 'grading-student-profile', params: { id: userId } });
}
</script>

