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
        :class="[
          'text-[11px] text-error hover:text-error/80 bg-transparent border-none cursor-pointer transition-colors',
          dirty ? '' : 'ml-auto',
        ]"
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

    <!-- Text-only chip (when both snippets are empty) -->
    <div
      v-if="isTextOnly"
      class="flex items-center gap-1.5 self-start rounded-full bg-surface-container px-2.5 py-1 text-[10px] uppercase tracking-widest font-semibold text-on-surface-variant"
      :data-testid="`text-only-chip-${index}`"
    >
      <span class="material-symbols-rounded text-[14px]" aria-hidden="true">edit_note</span>
      <span>Tekstuele feedback</span>
    </div>

    <!-- Inline Shiki-highlighted snippets: side-by-side on md+, stacked on narrow -->
    <div v-else class="flex flex-col gap-2">
      <div
        :class="[
          'grid gap-4',
          hasOriginal && hasSuggested ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1',
        ]"
      >
        <!-- Original snippet (red accent) -->
        <div
          v-if="hasOriginal"
          class="flex flex-col gap-1 min-w-0"
          :data-testid="`original-snippet-${index}`"
        >
          <label
            class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
          >Originele code</label>
          <div
            class="rounded-md border-l-2 border border-red-500/50 bg-surface-container-lowest overflow-hidden max-h-[40vh] overflow-y-auto"
          >
            <div
              v-if="originalHtml"
              class="inline-code"
              v-html="originalHtml"
            ></div>
            <pre
              v-else
              class="p-3 text-[13px] leading-relaxed text-on-surface-variant whitespace-pre-wrap break-words m-0"
              :style="codeFontStyle"
            >{{ draftOriginal }}</pre>
          </div>
        </div>

        <!-- Suggested snippet (green accent).
             Editable for the docent: textarea when editable=true so the
             docent can rewrite the AI's proposal before sending. The
             syntax-highlighted shiki version only shows for the student's
             read-only view (after Send) — see suggestedHtml computed. -->
        <div
          v-if="hasSuggested || editable"
          class="flex flex-col gap-1 min-w-0"
          :data-testid="`suggested-snippet-${index}`"
        >
          <label
            :for="`suggested-snippet-${index}`"
            class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
          >Voorgestelde code</label>
          <div
            class="rounded-md border-l-2 border border-emerald-500/50 bg-surface-container-lowest overflow-hidden max-h-[40vh] overflow-y-auto"
          >
            <!-- Editable docent view: textarea pre-filled with the AI's
                 suggestion. Same monospace styling as the highlighted
                 version below; live-updates via watch in the script. -->
            <textarea
              v-if="editable"
              :id="`suggested-snippet-${index}`"
              v-model="draftSuggested"
              rows="6"
              class="w-full block bg-transparent border-0 text-[13px] leading-relaxed text-on-surface p-3 resize-y focus:outline-none placeholder:text-outline/60"
              :style="codeFontStyle"
              placeholder="Geen suggestie van de LLM. Typ hier je eigen voorstel om de student een fix aan te bieden, of laat leeg om alleen tekstuele feedback te sturen."
              :data-testid="`suggested-snippet-textarea-${index}`"
            ></textarea>
            <!-- Read-only student view: syntax-highlighted html when shiki
                 produced it, plain pre as fallback. -->
            <template v-else>
              <div
                v-if="suggestedHtml"
                class="inline-code"
                v-html="suggestedHtml"
              ></div>
              <pre
                v-else
                class="p-3 text-[13px] leading-relaxed text-on-surface-variant whitespace-pre-wrap break-words m-0"
                :style="codeFontStyle"
              >{{ draftSuggested }}</pre>
            </template>
          </div>
        </div>
      </div>
      <button
        v-if="editable && hasOriginal && hasSuggested"
        type="button"
        @click="copyOriginalToSuggested"
        :disabled="!draftOriginal"
        class="self-end text-[11px] text-primary/80 hover:text-primary disabled:opacity-40 disabled:cursor-not-allowed bg-transparent border-none cursor-pointer"
      >↓ Kopieer originele naar voorstel</button>
    </div>

    <!-- Waarom dit beter is — LLM's pedagogical reasoning, teacher-editable. -->
    <div
      v-if="hasExplanationDefault || editable"
      class="flex flex-col gap-1 rounded-md border-l-2 border border-tertiary/40 bg-tertiary/5 px-3 py-2"
      :data-testid="`explanation-${index}`"
    >
      <label
        :for="`teacher-explanation-${index}`"
        class="flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-tertiary font-semibold"
      >
        <span class="material-symbols-rounded text-[14px]" aria-hidden="true">edit_note</span>
        Waarom dit beter is
      </label>
      <textarea
        :id="`teacher-explanation-${index}`"
        v-model="draftExplanation"
        :disabled="!editable"
        rows="3"
        class="w-full rounded-md border border-transparent bg-transparent text-sm text-on-surface leading-relaxed focus:outline-none focus:ring-1 focus:ring-tertiary/50 disabled:opacity-80 placeholder:text-outline/60"
        placeholder="Pedagogische uitleg voor de student — waarom de voorgestelde aanpak beter is."
      ></textarea>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';

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

