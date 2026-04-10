<script setup lang="ts">
import { computed } from 'vue';

interface Pattern {
  id: number;
  pattern_type: string;
  pattern_key: string;
  frequency: number;
  first_seen: string;
  last_seen: string;
  is_resolved: boolean;
}

const props = defineProps<{
  patterns: Pattern[];
}>();

const unresolvedPatterns = computed(() =>
  props.patterns
    .filter(p => !p.is_resolved)
    .sort((a, b) => b.frequency - a.frequency)
    .slice(0, 8)
);

function daysSince(dateStr: string): number {
  const now = new Date();
  const then = new Date(dateStr);
  return Math.floor((now.getTime() - then.getTime()) / 86400000);
}

function relativeTime(dateStr: string): string {
  const days = daysSince(dateStr);
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function frequencyIntensity(freq: number): string {
  if (freq >= 10) return 'bg-red-500/15 border-red-500/20 text-red-400';
  if (freq >= 5) return 'bg-orange-500/15 border-orange-500/20 text-orange-400';
  if (freq >= 3) return 'bg-yellow-500/15 border-yellow-500/20 text-yellow-400';
  return 'bg-surface-container border-outline-variant/20 text-on-surface-variant';
}

function formatPatternType(type: string): string {
  return type.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}
</script>

<template>
  <div v-if="unresolvedPatterns.length">
    <div class="space-y-2">
      <div v-for="p in unresolvedPatterns" :key="p.id"
        class="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all"
        :class="frequencyIntensity(p.frequency)">
        <!-- Frequency pill -->
        <div class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-black text-sm"
          :class="{
            'bg-red-500/20 text-red-400': p.frequency >= 10,
            'bg-orange-500/20 text-orange-400': p.frequency >= 5 && p.frequency < 10,
            'bg-yellow-500/20 text-yellow-400': p.frequency >= 3 && p.frequency < 5,
            'bg-surface-container-high text-outline': p.frequency < 3,
          }">
          {{ p.frequency }}x
        </div>

        <!-- Details -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface-container-high text-outline">
              {{ formatPatternType(p.pattern_type) }}
            </span>
          </div>
          <p class="text-sm font-medium truncate">{{ p.pattern_key }}</p>
        </div>

        <!-- Recency -->
        <div class="flex-shrink-0 text-right">
          <p class="text-xs font-medium">{{ relativeTime(p.last_seen) }}</p>
          <p class="text-[10px] text-outline">last seen</p>
        </div>

        <!-- Status icon -->
        <span class="material-symbols-outlined text-sm flex-shrink-0"
          :class="daysSince(p.last_seen) > 14 ? 'text-green-400' : 'text-outline'">
          {{ daysSince(p.last_seen) > 14 ? 'check_circle' : 'warning' }}
        </span>
      </div>
    </div>

    <!-- Hint -->
    <p class="text-[10px] text-outline mt-3 flex items-center gap-1">
      <span class="material-symbols-outlined" style="font-size: 12px">info</span>
      Patterns not seen for 14+ days show a green check — keep it up!
    </p>
  </div>

  <div v-else class="text-center py-8">
    <span class="material-symbols-outlined text-4xl text-green-400 mb-2">verified</span>
    <p class="text-sm text-outline">No recurring error patterns detected</p>
  </div>
</template>
