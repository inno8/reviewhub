<script setup lang="ts">
import { computed } from 'vue';
import hljs from 'highlight.js/lib/core';
import typescript from 'highlight.js/lib/languages/typescript';
import javascript from 'highlight.js/lib/languages/javascript';
import Card from '@/components/common/Card.vue';

hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('javascript', javascript);

const props = defineProps<{ originalCode: string; optimizedCode: string }>();

const highlightedOriginal = computed(() => hljs.highlightAuto(props.originalCode).value);
const highlightedOptimized = computed(() => hljs.highlightAuto(props.optimizedCode).value);
</script>

<template>
  <Card>
    <h3 class="mb-3 text-lg font-semibold">Code Comparison</h3>
    <div class="grid gap-4 lg:grid-cols-2">
      <div class="rounded-lg border border-error/40 bg-error/5 p-3">
        <p class="mb-2 text-sm font-semibold text-error">Original</p>
        <pre class="overflow-auto text-xs font-mono"><code v-html="highlightedOriginal" /></pre>
      </div>
      <div class="rounded-lg border border-success/40 bg-success/5 p-3">
        <p class="mb-2 text-sm font-semibold text-success">Optimized</p>
        <pre class="overflow-auto text-xs font-mono"><code v-html="highlightedOptimized" /></pre>
      </div>
    </div>
  </Card>
</template>
