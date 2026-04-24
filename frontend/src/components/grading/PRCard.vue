<script setup lang="ts">
/**
 * PRCard — card tile for one GradingSession (one PR) in the student PR list.
 *
 * Matches the same project-card pattern as StudentCard for visual consistency
 * across the Leera grading flow.
 */
import { computed } from 'vue';

interface Props {
  prNumber: number | null;
  prTitle: string;
  repoFullName: string | null;
  state: string;
  submittedAt: string | null;
  gradedAt?: string | null;
  rubricScoreAvg?: number | null;
  courseName?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  gradedAt: null,
  rubricScoreAvg: null,
  courseName: null,
});

interface StateMeta {
  label: string;
  cls: string;
}

const STATE_META: Record<string, StateMeta> = {
  pending: { label: 'In afwachting', cls: 'bg-surface-container text-on-surface-variant' },
  drafting: { label: 'Concept wordt gemaakt', cls: 'bg-surface-container text-on-surface-variant' },
  drafted: { label: 'Klaar voor review', cls: 'bg-primary/15 text-primary' },
  reviewing: { label: 'Bezig met nakijken', cls: 'bg-tertiary/20 text-tertiary' },
  sending: { label: 'Versturen…', cls: 'bg-tertiary/20 text-tertiary' },
  posted: { label: 'Feedback verstuurd', cls: 'bg-primary-container/15 text-primary-container' },
  partial: { label: 'Deels verstuurd', cls: 'bg-tertiary/20 text-tertiary' },
  failed: { label: 'Mislukt', cls: 'bg-error/15 text-error' },
  discarded: { label: 'Verwijderd', cls: 'bg-surface-container text-on-surface-variant' },
};

const stateMeta = computed<StateMeta>(() => {
  return STATE_META[props.state] || { label: props.state, cls: 'bg-surface-container text-on-surface-variant' };
});

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('nl-NL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

const submittedLabel = computed(() => formatDate(props.submittedAt));
</script>

<template>
  <div
    class="bg-surface-container-low p-6 rounded-xl border border-outline-variant/10 hover:border-primary/40 hover:bg-surface-container transition-colors cursor-pointer flex flex-col gap-3"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex-1 min-w-0">
        <div class="text-sm font-bold text-on-surface truncate">
          {{ prTitle || 'Geen PR-titel' }}
          <span v-if="prNumber" class="text-on-surface-variant font-medium"> #{{ prNumber }}</span>
        </div>
        <div v-if="repoFullName" class="text-xs text-on-surface-variant truncate mt-0.5">
          {{ repoFullName }}
        </div>
      </div>
      <span
        class="text-[10px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-md whitespace-nowrap"
        :class="stateMeta.cls"
      >
        {{ stateMeta.label }}
      </span>
    </div>

    <div
      class="flex items-center justify-between pt-3 border-t border-outline-variant/10 text-xs text-on-surface-variant gap-3 flex-wrap"
    >
      <div class="flex items-center gap-3 flex-wrap">
        <span v-if="courseName" class="font-medium text-on-surface">{{ courseName }}</span>
        <span v-if="courseName" class="opacity-40">·</span>
        <span>Ingediend {{ submittedLabel }}</span>
        <template v-if="rubricScoreAvg !== null && rubricScoreAvg !== undefined">
          <span class="opacity-40">·</span>
          <!--
            Backend rubric_score_avg is the mean of 1-4 criterion scores
            (see grading/views_student_intelligence.StudentPRHistoryView).
            Show as "x.x/4" so the denominator matches what the teacher
            sees in the rubric panel.
          -->
          <span class="text-on-surface font-semibold">{{ rubricScoreAvg.toFixed(1) }}/4</span>
        </template>
      </div>
      <span class="text-primary font-medium whitespace-nowrap">Open →</span>
    </div>
  </div>
</template>
