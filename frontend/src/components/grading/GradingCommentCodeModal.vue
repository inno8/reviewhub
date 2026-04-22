<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-surface/80 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    data-testid="comment-code-modal"
    @click.self="requestClose"
    @keydown.esc="requestClose"
  >
    <div
      class="bg-surface-container-low border border-outline-variant/20 rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col shadow-2xl"
      @keydown.ctrl.s.prevent="onSave"
      @keydown.meta.s.prevent="onSave"
      tabindex="-1"
      ref="cardEl"
    >
      <!-- Header -->
      <header class="flex items-center gap-3 border-b border-outline-variant/10 p-4">
        <span
          class="material-symbols-rounded text-on-surface-variant text-xl"
          aria-hidden="true"
        >code</span>
        <div class="flex-1 min-w-0">
          <div class="font-mono text-sm text-on-surface truncate">
            {{ comment.file }}
          </div>
          <div class="font-mono text-xs text-on-surface-variant">
            Regel {{ comment.line }}
          </div>
        </div>
        <button
          @click="requestClose"
          class="text-on-surface-variant hover:text-on-surface p-2 rounded-lg transition-colors"
          aria-label="Sluiten"
          data-testid="modal-close-btn"
        >
          <span class="material-symbols-rounded text-xl" aria-hidden="true">close</span>
        </button>
      </header>

      <!-- Body -->
      <div class="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[3fr_2fr] overflow-hidden">
        <!-- File viewer (left) -->
        <section
          class="border-b md:border-b-0 md:border-r border-outline-variant/10 flex flex-col min-h-0"
          data-testid="file-viewer"
        >
          <div class="p-3 border-b border-outline-variant/10 text-xs text-on-surface-variant flex items-center gap-2">
            <span class="material-symbols-rounded text-base" aria-hidden="true">description</span>
            <span>Bron op {{ refLabel }}</span>
            <span
              v-if="fileMeta.truncated"
              class="ml-auto px-2 py-0.5 rounded-full bg-tertiary/15 text-tertiary text-[11px]"
            >eerste 1000 regels</span>
          </div>

          <div class="flex-1 overflow-auto font-mono text-[13px] leading-relaxed">
            <!-- Loading skeleton -->
            <div v-if="loading" class="p-4 flex flex-col gap-2" data-testid="file-loading">
              <div
                v-for="n in 14"
                :key="n"
                class="h-4 bg-surface-container/50 rounded animate-pulse"
                :style="{ width: (40 + (n * 13) % 55) + '%' }"
              ></div>
            </div>

            <!-- No-PAT fallback -->
            <div
              v-else-if="fetchError && fetchError.code === 'no_pat'"
              class="glass-panel m-4 p-6 text-center rounded-xl"
              data-testid="no-pat-fallback"
            >
              <span
                class="material-symbols-rounded text-outline text-4xl block mb-2"
                aria-hidden="true"
              >key_off</span>
              <p class="text-sm text-on-surface mb-1 font-semibold">
                Geen GitHub PAT ingesteld
              </p>
              <p class="text-xs text-on-surface-variant font-sans">
                Voeg een GitHub PAT toe in je instellingen om de code hier te
                zien. Je kunt de comment hiernaast gewoon bewerken en opslaan.
              </p>
            </div>

            <!-- Generic error -->
            <div
              v-else-if="fetchError"
              class="glass-panel m-4 p-6 text-center rounded-xl text-error"
              data-testid="file-error"
            >
              <span
                class="material-symbols-rounded text-4xl block mb-2"
                aria-hidden="true"
              >error</span>
              <p class="text-sm mb-3 font-sans">{{ fetchError.detail || 'Kon bestand niet laden.' }}</p>
              <button
                @click="loadFile"
                class="bg-surface-container hover:bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-sans transition-colors"
              >Opnieuw proberen</button>
            </div>

            <!-- File content with line numbers + highlighted target line -->
            <div v-else class="min-w-full">
              <div
                v-for="(line, idx) in fileLines"
                :key="idx"
                :ref="(el) => registerLineEl(idx + 1, el)"
                :class="[
                  'flex gap-4 px-4 py-0.5',
                  isTargetLine(idx + 1)
                    ? 'bg-primary/10 border-l-2 border-primary'
                    : 'border-l-2 border-transparent',
                ]"
                :data-testid="isTargetLine(idx + 1) ? 'target-line' : undefined"
              >
                <span
                  class="text-on-surface-variant/60 tabular-nums select-none text-right w-10 shrink-0"
                >{{ idx + 1 }}</span>
                <pre class="whitespace-pre text-on-surface m-0 font-mono">{{ line || ' ' }}</pre>
              </div>
              <div v-if="fileLines.length === 0" class="p-6 text-center text-on-surface-variant text-sm font-sans">
                Bestand is leeg.
              </div>
            </div>
          </div>
        </section>

        <!-- Comment editor (right) -->
        <section class="flex flex-col min-h-0" data-testid="comment-editor">
          <div class="p-4 border-b border-outline-variant/10 flex items-center gap-2">
            <code class="font-mono text-xs text-primary bg-surface-container px-2 py-0.5 rounded">
              {{ comment.file }}:{{ comment.line }}
            </code>
            <span v-if="isDirty" class="text-xs text-tertiary ml-auto">
              Niet opgeslagen
            </span>
          </div>
          <div class="p-4 flex-1 min-h-0 overflow-y-auto flex flex-col gap-4" data-testid="modal-right-scroll">
            <!-- 1. Comment body -->
            <div class="flex flex-col gap-2">
              <label
                for="comment-body-edit"
                class="text-xs uppercase tracking-widest text-on-surface-variant font-semibold"
              >Commentaar</label>
              <textarea
                id="comment-body-edit"
                v-model="draftBody"
                :disabled="!canEdit"
                rows="5"
                class="min-h-[120px] bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface font-mono text-sm p-3 resize-y focus:ring-1 focus:ring-primary/50 focus:outline-none leading-relaxed disabled:opacity-60"
                data-testid="modal-comment-textarea"
                placeholder="Bewerk de feedback voordat je hem naar de student stuurt…"
              ></textarea>
            </div>

            <!-- 2. Original snippet (readonly if populated; paste area if empty) -->
            <div class="flex flex-col gap-2" data-testid="original-snippet-panel">
              <label
                :for="hasOriginal ? undefined : 'original-snippet-paste'"
                class="text-xs uppercase tracking-widest text-on-surface-variant font-semibold"
              >Originele code</label>
              <div class="bg-surface-container-lowest border border-error/30 rounded-lg p-3">
                <textarea
                  v-if="hasOriginal"
                  :value="draftOriginalSnippet"
                  readonly
                  rows="4"
                  class="w-full bg-transparent border-0 text-on-surface font-mono text-sm resize-y focus:outline-none leading-relaxed"
                  data-testid="original-snippet-readonly"
                ></textarea>
                <textarea
                  v-else
                  id="original-snippet-paste"
                  v-model="draftOriginalSnippet"
                  :disabled="!canEdit"
                  rows="4"
                  class="w-full bg-transparent border-0 text-on-surface font-mono text-sm resize-y focus:outline-none leading-relaxed disabled:opacity-60 placeholder:text-outline/60"
                  placeholder="LLM heeft nog geen snippet geleverd — plak hier de relevante code als je wilt"
                  data-testid="original-snippet-paste"
                ></textarea>
              </div>
              <div class="flex justify-end">
                <button
                  type="button"
                  @click="copyOriginalToSuggested"
                  :disabled="!canEdit || !draftOriginalSnippet"
                  class="text-xs text-primary/80 hover:text-primary disabled:opacity-40 disabled:cursor-not-allowed bg-transparent border-none cursor-pointer"
                  data-testid="copy-original-to-suggested"
                >
                  ↓ Kopieer naar voorstel
                </button>
              </div>
            </div>

            <!-- 3. Suggested snippet (editable) -->
            <div class="flex flex-col gap-2" data-testid="suggested-snippet-panel">
              <label
                for="suggested-snippet-edit"
                class="text-xs uppercase tracking-widest text-on-surface-variant font-semibold"
              >Voorgestelde code</label>
              <div class="bg-surface-container-lowest border border-primary/30 rounded-lg p-3">
                <textarea
                  id="suggested-snippet-edit"
                  v-model="draftSuggestedSnippet"
                  :disabled="!canEdit"
                  rows="4"
                  class="w-full bg-transparent border-0 text-on-surface text-sm resize-y focus:outline-none leading-relaxed disabled:opacity-60 placeholder:text-outline/60"
                  :style="suggestedSnippetFontStyle"
                  placeholder="Geen suggestie van de LLM. Typ een voorstel om de student een fix aan te bieden."
                  data-testid="suggested-snippet-textarea"
                ></textarea>
              </div>
            </div>

            <!-- 4. Teacher explanation (optional) -->
            <div class="flex flex-col gap-2" data-testid="teacher-explanation-panel">
              <label
                for="teacher-explanation-edit"
                class="text-xs uppercase tracking-widest text-on-surface-variant font-semibold"
              >Extra toelichting (optioneel)</label>
              <textarea
                id="teacher-explanation-edit"
                v-model="draftTeacherExplanation"
                :disabled="!canEdit"
                rows="3"
                class="bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm p-3 resize-y focus:ring-1 focus:ring-primary/50 focus:outline-none leading-relaxed disabled:opacity-60 placeholder:text-outline/60"
                placeholder="Voeg eventueel een korte uitleg toe voor de student…"
                data-testid="teacher-explanation-textarea"
              ></textarea>
            </div>

            <div v-if="!canEdit" class="text-xs text-on-surface-variant">
              Deze sessie is al verstuurd of gearchiveerd; bewerken uitgeschakeld.
            </div>
          </div>
          <footer class="p-4 border-t border-outline-variant/10 flex items-center justify-end gap-3">
            <button
              @click="requestClose"
              class="bg-surface-container hover:bg-surface-container-high text-on-surface px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
              data-testid="modal-cancel-btn"
            >
              Annuleer
            </button>
            <button
              @click="onSave"
              :disabled="!isDirty || !canEdit"
              class="primary-gradient text-on-primary font-bold px-5 py-2.5 rounded-lg text-sm shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="modal-save-btn"
            >
              Opslaan
            </button>
          </footer>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import axios from 'axios';

