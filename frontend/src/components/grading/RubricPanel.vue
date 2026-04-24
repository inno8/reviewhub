<template>
  <section class="flex flex-col gap-4" data-testid="rubric-panel">
    <!-- EINDBEOORDELING card -->
    <div
      class="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 flex flex-col gap-3"
      data-testid="rubric-final-card"
    >
      <div class="flex items-start justify-between gap-4">
        <div class="flex flex-col gap-1 min-w-0">
          <span class="text-[11px] uppercase tracking-widest font-semibold text-on-surface-variant">
            Eindbeoordeling
          </span>
          <div class="flex items-baseline gap-1">
            <span
              class="text-4xl font-bold tabular-nums"
              :class="bandFor(weightedAverage).text"
              data-testid="rubric-overall-score"
            >{{ weightedAverage.toFixed(1) }}</span>
            <span class="text-lg text-outline tabular-nums">/ 4.0</span>
          </div>
        </div>
        <span
          :class="['shrink-0 rounded-full px-3 py-1 text-[11px] uppercase tracking-widest font-bold', bandFor(weightedAverage).pill]"
          data-testid="rubric-overall-band"
        >{{ bandFor(weightedAverage).label }}</span>
      </div>
      <!-- Progress bar -->
      <div class="h-2 w-full rounded-full bg-surface-container overflow-hidden">
        <div
          :class="['h-full rounded-full transition-all', bandFor(weightedAverage).bar]"
          :style="{ width: Math.min(100, (weightedAverage / 4) * 100) + '%' }"
        ></div>
      </div>
    </div>

    <!-- Section header -->
    <div class="flex items-center gap-3">
      <h2 class="text-sm font-bold uppercase tracking-widest text-on-surface-variant">
        {{ sectionHeader }}
      </h2>
      <span v-if="!editable" class="text-[11px] text-outline">alleen-lezen</span>
    </div>

    <!-- Criterion cards -->
    <div class="flex flex-col gap-4">
      <div
        v-for="criterion in criteria"
        :key="criterion.id"
        class="rounded-xl border border-outline-variant/10 bg-surface-container-low p-4 flex flex-col gap-3"
        :data-testid="`rubric-card-${criterion.id}`"
      >
        <div class="flex items-start gap-4">
          <!-- Circular score ring -->
          <div
            class="relative shrink-0"
            :title="selectedLevelDescription(criterion) || ''"
          >
            <svg width="56" height="56" viewBox="0 0 56 56" class="-rotate-90">
              <circle
                cx="28"
                cy="28"
                r="24"
                fill="none"
                stroke="currentColor"
                stroke-width="4"
                class="text-surface-container"
              />
              <circle
                cx="28"
                cy="28"
                r="24"
                fill="none"
                :stroke="ringColorFor(scoreFor(criterion.id))"
                stroke-width="4"
                stroke-linecap="round"
                :stroke-dasharray="2 * Math.PI * 24"
                :stroke-dashoffset="ringOffset(scoreFor(criterion.id), maxScoreFor(criterion))"
                class="transition-all"
              />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span
                class="text-sm font-bold tabular-nums"
                :class="bandFor(scoreFor(criterion.id)).text"
              >
                {{ scoreFor(criterion.id) ?? '—' }} / {{ maxScoreFor(criterion) }}
              </span>
            </div>
          </div>

          <!-- Name + weight + pill selector -->
          <div class="flex-1 min-w-0 flex flex-col gap-2">
            <div class="flex items-baseline gap-2 flex-wrap">
              <span
                class="text-base font-semibold text-on-surface truncate"
                :title="criterion.name"
              >{{ criterion.name }}</span>
              <span class="text-xs text-outline tabular-nums">{{ weightLabel(criterion) }}</span>
              <span
                v-if="criterion.kerntaak"
                :title="criterion.kerntaak_label || criterion.kerntaak"
                class="rounded-full bg-surface-container-high px-1.5 py-0.5 font-mono text-[10px] leading-none text-on-surface-variant"
                :data-testid="`kerntaak-${criterion.id}`"
              >{{ criterion.kerntaak }}</span>
            </div>

            <!-- Segmented pill selector: 1 / 2 / 3 / 4 -->
            <div
              class="inline-flex items-stretch rounded-full bg-surface-container border border-outline-variant/15 p-0.5 self-start"
              role="group"
              :aria-label="`Score voor ${criterion.name}`"
              :data-testid="`score-${criterion.id}`"
            >
              <button
                v-for="lvl in pillLevels(criterion)"
                :key="lvl.score"
                type="button"
                :disabled="!editable"
                @click="onScoreChange(criterion.id, lvl.score)"
                :class="[
                  'min-w-[40px] px-3 py-1 text-xs font-bold tabular-nums rounded-full transition-colors',
                  scoreFor(criterion.id) === lvl.score
                    ? bandFor(lvl.score).pill
                    : 'text-on-surface-variant hover:text-on-surface',
                  !editable ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
                ]"
                :data-testid="`score-pill-${criterion.id}-${lvl.score}`"
                :title="lvl.label || ''"
              >{{ lvl.score }}</button>
            </div>
          </div>
        </div>

        <div class="border-t border-outline-variant/10"></div>

        <!-- AI evidence -->
        <p
          v-if="evidenceFor(criterion.id)"
          class="text-[12px] italic leading-relaxed text-on-surface-variant"
          :data-testid="`evidence-${criterion.id}`"
        >
          <span class="not-italic font-semibold text-outline">AI evidence:</span>
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
  courseName?: string | null;
  cohortName?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  editable: true,
  courseName: null,
  cohortName: null,
});
const emit = defineEmits<{
  (e: 'update-score', criterionId: string, score: number): void;
}>();

