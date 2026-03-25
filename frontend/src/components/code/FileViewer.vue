<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-surface-container-low rounded-xl shadow-xl w-[90vw] max-w-5xl max-h-[85vh] flex flex-col border border-outline-variant/10">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-outline-variant/10">
        <div>
          <h3 class="font-semibold text-lg text-on-surface font-mono">{{ filePath }}</h3>
          <p class="text-sm text-outline">{{ branch }}</p>
        </div>
        <button @click="$emit('close')" class="p-2 hover:bg-surface-container-highest rounded-lg transition-colors">
          <span class="material-symbols-outlined text-on-surface-variant">close</span>
        </button>
      </div>

      <!-- Code Content -->
      <div class="flex-1 overflow-auto" ref="codeContainer">
        <div v-if="loading" class="p-8 text-center text-outline">
          <span class="material-symbols-outlined text-2xl animate-spin">progress_activity</span>
          <p class="mt-2">Loading file...</p>
        </div>
        <div v-else-if="error" class="p-8 text-center text-error">{{ error }}</div>
        <div v-else class="code-viewer font-mono text-sm">
          <div
            v-for="(line, index) in lines"
            :key="index"
            :ref="el => { if (el && isHighlighted(index + 1)) highlightedEls.push(el as HTMLElement) }"
            :class="[
              'flex hover:bg-surface-container-highest/50',
              isHighlighted(index + 1) ? 'bg-tertiary/10 border-l-4 border-tertiary' : ''
            ]"
          >
            <span class="w-12 px-2 py-0.5 text-right text-outline select-none border-r border-outline-variant/10 bg-surface-container shrink-0">
              {{ index + 1 }}
            </span>
            <pre class="flex-1 px-4 py-0.5 overflow-x-auto"><code v-html="highlightLine(line)"></code></pre>
          </div>
        </div>
      </div>

      <!-- Footer with issue info -->
      <div v-if="finding" class="p-4 border-t border-outline-variant/10 bg-surface-container">
        <p class="font-medium text-sm text-on-surface">{{ finding.category.replace('_', ' ') }}</p>
        <p class="text-sm text-on-surface-variant mt-1 line-clamp-2">{{ finding.explanation }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue';
import { api } from '@/composables/useApi';
import type { Finding } from '@/stores/findings';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
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
  projectId: number;
  branch: string;
  filePath: string;
  lineStart: number;
  lineEnd: number;
  finding?: Finding;
}>();

defineEmits(['close']);

const loading = ref(true);
const error = ref('');
const content = ref('');
const codeContainer = ref<HTMLElement>();
const highlightedEls = ref<HTMLElement[]>([]);

const lines = computed(() => content.value.split('\n'));

const language = computed(() => {
  const ext = props.filePath.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    html: 'markup',
    htm: 'markup',
    vue: 'markup',
    xml: 'markup',
    svg: 'markup',
    js: 'javascript',
    mjs: 'javascript',
    cjs: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    css: 'css',
    scss: 'css',
    go: 'go',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    sh: 'bash',
    bash: 'bash',
  };
  return langMap[ext || ''] || 'markup';
});

function isHighlighted(lineNum: number): boolean {
  return lineNum >= props.lineStart && lineNum <= props.lineEnd;
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
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

onMounted(async () => {
  try {
    const { data } = await api.files.getContent(props.projectId, props.branch, props.filePath);
    content.value = data.content;
  } catch (e: any) {
    error.value = e.response?.data?.error || 'Failed to load file';
  } finally {
    loading.value = false;
  }

  // Scroll to highlighted line after render
  await nextTick();
  if (highlightedEls.value.length > 0) {
    highlightedEls.value[0]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});
</script>

<style scoped>
.code-viewer {
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
</style>