interface GradingCommentLike {
  file: string;
  line: number;
  body: string;
  client_mutation_id?: string;
  // Leera v1 suggested_snippet fields — all optional for backward compat.
  original_snippet?: string;
  suggested_snippet?: string;
  teacher_explanation?: string;
}

interface Props {
  sessionId: number;
  comment: GradingCommentLike;
  sessionState?: string;
}
const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'save', updated: GradingCommentLike): void;
  (e: 'close'): void;
}>();

const EDITABLE_STATES = new Set(['drafted', 'reviewing', 'partial']);
const canEdit = computed(() =>
  props.sessionState ? EDITABLE_STATES.has(props.sessionState) : true,
);

const draftBody = ref(props.comment.body ?? '');
const draftOriginalSnippet = ref(props.comment.original_snippet ?? '');
const draftSuggestedSnippet = ref(props.comment.suggested_snippet ?? '');
const draftTeacherExplanation = ref(props.comment.teacher_explanation ?? '');

const originalBody = props.comment.body ?? '';
const originalOriginalSnippet = props.comment.original_snippet ?? '';
const originalSuggestedSnippet = props.comment.suggested_snippet ?? '';
const originalTeacherExplanation = props.comment.teacher_explanation ?? '';

const isDirty = computed(() =>
  draftBody.value !== originalBody
  || draftOriginalSnippet.value !== originalOriginalSnippet
  || draftSuggestedSnippet.value !== originalSuggestedSnippet
  || draftTeacherExplanation.value !== originalTeacherExplanation,
);

