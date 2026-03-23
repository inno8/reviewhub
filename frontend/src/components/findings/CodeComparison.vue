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
    <h3 class="mb-4 text-lg font-semibold">Code Comparison</h3>
    <div class="grid gap-4 lg:grid-cols-2">
      <div class="rounded-lg border border-border bg-bg-darkest p-3">
        <p class="mb-2 text-sm font-semibold text-error">Original</p>
        <div class="max-h-[520px] overflow-auto rounded border border-border/70">
          <table class="code-panel w-full border-collapse text-[13px]">
            <tbody>
              <tr v-for="(line, index) in originalLines" :key="`original-${index}`">
                <td class="line-number border-r border-border/70 px-2 py-1">
                  {{ index + 1 }}
                </td>
                <td
                  class="px-2 py-1 align-top"
                  :class="changedOriginalLineNumbers.has(index + 1) ? 'line-deleted' : ''"
                  v-html="highlightLine(line)"
                />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="rounded-lg border border-border bg-bg-darkest p-3">
        <p class="mb-2 text-sm font-semibold text-success">Optimized</p>
        <div class="max-h-[520px] overflow-auto rounded border border-border/70">
          <table class="code-panel w-full border-collapse text-[13px]">
            <tbody>
              <tr v-for="(line, index) in optimizedLines" :key="`optimized-${index}`">
                <td class="line-number border-r border-border/70 px-2 py-1">
                  {{ index + 1 }}
                </td>
                <td
                  class="px-2 py-1 align-top"
                  :class="changedOptimizedLineNumbers.has(index + 1) ? 'line-added' : ''"
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
