<template>
  <div
    class="rounded-xl border border-outline-variant/10 bg-surface-container-lowest overflow-hidden"
    :data-testid="`diff-viewer-${filePath}`"
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
      <p class="leading-relaxed">{{ fetchError.detail || 'Kon bestand niet laden.' }}</p>
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
              ? 'bg-primary/5 border-l-2 border-primary'
              : 'border-l-2 border-transparent',
          ]"
          :data-testid="isCommentedLine(idx + 1) ? `commented-line-${idx + 1}` : undefined"
        >
          <span
            class="text-outline/50 tabular-nums select-none text-right w-10 shrink-0"
          >{{ idx + 1 }}</span>
          <pre class="whitespace-pre m-0 text-on-surface-variant">{{ line || ' ' }}</pre>
        </div>
        <!-- Inline comment editors anchored under this line -->
        <div
          v-for="c in commentsAt(idx + 1)"
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
}

const props = withDefaults(defineProps<Props>(), { editable: true });
defineEmits<{
  (e: 'update-comment', index: number, patch: Partial<AnchoredComment>): void;
  (e: 'remove-comment', index: number): void;
}>();

const loading = ref(false);
const fetchError = ref<{ code?: string; detail?: string } | null>(null);
const fileLines = ref<string[]>([]);
const truncated = ref(false);

const codeFontStyle = {
  fontFamily: '"Fira Code", ui-monospace, SFMono-Regular, Menlo, monospace',
};

const fetchErrorHeading = computed(() => {
  if (fetchError.value?.code === 'no_pat') return 'Geen GitHub PAT ingesteld';
  return 'Bestand niet beschikbaar';
});

function isCommentedLine(n: number): boolean {
  return props.comments.some((c) => Number(c.line) === n);
}

function commentsAt(n: number): AnchoredComment[] {
  return props.comments.filter((c) => Number(c.line) === n);
}

const orphanComments = computed(() =>
  props.comments.filter((c) => {
    const n = Number(c.line);
    return n < 1 || n > fileLines.value.length;
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