const FALLBACK_LEVEL_LABELS: Record<number, string> = {
  1: 'Nog niet beheerst',
  2: 'Gedeeltelijk beheerst',
  3: 'Op opleidingsniveau',
  4: 'Boven niveau',
};

function scoreFor(id: string): number | undefined {
  return props.scores?.[id]?.score;
}
function evidenceFor(id: string): string | undefined {
  return props.scores?.[id]?.evidence;
}

function maxScoreFor(c: RubricCriterion): number {
  return c.levels.reduce((max, lvl) => (lvl.score > max ? lvl.score : max), 0) || 4;
}

function onScoreChange(id: string, score: number) {
  if (!props.editable) return;
  emit('update-score', id, score);
}

function levelLabel(lvl: any): string {
  return lvl?.label || FALLBACK_LEVEL_LABELS[lvl?.score] || '';
}

function selectedLevelDescription(c: RubricCriterion): string {
  const score = scoreFor(c.id);
  if (score == null) return '';
  const lvl = c.levels.find((l: any) => l.score === score);
  return (lvl && ((lvl as any).description || (lvl as any).label)) || '';
}

function pillLevels(c: RubricCriterion) {
  // Sort ascending so pills always read 1, 2, 3, 4.
  return [...c.levels]
    .sort((a, b) => a.score - b.score)
    .map(l => ({ score: l.score, label: levelLabel(l) }));
}

const totalWeight = computed(() => {
  const sum = props.criteria.reduce((acc, c) => acc + (c.weight ?? 1), 0);
  return sum > 0 ? sum : props.criteria.length || 1;
});

function weightLabel(c: RubricCriterion): string {
  const w = c.weight ?? 1;
  const pct = Math.round((w / totalWeight.value) * 100);
  return `${pct}%`;
}

const weightedAverage = computed(() => {
  let weightedSum = 0;
  let weightUsed = 0;
  for (const c of props.criteria) {
    const s = scoreFor(c.id);
    if (s == null) continue;
    const w = c.weight ?? 1;
    weightedSum += s * w;
    weightUsed += w;
  }
  if (weightUsed === 0) return 0;
  return weightedSum / weightUsed;
});

const sectionHeader = computed(() => {
  const courseLabel = (props.courseName || 'Rubriek').toUpperCase();
  const hay = `${props.cohortName || ''} ${props.courseName || ''}`;
  const yearMatch = /(?:\b|_)(?:jaar\s*2|j2|q2)(?:\b|_)/i.test(hay);
  const base = `Rubriek — ${courseLabel}`;
  return yearMatch ? `${base} — Rubriek J2` : base;
});

/**
 * Score bands per spec:
 *   score < 2           → error (red)      ONVOLDOENDE
 *   2 <= score < 3      → tertiary (amber) NET AAN
 *   3 <= score < 3.5    → primary (blue)   VOLDOENDE
 *   score >= 3.5        → emerald (green)  GOED
 * No `success` token exists; emerald is hard-coded (same pattern as old panel).
 */
interface Band {
  label: string;
  text: string;
  pill: string;
  bar: string;
  ring: string; // stroke color
}

const BAND_NONE: Band = {
  label: '—',
  text: 'text-on-surface-variant',
  pill: 'bg-surface-container text-on-surface-variant',
  bar: 'bg-outline-variant',
  ring: 'rgba(139, 145, 157, 0.5)', // outline
};

function bandFor(score: number | undefined): Band {
  if (score == null || score === 0) return BAND_NONE;
  if (score < 2) {
    return {
      label: 'Onvoldoende',
      text: 'text-error',
      pill: 'bg-error/20 text-error',
      bar: 'bg-error',
      ring: '#ffb4ab',
    };
  }
  if (score < 3) {
    return {
      label: 'Net aan',
      text: 'text-tertiary',
      pill: 'bg-tertiary/20 text-tertiary',
      bar: 'bg-tertiary',
      ring: '#ffba42',
    };
  }
  if (score < 3.5) {
    return {
      label: 'Voldoende',
      text: 'text-primary',
      pill: 'bg-primary/20 text-primary',
      bar: 'bg-primary',
      ring: '#a2c9ff',
    };
  }
  return {
    label: 'Goed',
    text: 'text-emerald-300',
    pill: 'bg-emerald-900/40 text-emerald-300',
    bar: 'bg-emerald-400',
    ring: '#6ee7b7',
  };
}

function ringColorFor(score: number | undefined): string {
  return bandFor(score).ring;
}

function ringOffset(score: number | undefined, max: number): number {
  const C = 2 * Math.PI * 24;
  if (score == null || score === 0) return C;
  const frac = Math.min(1, Math.max(0, score / (max || 4)));
  return C * (1 - frac);
}
</script>
