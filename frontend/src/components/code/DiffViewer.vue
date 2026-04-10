<template>
  <div class="diff-viewer space-y-4">
    <!-- File Header -->
    <div class="bg-surface-container-low rounded-xl p-4 border border-outline-variant/10">
      <div class="flex items-center gap-4 flex-wrap">
        <span class="font-mono text-sm text-on-surface-variant bg-surface-container px-3 py-1 rounded-lg flex items-center gap-1.5">
          <span class="material-symbols-outlined text-sm">description</span>
          {{ finding.filePath }}
        </span>
        <a
          v-if="commitUrl"
          :href="commitUrl"
          target="_blank"
          class="text-primary text-sm hover:underline flex items-center gap-1"
        >
          <span class="material-symbols-outlined text-sm">commit</span>
          {{ finding.commitSha || 'View commit' }}
        </a>
      </div>
      <div class="flex items-center gap-3 mt-2 text-sm text-outline">
        <span v-if="finding.commitAuthor" class="flex items-center gap-1">
          <span class="material-symbols-outlined text-sm">person</span>
          {{ finding.commitAuthor }}
        </span>
        <span v-if="finding.review?.branch" class="flex items-center gap-1">
          <span class="material-symbols-outlined text-sm">account_tree</span>
          {{ finding.review.branch }}
        </span>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center h-64 bg-surface-container rounded-xl border border-outline-variant/10">
      <div class="text-center text-outline">
        <span class="material-symbols-outlined text-3xl animate-spin">progress_activity</span>
        <p class="mt-2 text-sm">Loading file from GitHub...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-error/10 border border-error/20 rounded-xl p-6 text-center">
      <span class="material-symbols-outlined text-3xl text-error">error</span>
      <p class="mt-2 text-error">{{ error }}</p>
    </div>

    <!-- Diff Panels -->
    <div v-else class="grid grid-cols-2 gap-4">
      <!-- ORIGINAL Panel -->
      <div class="rounded-xl overflow-hidden border border-outline-variant/10">
        <div class="px-4 py-2 bg-red-900/80 text-white text-sm font-bold flex items-center gap-2">
          <span class="material-symbols-outlined text-sm">remove_circle</span>
          ORIGINAL
        </div>
        <div
          ref="originalPanel"
          class="code-scroll-panel overflow-auto font-mono text-sm"
          @scroll="syncScroll('original')"
        >
          <div class="code-lines">
            <div
              v-for="(line, idx) in originalLines"
              :key="idx"
              :class="[
                'flex hover:bg-surface-container-highest/30',
                isIssueLine(idx + 1) ? 'bg-red-900/20 border-l-4 border-red-500' : ''
              ]"
            >
              <span class="line-num w-12 px-2 py-0.5 text-right text-outline select-none border-r border-outline-variant/10 bg-surface-container shrink-0">
                {{ idx + 1 }}
              </span>
              <pre class="flex-1 px-4 py-0.5 overflow-x-auto"><code v-html="highlightLine(line)"></code></pre>
            </div>
          </div>
        </div>
      </div>

      <!-- OPTIMIZED Panel -->
      <div class="rounded-xl overflow-hidden border border-outline-variant/10">
        <div class="px-4 py-2 bg-green-900/80 text-white text-sm font-bold flex items-center gap-2">
          <span class="material-symbols-outlined text-sm">check_circle</span>
          OPTIMIZED
        </div>
        <div
          ref="optimizedPanel"
          class="code-scroll-panel overflow-auto font-mono text-sm"
          @scroll="syncScroll('optimized')"
        >
          <div class="code-lines">
            <div
              v-for="(line, idx) in optimizedLines"
              :key="idx"
              :class="[
                'flex hover:bg-surface-container-highest/30',
                isFixLine(idx + 1) ? 'bg-green-900/20 border-l-4 border-green-500' : ''
              ]"
            >
              <span class="line-num w-12 px-2 py-0.5 text-right text-outline select-none border-r border-outline-variant/10 bg-surface-container shrink-0">
                {{ idx + 1 }}
              </span>
              <pre class="flex-1 px-4 py-0.5 overflow-x-auto"><code v-html="highlightLine(line)"></code></pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { api } from '@/composables/useApi';
import type { Finding } from '@/stores/findings';
import Prism from 'prismjs';
// NOTE: We intentionally do NOT import prismjs/themes/prism.css (light theme).
// Dark token colors are defined in <style> below to match VS Code Dark+.
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-go';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-bash';

const props = defineProps<{
  finding: Finding;
}>();

const loading = ref(true);
const error = ref('');
const fileContent = ref('');
const originalPanel = ref<HTMLElement>();
const optimizedPanel = ref<HTMLElement>();
let scrolling = false;

const language = computed(() => {
  const ext = props.finding.filePath.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    html: 'markup', htm: 'markup', vue: 'markup', xml: 'markup', svg: 'markup',
    js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
    ts: 'typescript', tsx: 'typescript',
    py: 'python', css: 'css', scss: 'css', go: 'go',
    json: 'json', yaml: 'yaml', yml: 'yaml', sh: 'bash', bash: 'bash',
  };
  return langMap[ext || ''] || 'markup';
});

const originalLines = computed(() => fileContent.value.split('\n'));

const optimizedLines = computed(() => {
  if (!fileContent.value) return [];
  return generateOptimizedFile(fileContent.value, props.finding).split('\n');
});

const fixLineStart = computed(() => {
  if (!props.finding.lineStart) return -1;
  return props.finding.lineStart;
});

