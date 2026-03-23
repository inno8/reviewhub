<script setup lang="ts">
import { computed } from 'vue';
import hljs from 'highlight.js/lib/core';
import typescript from 'highlight.js/lib/languages/typescript';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import xml from 'highlight.js/lib/languages/xml';
import css from 'highlight.js/lib/languages/css';
import bash from 'highlight.js/lib/languages/bash';
import Card from '@/components/common/Card.vue';

hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('json', json);
hljs.registerLanguage('html', xml);
hljs.registerLanguage('css', css);
hljs.registerLanguage('bash', bash);

const props = defineProps<{ originalCode: string; optimizedCode: string; filePath?: string }>();

const language = computed(() => {
  const ext = props.filePath?.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'ts':
    case 'tsx':
      return 'typescript';
    case 'js':
    case 'jsx':
      return 'javascript';
    case 'json':
      return 'json';
    case 'html':
    case 'vue':
      return 'html';
    case 'css':
      return 'css';
    case 'sh':
      return 'bash';
    default:
      return undefined;
  }
});

const originalLines = computed(() => props.originalCode.split('\n'));
const optimizedLines = computed(() => props.optimizedCode.split('\n'));
const maxLines = computed(() => Math.max(originalLines.value.length, optimizedLines.value.length));

function highlightLine(line: string): string {
  if (!line) return '&nbsp;';
  if (language.value) {
    return hljs.highlight(line, { language: language.value, ignoreIllegals: true }).value;
  }
  return hljs.highlightAuto(line).value;
}

const changedOriginalLineNumbers = computed(() => {
  const changed = new Set<number>();
  for (let i = 0; i < maxLines.value; i += 1) {
    if ((originalLines.value[i] || '') !== (optimizedLines.value[i] || '')) {
      changed.add(i + 1);
    }
  }
  return changed;
});

const changedOptimizedLineNumbers = computed(() => changedOriginalLineNumbers.value);
</script>

<template>
  <Card>
    <h3 class="mb-3 text-lg font-semibold">Code Comparison</h3>
    <div class="grid gap-4 lg:grid-cols-2">
      <div class="rounded-lg border border-error/40 bg-error/5 p-3">
        <p class="mb-2 text-sm font-semibold text-error">Original</p>
        <div class="max-h-[520px] overflow-auto rounded border border-dark-border/60">
          <table class="w-full border-collapse text-xs font-mono">
            <tbody>
              <tr v-for="(line, index) in originalLines" :key="`original-${index}`">
                <td class="w-10 select-none border-r border-dark-border/60 px-2 py-1 text-right text-text-secondary">
                  {{ index + 1 }}
                </td>
                <td
                  class="px-2 py-1 align-top"
                  :class="changedOriginalLineNumbers.has(index + 1) ? 'bg-error/15' : ''"
                  v-html="highlightLine(line)"
                />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="rounded-lg border border-success/40 bg-success/5 p-3">
        <p class="mb-2 text-sm font-semibold text-success">Optimized</p>
        <div class="max-h-[520px] overflow-auto rounded border border-dark-border/60">
          <table class="w-full border-collapse text-xs font-mono">
            <tbody>
              <tr v-for="(line, index) in optimizedLines" :key="`optimized-${index}`">
                <td class="w-10 select-none border-r border-dark-border/60 px-2 py-1 text-right text-text-secondary">
                  {{ index + 1 }}
                </td>
                <td
                  class="px-2 py-1 align-top"
                  :class="changedOptimizedLineNumbers.has(index + 1) ? 'bg-success/15' : ''"
                  v-html="highlightLine(line)"
                />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </Card>
</template>
