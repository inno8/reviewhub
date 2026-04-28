<template>
  <div
    :id="`file-${encodedFilePath}`"
    class="rounded-xl border border-outline-variant/10 bg-surface-container-lowest overflow-hidden scroll-mt-24"
    :data-testid="`diff-viewer-${filePath}`"
    :data-file-path="filePath"
  >
    <header
      class="flex items-center gap-2 border-b border-outline-variant/10 bg-surface-container/60 px-3 py-2"
    >
      <span
        class="material-symbols-rounded text-base text-on-surface-variant"
        aria-hidden="true"
      >description</span>
      <code class="font-mono text-xs text-on-surface truncate flex-1">{{ filePath }}</code>
      <span class="text-[11px] text-outline">
        {{ comments.length }} comment{{ comments.length === 1 ? '' : 's' }}
      </span>
      <span
        v-if="truncated"
        class="text-[11px] px-2 py-0.5 rounded-full bg-tertiary/15 text-tertiary"
      >eerste 1000 regels</span>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="p-4 flex flex-col gap-2" :data-testid="`file-loading-${filePath}`">
      <div
        v-for="n in 10"
        :key="n"
        class="h-4 bg-surface-container/50 rounded animate-pulse"
        :style="{ width: (40 + (n * 13) % 55) + '%' }"
      ></div>
    </div>

    <!-- Fetch error (no PAT / 404 / etc.) -->
    <div
      v-else-if="fetchError"
      class="m-4 p-4 rounded-xl border border-outline-variant/20 bg-surface-container text-sm text-on-surface-variant flex flex-col gap-2"
      :data-testid="`file-error-${filePath}`"
    >
      <div class="flex items-center gap-2 text-on-surface">
        <span class="material-symbols-rounded text-base" aria-hidden="true">info</span>
        <span class="font-semibold">{{ fetchErrorHeading }}</span>
      </div>
      <p class="leading-relaxed">{{ fetchErrorDetail }}</p>
      <!-- Fallback: render the comments inline without file context -->
      <div v-if="comments.length > 0" class="flex flex-col gap-3 mt-2">
        <InlineCommentEditor
          v-for="c in comments"
          :key="c._index"
          :comment="c"
          :index="c._index"
          :editable="editable"
          @update="(p) => $emit('update-comment', c._index, p)"
          @remove="$emit('remove-comment', c._index)"
        />
      </div>
    </div>

    <!-- File rendered with line numbers; comments anchored at target line -->
    <div v-else class="font-mono text-[13px] leading-relaxed" :style="codeFontStyle">
      <template v-for="(line, idx) in fileLines" :key="idx">
        <!-- Code line -->
        <div
          :class="[
            'flex gap-3 px-3 py-0.5',
            isCommentedLine(idx + 1)
              ? 'bg-red-500/5 border-l-2 border-red-500/60'
              : 'border-l-2 border-transparent',
          ]"
          :data-testid="isCommentedLine(idx + 1) ? `commented-line-${idx + 1}` : undefined"
        >
          <span
            class="text-outline/50 tabular-nums select-none text-right w-10 shrink-0"
          >{{ idx + 1 }}</span>
          <pre
            v-if="highlightedLines[idx]"
            class="shiki-line whitespace-pre m-0 flex-1 min-w-0 overflow-x-auto text-on-surface-variant"
            v-html="highlightedLines[idx]"
          ></pre>
          <pre
            v-else
            class="whitespace-pre m-0 flex-1 min-w-0 overflow-x-auto text-on-surface-variant"
          >{{ line || ' ' }}</pre>
        </div>
        <!-- Inline comment editors anchored under the LAST line of the matched snippet range -->
        <div
          v-for="c in commentsAfterLine(idx + 1)"
          :key="`c-${c._index}`"
          class="px-3 py-2 bg-surface-container/40 border-l-2 border-primary"
        >
          <InlineCommentEditor
            :comment="c"
            :index="c._index"
            :editable="editable"
            @update="(p) => $emit('update-comment', c._index, p)"
            @remove="$emit('remove-comment', c._index)"
          />
        </div>
      </template>
      <!-- Orphan comments: target line not in the loaded file -->
      <div
        v-for="c in orphanComments"
        :key="`orphan-${c._index}`"
        class="px-3 py-2 border-t border-outline-variant/10 bg-surface-container/20"
      >
        <p class="text-[11px] text-tertiary mb-2 font-sans">
          Regel {{ c.line }} niet gevonden in het bestand — comment weergegeven zonder context.
        </p>
        <InlineCommentEditor
          :comment="c"
          :index="c._index"
          :editable="editable"
          @update="(p) => $emit('update-comment', c._index, p)"
          @remove="$emit('remove-comment', c._index)"
        />
      </div>
      <div
        v-if="fileLines.length === 0"
        class="p-6 text-center text-on-surface-variant text-sm font-sans"
      >Bestand is leeg.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import InlineCommentEditor from './InlineCommentEditor.vue';
