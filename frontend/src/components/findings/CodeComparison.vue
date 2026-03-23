<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  originalCode: string;
  optimizedCode: string;
  filePath?: string;
}>();

const originalLines = computed(() => props.originalCode?.split('\n') || []);
const optimizedLines = computed(() => props.optimizedCode?.split('\n') || []);

// Find which lines differ
const changedLines = computed(() => {
  const changed = new Set<number>();
  const maxLen = Math.max(originalLines.value.length, optimizedLines.value.length);
  for (let i = 0; i < maxLen; i++) {
    if ((originalLines.value[i] || '') !== (optimizedLines.value[i] || '')) {
      changed.add(i);
    }
  }
  return changed;
});
</script>

<template>
  <section class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <!-- Left: Original -->
    <div class="bg-surface-container-low rounded-xl overflow-hidden flex flex-col border border-outline-variant/10">
      <div class="px-4 py-2 bg-surface-container-highest/50 flex items-center gap-2 border-b border-outline-variant/10">
        <span class="text-xs font-bold uppercase tracking-widest text-outline">Original Code</span>
      </div>
      <div class="p-4 font-mono text-sm overflow-x-auto leading-relaxed">
        <div class="flex gap-4">
          <div class="text-outline/40 text-right select-none w-8">
            <div v-for="(_, idx) in originalLines" :key="`orig-num-${idx}`">{{ idx + 1 }}</div>
          </div>
          <div class="flex-1 whitespace-pre">
            <div
              v-for="(line, idx) in originalLines"
              :key="`orig-line-${idx}`"
              :class="changedLines.has(idx) ? 'bg-error/20 -mx-4 px-4 border-l-2 border-error' : ''"
            >{{ line || ' ' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Optimized -->
    <div class="bg-surface-container rounded-xl overflow-hidden flex flex-col border border-primary/20 ring-1 ring-primary/10">
      <div class="px-4 py-2 bg-primary/10 flex items-center justify-between border-b border-primary/20">
        <span class="text-xs font-bold uppercase tracking-widest text-primary">Optimized Fix</span>
        <span class="text-[10px] bg-primary text-on-primary px-1.5 py-0.5 rounded font-bold">RECOMMENDED</span>
      </div>
      <div class="p-4 font-mono text-sm overflow-x-auto leading-relaxed">
        <div class="flex gap-4">
          <div class="text-outline/40 text-right select-none w-8">
            <div v-for="(_, idx) in optimizedLines" :key="`opt-num-${idx}`">{{ idx + 1 }}</div>
          </div>
          <div class="flex-1 whitespace-pre">
            <div
              v-for="(line, idx) in optimizedLines"
              :key="`opt-line-${idx}`"
              :class="changedLines.has(idx) ? 'bg-primary/10 -mx-4 px-4 border-l-2 border-primary' : ''"
            >{{ line || ' ' }}</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
