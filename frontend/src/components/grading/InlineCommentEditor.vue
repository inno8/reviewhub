<template>
  <div
    class="rounded-xl border border-outline-variant/20 bg-surface-container-low p-4 flex flex-col gap-3"
    :data-testid="`inline-comment-editor-${index}`"
  >
    <header class="flex flex-wrap items-center gap-2">
      <span
        class="material-symbols-rounded text-base text-primary"
        aria-hidden="true"
      >chat_bubble</span>
      <code class="font-mono text-xs text-primary bg-surface-container px-2 py-0.5 rounded">
        {{ comment.file }}:{{ comment.line }}
      </code>
      <span
        v-if="comment.suggested_snippet"
        class="px-2 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] uppercase tracking-widest font-semibold"
        :data-testid="`suggestion-badge-${index}`"
        title="Bevat een voorgestelde code-fix"
      >Suggestion</span>
      <span v-if="dirty" class="ml-auto text-[11px] text-tertiary">niet opgeslagen</span>
      <button
        v-if="editable"
        type="button"
        @click="$emit('remove')"
        class="text-[11px] text-error hover:text-error/80 bg-transparent border-none cursor-pointer transition-colors"
        :class="{ 'ml-auto': !dirty }"
        :data-testid="`remove-comment-${index}`"
      >Verwijder</button>
    </header>

    <!-- Comment body -->
    <div class="flex flex-col gap-1">
      <label
        :for="`comment-body-${index}`"
        class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
      >Commentaar</label>
      <textarea
        :id="`comment-body-${index}`"
        v-model="draftBody"
        :disabled="!editable"
        rows="3"
        class="w-full rounded-md border border-outline-variant/20 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-60"
        :data-testid="`comment-body-${index}`"
        placeholder="Bewerk de feedback voor de student…"
      ></textarea>
    </div>

    <!-- Original + suggested side-by-side -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <!-- Original snippet (readonly, error tint) -->
      <div class="flex flex-col gap-1" :data-testid="`original-snippet-${index}`">
        <label
          class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
        >Originele code</label>
        <div class="rounded-md border border-error/40 bg-surface-container-lowest p-2">
          <textarea
            v-if="hasOriginal"
            :value="draftOriginal"
            readonly
            rows="4"
            class="w-full bg-transparent border-0 text-on-surface text-[13px] leading-relaxed focus:outline-none resize-y"
            :style="codeFontStyle"
          ></textarea>
          <textarea
            v-else
            v-model="draftOriginal"
            :disabled="!editable"
            rows="4"
            class="w-full bg-transparent border-0 text-on-surface text-[13px] leading-relaxed focus:outline-none resize-y disabled:opacity-60 placeholder:text-outline/60"
            :style="codeFontStyle"
            placeholder="Geen snippet van de LLM — plak hier eventueel de relevante code"
          ></textarea>
        </div>
      </div>

      <!-- Suggested snippet (editable, primary tint) -->
      <div class="flex flex-col gap-1" :data-testid="`suggested-snippet-${index}`">
        <label
          :for="`suggested-snippet-${index}`"
          class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
        >Voorgestelde code</label>
        <div class="rounded-md border border-primary/40 bg-surface-container-lowest p-2">
          <textarea
            :id="`suggested-snippet-${index}`"
            v-model="draftSuggested"
            :disabled="!editable"
            rows="4"
            class="w-full bg-transparent border-0 text-on-surface text-[13px] leading-relaxed focus:outline-none resize-y disabled:opacity-60 placeholder:text-outline/60"
            :style="codeFontStyle"
            placeholder="Typ een voorstel om de student een one-click fix te geven."
          ></textarea>
        </div>
        <button
          v-if="editable"
          type="button"
          @click="copyOriginalToSuggested"
          :disabled="!draftOriginal"
          class="self-end text-[11px] text-primary/80 hover:text-primary disabled:opacity-40 disabled:cursor-not-allowed bg-transparent border-none cursor-pointer"
        >↓ Kopieer originele naar voorstel</button>
      </div>
    </div>

    <!-- Teacher explanation -->
    <div class="flex flex-col gap-1">
      <label
        :for="`teacher-explanation-${index}`"
        class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
      >Extra toelichting (optioneel)</label>
      <textarea
        :id="`teacher-explanation-${index}`"
        v-model="draftExplanation"
        :disabled="!editable"
        rows="2"
        class="w-full rounded-md border border-outline-variant/20 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-60 placeholder:text-outline/60"
        placeholder="Voeg een korte uitleg toe voor de student…"
      ></textarea>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

interface CommentShape {
  file: string;
  line: number;
  body: string;
  original_snippet?: string;
  suggested_snippet?: string;
  teacher_explanation?: string;
}

interface Props {
  comment: CommentShape;
  index: number;
  editable?: boolean;
}

const props = withDefaults(defineProps<Props>(), { editable: true });
const emit = defineEmits<{
  (e: 'update', patch: Partial<CommentShape>): void;
  (e: 'remove'): void;
}>();

const draftBody = ref(props.comment.body ?? '');
const draftOriginal = ref(props.comment.original_snippet ?? '');
const draftSuggested = ref(props.comment.suggested_snippet ?? '');
const draftExplanation = ref(props.comment.teacher_explanation ?? '');

const hasOriginal = computed(() => (props.comment.original_snippet ?? '').length > 0);

const dirty = computed(
  () =>
    draftBody.value !== (props.comment.body ?? '')
    || draftOriginal.value !== (props.comment.original_snippet ?? '')
    || draftSuggested.value !== (props.comment.suggested_snippet ?? '')
    || draftExplanation.value !== (props.comment.teacher_explanation ?? ''),
);

// Emit edits up to the parent on every change so the parent's dirty
// flag / autosave pipeline runs against the latest values.
watch(draftBody, (v) => emit('update', { body: v }));
watch(draftOriginal, (v) => emit('update', { original_snippet: v }));
watch(draftSuggested, (v) => emit('update', { suggested_snippet: v }));
watch(draftExplanation, (v) => emit('update', { teacher_explanation: v }));

// Keep drafts in sync if the parent replaces the comment (e.g. after load).
watch(
  () => props.comment,
  (next) => {
    draftBody.value = next.body ?? '';
    draftOriginal.value = next.original_snippet ?? '';
    draftSuggested.value = next.suggested_snippet ?? '';
    draftExplanation.value = next.teacher_explanation ?? '';
  },
  { deep: false },
);

function copyOriginalToSuggested() {
  if (!props.editable) return;
  draftSuggested.value = draftOriginal.value;
}

// Fira Code per DESIGN.md §5.2 for code snippets.
const codeFontStyle = {
  fontFamily: '"Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace',
};
</script>