import { detectLangFromPath, highlightLines } from '@/utils/shikiHighlight';

interface AnchoredComment {
  _index: number;
  file: string;
  line: number;
  body: string;
  original_snippet?: string;
  suggested_snippet?: string;
  teacher_explanation?: string;
}

interface Props {
  sessionId: number;
  filePath: string;
  comments: AnchoredComment[];
  editable?: boolean;
  /**
   * Optional "{owner}/{name}" of the PR repo. When this is a known demo /
   * seeded prefix (e.g. mediacollege-webdev-q2/*) and the file fetch fails,
   * the error banner is softened from "Bestand niet beschikbaar" to a
   * calmer "demo PR" message. Teachers' dogfood view doesn't need alarm bells.
   */
  repoFullName?: string | null;
}

const props = withDefaults(defineProps<Props>(), { editable: true, repoFullName: null });
defineEmits<{
  (e: 'update-comment', index: number, patch: Partial<AnchoredComment>): void;
  (e: 'remove-comment', index: number): void;
}>();

const loading = ref(false);
const fetchError = ref<{ code?: string; detail?: string } | null>(null);
const fileLines = ref<string[]>([]);
const truncated = ref(false);
const highlightedLines = ref<string[]>([]);

const encodedFilePath = computed(() => encodeURIComponent(props.filePath));

const codeFontStyle = {
  fontFamily: '"Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace',
};

// Demo/seeded repos live under this GitHub org — they don't exist on GitHub
// so the file endpoint always 404s. Soften the copy in that case so the
// banner doesn't scream "something is broken" during a pitch demo.
const isDemoRepo = computed(
  () => !!props.repoFullName && props.repoFullName.startsWith('mediacollege-webdev-q2/'),
);

const fetchErrorHeading = computed(() => {
  if (fetchError.value?.code === 'no_pat') return 'Geen GitHub PAT ingesteld';
  if (isDemoRepo.value) return 'Demo-PR: codefragment hieronder';
  return 'Bestand niet beschikbaar';
});

const fetchErrorDetail = computed(() => {
  if (isDemoRepo.value) {
    return (
      'Dit is een demo-PR — het volledige bestand wordt niet opgehaald. '
      + 'Je ziet hieronder het codefragment waarop de feedback betrekking heeft.'
    );
  }
  return fetchError.value?.detail || 'Kon bestand niet laden.';
});

// ─────────────────────────────────────────────────────────────────────────────
// Snippet-based range resolution (preferred over LLM's `line` anchor).
//
// The LLM's `line` field is a single-line anchor — it's often aimed at a
// topic-marker line (e.g. a `# path traversal` comment the student wrote),
// NOT at the actual problematic code. The real offending code lives in
// `original_snippet`, which can span multiple lines. We render the red
// highlight over the lines whose content matches `original_snippet`, and
// drop the comment row BELOW that range. Falls back to the `line` anchor
// when the snippet isn't present in the loaded file (e.g. text-only comments
// or context mismatch).
//
// Matching is content-based: strip each candidate+snippet line of leading
// whitespace and compare. Whitespace-tolerance handles tabs-vs-spaces or
// minor indent differences without false negatives.
// ─────────────────────────────────────────────────────────────────────────────