// Whether the comment already has an original_snippet (LLM-provided or
// previously pasted). Controls readonly vs paste-textarea rendering.
const hasOriginal = computed(() => (props.comment.original_snippet ?? '').length > 0);

function copyOriginalToSuggested() {
  if (!canEdit.value) return;
  draftSuggestedSnippet.value = draftOriginalSnippet.value;
}

// Fira Code for the suggested-snippet panel per DESIGN.md §5.2.
// Bound as a reactive style to keep the template free of embedded quotes.
const suggestedSnippetFontStyle = {
  fontFamily: '"Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace',
};

const loading = ref(false);
const fetchError = ref<{ code?: string; detail?: string } | null>(null);
const fileMeta = ref<{ truncated: boolean; ref: string }>({ truncated: false, ref: '' });
const fileLines = ref<string[]>([]);
const refLabel = computed(() => fileMeta.value.ref || 'head');

const lineEls = new Map<number, HTMLElement>();
function registerLineEl(lineNo: number, el: unknown) {
  if (el instanceof HTMLElement) {
    lineEls.set(lineNo, el);
  }
}

function isTargetLine(n: number): boolean {
  return n === Number(props.comment.line);
}

async function loadFile() {
  loading.value = true;
  fetchError.value = null;
  fileLines.value = [];
  try {
    const token = localStorage.getItem('reviewhub_token');
    const baseURL = (import.meta as any).env?.VITE_API_URL || '/api';
    const resp = await axios.get(
      `${baseURL}/grading/sessions/${props.sessionId}/file/`,
      {
        params: { path: props.comment.file },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    const data = resp.data || {};
    fileMeta.value = {
      truncated: !!data.truncated,
      ref: data.ref || '',
    };
    const content: string = data.content || '';
    fileLines.value = content.split(/\r?\n/);
    await nextTick();
    scrollTargetLineIntoView();
  } catch (err: any) {
    const resp = err?.response;
    if (resp?.status === 503 && resp?.data?.code === 'no_pat') {
      fetchError.value = { code: 'no_pat', detail: resp.data.detail };
    } else if (resp?.data?.detail) {
      fetchError.value = { detail: resp.data.detail };
    } else {
      fetchError.value = { detail: 'Kon bestand niet laden.' };
    }
  } finally {
    loading.value = false;
  }
}

function scrollTargetLineIntoView() {
  const el = lineEls.get(Number(props.comment.line));
  if (el && typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ block: 'center', behavior: 'auto' });
  }
}