const fixLineEnd = computed(() => {
  if (!props.finding.lineStart) return -1;
  const optimizedCodeLines = props.finding.optimizedCode?.split('\n') || [];
  return fixLineStart.value + optimizedCodeLines.length - 1;
});

const commitUrl = computed(() => {
  const p = props.finding.review?.project;
  if (!p?.githubOwner || !p?.githubRepo || !props.finding.commitSha) return '';
  return `https://github.com/${p.githubOwner}/${p.githubRepo}/commit/${props.finding.commitSha}`;
});

function isIssueLine(lineNum: number): boolean {
  const start = props.finding.lineStart;
  const end = props.finding.lineEnd;
  if (!start) return false;
  return lineNum >= start && lineNum <= (end || start);
}

function isFixLine(lineNum: number): boolean {
  if (fixLineStart.value < 0) return false;
  return lineNum >= fixLineStart.value && lineNum <= fixLineEnd.value;
}

function generateOptimizedFile(originalContent: string, finding: Finding): string {
  const lines = originalContent.split('\n');

  if (finding.optimizedCode && finding.lineStart && finding.lineEnd) {
    const before = lines.slice(0, finding.lineStart - 1);
    const after = lines.slice(finding.lineEnd);
    const fixLines = finding.optimizedCode.split('\n');
    return [...before, ...fixLines, ...after].join('\n');
  }

  return originalContent;
}

function highlightLine(line: string): string {
  try {
    const lang = Prism.languages[language.value];
    if (lang) {
      return Prism.highlight(line || ' ', lang, language.value);
    }
    return escapeHtml(line || ' ');
  } catch {
    return escapeHtml(line || ' ');
  }
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function syncScroll(source: 'original' | 'optimized') {
  if (scrolling) return;
  scrolling = true;
  if (source === 'original' && originalPanel.value && optimizedPanel.value) {
    optimizedPanel.value.scrollTop = originalPanel.value.scrollTop;
    optimizedPanel.value.scrollLeft = originalPanel.value.scrollLeft;
  } else if (source === 'optimized' && originalPanel.value && optimizedPanel.value) {
    originalPanel.value.scrollTop = optimizedPanel.value.scrollTop;
    originalPanel.value.scrollLeft = optimizedPanel.value.scrollLeft;
  }
  requestAnimationFrame(() => { scrolling = false; });
}

onMounted(async () => {
  const projectId = props.finding.review?.project?.id;
  const branch = props.finding.review?.branch || 'main';

  if (!projectId) {
    // Fallback: use finding's own file-content endpoint
    try {
      const { data } = await api.findings.getFileContent(props.finding.id);
      fileContent.value = data.content;
    } catch (e: any) {
      error.value = e.response?.data?.error || 'Failed to load file content';
    } finally {
      loading.value = false;
    }
    return;
  }

  try {
    const { data } = await api.files.getContent(projectId, branch, props.finding.filePath);
    fileContent.value = data.content;
  } catch {
    // Fallback to finding-specific endpoint
    try {
      const { data } = await api.findings.getFileContent(props.finding.id);
      fileContent.value = data.content;
    } catch (e: any) {
      error.value = e.response?.data?.error || 'Failed to load file content';
    }
  } finally {
    loading.value = false;
  }

  // Scroll to issue lines after render
  await nextTick();
  if (props.finding.lineStart && originalPanel.value) {
    const lineEl = originalPanel.value.querySelector(`.code-lines > div:nth-child(${props.finding.lineStart})`);
    if (lineEl) {
      lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
});
</script>

<style scoped>
.code-scroll-panel {
  max-height: 70vh;
  background: var(--surface-container-lowest, #0a0e14);
}

.code-lines {
  min-width: max-content;
}

pre {
  margin: 0;
  white-space: pre;
}

code {
  background: none;
  padding: 0;
}

.line-num {
  font-size: 0.75rem;
  line-height: 1.5;
}

/* Prism tokens — VS Code Dark+ palette */
.code-lines :deep(.token.keyword) { color: #c586c0 !important; }
.code-lines :deep(.token.builtin) { color: #4ec9b0 !important; }
.code-lines :deep(.token.string),
.code-lines :deep(.token.attr-value) { color: #ce9178 !important; }
.code-lines :deep(.token.function) { color: #dcdcaa !important; }
.code-lines :deep(.token.number) { color: #b5cea8 !important; }
.code-lines :deep(.token.boolean) { color: #569cd6 !important; }
.code-lines :deep(.token.comment),
.code-lines :deep(.token.prolog),
.code-lines :deep(.token.doctype),
.code-lines :deep(.token.cdata) { color: #6a9955 !important; font-style: italic; }
.code-lines :deep(.token.operator) { color: #d4d4d4 !important; }
.code-lines :deep(.token.punctuation) { color: #d4d4d4 !important; }
.code-lines :deep(.token.class-name),
.code-lines :deep(.token.constant) { color: #4ec9b0 !important; }
.code-lines :deep(.token.property) { color: #9cdcfe !important; }
.code-lines :deep(.token.parameter) { color: #9cdcfe !important; }
.code-lines :deep(.token.decorator),
.code-lines :deep(.token.attr-name) { color: #dcdcaa !important; }
.code-lines :deep(.token.regex),
.code-lines :deep(.token.important) { color: #d16969 !important; }
.code-lines :deep(.token.tag) { color: #569cd6 !important; }
.code-lines :deep(.token.triple-quoted-string),
.code-lines :deep(.token.double-quoted-string) { color: #ce9178 !important; }
</style>