interface AnchorRange {
  start: number; // 1-indexed
  end: number;   // 1-indexed inclusive
}

const commentRanges = computed<Map<number, AnchorRange>>(() => {
  const result = new Map<number, AnchorRange>();
  const lines = fileLines.value;
  for (const c of props.comments) {
    const anchor = Number(c.line);
    const snippet = (c.original_snippet || '').trim();
    if (!snippet) {
      // No snippet — fall back to the LLM's single-line anchor
      result.set(c._index, { start: anchor, end: anchor });
      continue;
    }
    const snippetLines = snippet
      .split(/\r?\n/)
      .map((s) => s.replace(/^\s+/, '').replace(/\s+$/, ''))
      .filter((s) => s.length > 0);
    if (snippetLines.length === 0) {
      result.set(c._index, { start: anchor, end: anchor });
      continue;
    }
    // Scan fileLines for the snippet's first line, then verify subsequent
    // lines match in order (whitespace-normalised). Prefer a match near the
    // LLM's anchor (within ±10 lines) to disambiguate repeats.
    const normalised = lines.map((l) => l.replace(/^\s+/, '').replace(/\s+$/, ''));
    const first = snippetLines[0];
    let best: AnchorRange | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let i = 0; i < normalised.length; i += 1) {
      if (normalised[i] !== first) continue;
      // Check all subsequent snippet lines match in sequence
      let ok = true;
      for (let j = 1; j < snippetLines.length; j += 1) {
        if (normalised[i + j] !== snippetLines[j]) {
          ok = false;
          break;
        }
      }
      if (!ok) continue;
      const start = i + 1;
      const end = i + snippetLines.length;
      const distance = Math.abs(start - anchor);
      if (distance < bestDistance) {
        best = { start, end };
        bestDistance = distance;
      }
    }
    if (best) {
      result.set(c._index, best);
    } else {
      // No content match — fall back to anchor
      result.set(c._index, { start: anchor, end: anchor });
    }
  }
  return result;
});

function isCommentedLine(n: number): boolean {
  for (const range of commentRanges.value.values()) {
    if (n >= range.start && n <= range.end) return true;
  }
  return false;
}

// Comments render AFTER the last line of their matched range (not after the
// LLM's anchor line). This places the teacher's editor directly under the
// code it addresses instead of next to a topic-marker comment above it.
function commentsAfterLine(n: number): AnchoredComment[] {
  return props.comments.filter((c) => {
    const r = commentRanges.value.get(c._index);
    return r ? r.end === n : false;
  });
}

const orphanComments = computed(() =>
  props.comments.filter((c) => {
    const r = commentRanges.value.get(c._index);
    if (!r) return true;
    return r.start < 1 || r.end > fileLines.value.length;
  }),
);

async function loadFile() {
  loading.value = true;
  fetchError.value = null;
  fileLines.value = [];
  truncated.value = false;
  try {
    const token = localStorage.getItem('reviewhub_token');
    const baseURL = (import.meta as any).env?.VITE_API_URL || '/api';
    const resp = await axios.get(
      `${baseURL}/grading/sessions/${props.sessionId}/file/`,
      {
        params: { path: props.filePath },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    const data = resp.data || {};
    truncated.value = !!data.truncated;
    const content: string = data.content || '';
    fileLines.value = content.length ? content.split(/\r?\n/) : [];
    highlightedLines.value = [];
    // Fire-and-forget syntax highlighting — context code stays readable even
    // if Shiki hasn't loaded yet. When it resolves we replace the plain
    // <pre> render with the colored version.
    if (content.length) {
      const lang = detectLangFromPath(props.filePath);
      const snapshot = content;
      highlightLines(content, lang).then(lines => {
        if (snapshot === (fileLines.value.join('\n'))) {
          highlightedLines.value = lines;
        }
      }).catch(() => { /* fallback to plaintext */ });
    }
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

onMounted(loadFile);
watch(() => [props.sessionId, props.filePath], loadFile);
</script>

<style scoped>
.shiki-line {
  font-family: "Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  line-height: 1.5;
  background: transparent !important;
}
.shiki-line :deep(span) {
  white-space: pre;
}
</style>