function onSave() {
  if (!isDirty.value || !canEdit.value) return;
  emit('save', {
    ...props.comment,
    body: draftBody.value,
    original_snippet: draftOriginalSnippet.value,
    suggested_snippet: draftSuggestedSnippet.value,
    teacher_explanation: draftTeacherExplanation.value,
  });
}

function requestClose() {
  if (isDirty.value) {
    const ok = window.confirm(
      'Je hebt wijzigingen die niet zijn opgeslagen. Toch sluiten?',
    );
    if (!ok) return;
  }
  emit('close');
}

// Keep draft in sync if the parent swaps the comment prop for a new one.
watch(
  () => props.comment,
  (next) => {
    draftBody.value = next.body ?? '';
    draftOriginalSnippet.value = next.original_snippet ?? '';
    draftSuggestedSnippet.value = next.suggested_snippet ?? '';
    draftTeacherExplanation.value = next.teacher_explanation ?? '';
  },
);

const cardEl = ref<HTMLElement | null>(null);
onMounted(() => {
  loadFile();
  // Focus trap-lite: focus the modal card so Escape + Ctrl+S bindings fire.
  nextTick(() => cardEl.value?.focus());
});

// Global Escape fallback (when focus is outside the card).
function onDocKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    requestClose();
  }
}
document.addEventListener('keydown', onDocKeydown);
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDocKeydown);
});
</script>
