<template>
  <section
    class="rounded-xl border border-outline-variant/10 bg-surface-container-low p-4"
    data-testid="rubric-panel"
  >
    <header class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-bold uppercase tracking-widest text-on-surface-variant">
        Beoordeling
      </h2>
      <span v-if="!editable" class="text-[11px] text-outline">alleen-lezen</span>
    </header>
    <div
      class="grid gap-3"
      :class="gridColsClass"
    >
      <div
        v-for="criterion in criteria"
        :key="criterion.id"
        :class="[
          'rounded-lg border p-3 flex flex-col gap-2 min-w-0',
          tintFor(scoreFor(criterion.id)).container,
        ]"
        :data-testid="`rubric-card-${criterion.id}`"
      >
        <div class="flex items-center justify-between gap-2">
          <span
            class="text-sm font-semibold text-on-surface truncate"
            :title="criterion.name"
          >{{ criterion.name }}</span>
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-bold tabular-nums',
              tintFor(scoreFor(criterion.id)).badge,
            ]"
          >
            {{ scoreFor(criterion.id) ?? '—' }} / {{ maxScoreFor(criterion) }}
          </span>
        </div>

        <select
          v-if="editable"
          :value="scoreFor(criterion.id)"
          @change="onScoreChange(criterion.id, ($event.target as HTMLSelectElement).value)"
          class="w-full rounded-md border border-outline-variant/20 bg-surface-container px-2 py-1 text-xs text-on-surface focus:outline-none focus:ring-1 focus:ring-primary/50"
          :data-testid="`score-${criterion.id}`"
        >
          <option
            v-for="lvl in criterion.levels"
            :key="lvl.score"
            :value="lvl.score"
          >
            {{ lvl.score }}{{ lvl.description ? ' — ' + truncate(lvl.description, 32) : '' }}
          </option>
        </select>

        <p
          v-if="evidenceFor(criterion.id)"
          class="text-[11px] italic leading-relaxed text-on-surface-variant line-clamp-3"
          :title="evidenceFor(criterion.id) || ''"
        >
          {{ evidenceFor(criterion.id) }}
        </p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { RubricCriterion } from '@/stores/grading';

interface ScoreEntry {
  score: number;
  evidence?: string;
}

interface Props {
  criteria: RubricCriterion[];
  scores: Record<string, ScoreEntry>;
  editable?: boolean;
}

const props = withDefaults(defineProps<Props>(), { editable: true });
const emit = defineEmits<{
  (e: 'update-score', criterionId: string, score: number): void;
}>();

function scoreFor(id: string): number | undefined {
  return props.scores?.[id]?.score;
}
function evidenceFor(id: string): string | undefined {
  return props.scores?.[id]?.evidence;
}

function maxScoreFor(c: RubricCriterion): number {
  return c.levels.reduce((max, lvl) => (lvl.score > max ? lvl.score : max), 0) || 4;
}

function onScoreChange(id: string, raw: string) {
  const v = parseInt(raw, 10);
  if (!Number.isNaN(v)) emit('update-score', id, v);
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length <= max ? text : text.slice(0, max - 1) + '…';
}

/**
 * Color map: 1/4 → error, 2/4 → warning (tertiary/amber), 3/4 → neutral,
 * 4/4 → primary. Tints use opacity for DESIGN.md §4 semantic compliance.
 */
function tintFor(score: number | undefined): { container: string; badge: string } {
  if (score == null) {
    return {
      container: 'border-outline-variant/20 bg-surface-container/40',
      badge: 'bg-surface-container text-on-surface-variant',
    };
  }
  if (score <= 1) {
    return {
      container: 'border-error/40 bg-error/10',
      badge: 'bg-error/20 text-error',
    };
  }
  if (score === 2) {
    return {
      container: 'border-tertiary/40 bg-tertiary/10',
      badge: 'bg-tertiary/20 text-tertiary',
    };
  }
  if (score === 3) {
    return {
      container: 'border-outline-variant/30 bg-surface-container/60',
      badge: 'bg-surface-container-high text-on-surface',
    };
  }
  return {
    container: 'border-primary/40 bg-primary/10',
    badge: 'bg-primary/20 text-primary',
  };
}

const gridColsClass = computed(() => {
  const n = props.criteria?.length || 0;
  if (n <= 1) return 'grid-cols-1';
  if (n === 2) return 'grid-cols-1 sm:grid-cols-2';
  if (n === 3) return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3';
  return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';
});
</script>