const hasOriginal = computed(() => (draftOriginal.value ?? '').trim().length > 0);
const hasSuggested = computed(() => (draftSuggested.value ?? '').trim().length > 0);
const isTextOnly = computed(() => !hasOriginal.value && !hasSuggested.value);
const hasExplanationDefault = computed(() => (draftExplanation.value ?? '').trim().length > 0);

const dirty = computed(
  () =>
    draftBody.value !== (props.comment.body ?? '')
    || draftOriginal.value !== (props.comment.original_snippet ?? '')
    || draftSuggested.value !== (props.comment.suggested_snippet ?? '')
    || draftExplanation.value !== (props.comment.teacher_explanation ?? ''),
);

watch(draftBody, (v) => emit('update', { body: v }));
watch(draftOriginal, (v) => emit('update', { original_snippet: v }));
watch(draftSuggested, (v) => emit('update', { suggested_snippet: v }));
watch(draftExplanation, (v) => emit('update', { teacher_explanation: v }));

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

const codeFontStyle = {
  fontFamily: '"Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace',
};

// ---- Shiki lazy highlighting (shared module-level singleton) ----

const EXT_LANG: Record<string, string> = {
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'jsx',
  ts: 'typescript', tsx: 'tsx',
  py: 'python',
  rb: 'ruby',
  go: 'go',
  rs: 'rust',
  java: 'java',
  kt: 'kotlin',
  cs: 'csharp',
  cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp', h: 'c',
  c: 'c',
  php: 'php',
  sh: 'bash', bash: 'bash', zsh: 'bash',
  yml: 'yaml', yaml: 'yaml',
  json: 'json',
  html: 'html', htm: 'html',
  css: 'css', scss: 'scss', sass: 'sass',
  vue: 'vue',
  md: 'markdown', markdown: 'markdown',
  sql: 'sql',
  xml: 'xml',
  toml: 'toml',
};

function detectLang(filePath: string | undefined): string {
  if (!filePath) return 'text';
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  return EXT_LANG[ext] || 'text';
}

const originalHtml = ref('');
const suggestedHtml = ref('');

async function ensureHighlighter(lang: string) {
  const hl = await getSharedHighlighter();
  if (!hl) return null;
  if (lang !== 'text') {
    const loaded = hl.getLoadedLanguages?.() || [];
    if (!loaded.includes(lang)) {
      try {
        await hl.loadLanguage(lang);
      } catch {
        /* fallback: render as text */
      }
    }
  }
  return hl;
}

async function highlight(code: string, lang: string): Promise<string> {
  if (!code) return '';
  const hl = await ensureHighlighter(lang);
  if (!hl) return '';
  try {
    return hl.codeToHtml(code, { lang: lang === 'text' ? 'text' : lang, theme: 'github-dark' });
  } catch {
    return '';
  }
}

async function refreshHighlights() {
  const lang = detectLang(props.comment.file);
  const orig = draftOriginal.value;
  const sug = draftSuggested.value;
  const [oh, sh] = await Promise.all([
    hasOriginal.value ? highlight(orig, lang) : Promise.resolve(''),
    hasSuggested.value ? highlight(sug, lang) : Promise.resolve(''),
  ]);
  if (draftOriginal.value === orig) originalHtml.value = oh;
  if (draftSuggested.value === sug) suggestedHtml.value = sh;
}

watch(
  () => [draftOriginal.value, draftSuggested.value, props.comment.file],
  () => { refreshHighlights(); },
  { immediate: true },
);
</script>

<script lang="ts">
// Module-scope Shiki singleton cache — shared across all editor instances so
// the highlighter initializes once per page load, not once per comment row.
// This block runs once when the SFC module loads, not per component instance.
const shikiState: { highlighter: any; loader: Promise<any> | null } = {
  highlighter: null,
  loader: null,
};

export async function getSharedHighlighter(): Promise<any> {
  if (shikiState.highlighter) return shikiState.highlighter;
  if (shikiState.loader) return shikiState.loader;
  shikiState.loader = (async () => {
    try {
      const shiki = await import('shiki');
      shikiState.highlighter = await shiki.createHighlighter({
        themes: ['github-dark'],
        langs: [],
      });
      return shikiState.highlighter;
    } catch (err) {
      console.warn('Shiki failed to load', err);
      return null;
    }
  })();
  return shikiState.loader;
}
</script>

<style scoped>
:deep(.inline-code) pre {
  margin: 0;
  padding: 10px 12px;
  font-family: "Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12.5px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  background: transparent !important;
}
:deep(.inline-code) code {
  font-family: inherit;
  white-space: inherit;
}
</style>
