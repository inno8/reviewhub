<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { api } from '@/composables/useApi';

interface Deduction {
  findingId: number;
  explanation: string;
  impact: number;
  keyword: string;
  type: 'positive' | 'negative';
  filePath: string;
  date: string;
}

interface BreakdownData {
  skill: {
    id: number;
    name: string;
    displayName: string;
    description: string;
    category: {
      id: number;
      name: string;
      displayName: string;
      icon: string;
    };
  };
  score: number;
  level: number;
  baseScore: number;
  deductions: Deduction[];
  tips: string[];
}

const props = defineProps<{
  open: boolean;
  userId: number;
  skillId: number | null;
  projectId: number;
}>();

const emit = defineEmits<{
  close: [];
}>();

const loading = ref(false);
const breakdown = ref<BreakdownData | null>(null);

watch(
  () => [props.open, props.skillId],
  async () => {
    if (props.open && props.skillId) {
      loading.value = true;
      try {
        const { data } = await api.skills.breakdown(props.userId, props.skillId, props.projectId);
        breakdown.value = data;
      } catch (e) {
        console.error('Failed to load skill breakdown', e);
        breakdown.value = null;
      } finally {
        loading.value = false;
      }
    }
  },
  { immediate: true },
);

const levelLabel = computed(() => {
  if (!breakdown.value) return '';
  const s = breakdown.value.score;
  if (s >= 90) return 'Expert';
  if (s >= 75) return 'Advanced';
  if (s >= 50) return 'Intermediate';
  if (s >= 25) return 'Developing';
  return 'Beginner';
});

const scoreColor = computed(() => {
  if (!breakdown.value) return 'text-outline';
  const s = breakdown.value.score;
  if (s >= 90) return 'text-primary';
  if (s >= 75) return 'text-green-500';
  if (s >= 50) return 'text-yellow-500';
  if (s >= 25) return 'text-orange-500';
  return 'text-red-500';
});

const barColor = computed(() => {
  if (!breakdown.value) return 'bg-outline';
  const s = breakdown.value.score;
  if (s >= 90) return 'bg-primary';
  if (s >= 75) return 'bg-green-500';
  if (s >= 50) return 'bg-yellow-500';
  if (s >= 25) return 'bg-orange-500';
  return 'bg-red-500';
});

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function truncate(text: string | undefined | null, max: number): string {
  if (!text) return '';
  return text.length > max ? text.slice(0, max) + '...' : text;
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center"
      @click.self="emit('close')"
    >
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/50" @click="emit('close')"></div>

      <!-- Dialog -->
      <div class="relative bg-surface-container rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col mx-4">
        <!-- Header -->
        <div v-if="breakdown" class="p-6 border-b border-outline-variant/10">
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <span class="material-symbols-outlined text-primary">{{ breakdown.skill.category.icon }}</span>
              </div>
              <div>
                <h3 class="text-lg font-bold">{{ breakdown.skill.displayName }}</h3>
                <p class="text-xs text-outline">{{ breakdown.skill.category.displayName }}</p>
              </div>
            </div>
            <button @click="emit('close')" class="p-1 rounded-lg hover:bg-surface-container-highest transition-colors">
              <span class="material-symbols-outlined text-outline">close</span>
            </button>
          </div>

          <!-- Score display -->
          <div class="mt-4 flex items-center gap-4">
            <div class="flex items-baseline gap-1">
              <span class="text-3xl font-black" :class="scoreColor">{{ breakdown.score }}</span>
              <span class="text-sm text-outline">/100</span>
            </div>
            <span class="px-2 py-0.5 rounded-full text-xs font-bold" :class="[barColor, 'text-white']">
              {{ levelLabel }}
            </span>
            <div class="flex-1">
              <div class="h-2 bg-surface-container-highest rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500" :class="barColor" :style="{ width: breakdown.score + '%' }"></div>
              </div>
            </div>
          </div>

          <!-- Score formula -->
          <p class="mt-2 text-xs text-outline">
            Base {{ breakdown.baseScore }}
            <template v-for="d in breakdown.deductions" :key="d.findingId + d.keyword">
              <span :class="d.impact > 0 ? 'text-green-500' : 'text-red-400'">
                {{ d.impact > 0 ? '+' : '' }}{{ d.impact }}
              </span>
            </template>
            = {{ breakdown.score }}
          </p>
        </div>

        <!-- Loading state -->
        <div v-if="loading" class="p-12 text-center">
          <span class="material-symbols-outlined text-3xl text-outline animate-spin">progress_activity</span>
          <p class="mt-2 text-sm text-outline">Loading breakdown...</p>
        </div>

        <!-- Content -->
        <div v-else-if="breakdown" class="flex-1 overflow-y-auto p-6 space-y-6">
          <!-- Description -->
          <div>
            <p class="text-sm text-on-surface/80">{{ breakdown.skill.description }}</p>
          </div>

          <!-- Deductions / Impacts -->
          <div v-if="breakdown.deductions.length">
            <h4 class="text-sm font-bold mb-3 flex items-center gap-2">
              <span class="material-symbols-outlined text-sm">receipt_long</span>
              Score Impacts ({{ breakdown.deductions.length }})
            </h4>
            <div class="space-y-2">
              <div
                v-for="(d, i) in breakdown.deductions"
                :key="i"
                class="p-3 rounded-xl border border-outline-variant/10 bg-surface-container-lowest"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span
                        class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold"
                        :class="d.type === 'negative' ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-500'"
                      >
                        <span class="material-symbols-outlined text-xs">{{ d.type === 'negative' ? 'remove' : 'add' }}</span>
                        {{ Math.abs(d.impact) }} pts
                      </span>
                      <span class="text-[10px] text-outline px-1.5 py-0.5 bg-surface-container rounded">{{ d.keyword }}</span>
                      <span class="text-[10px] text-outline ml-auto flex-shrink-0">{{ formatDate(d.date) }}</span>
                    </div>
                    <p class="text-xs text-on-surface/70 leading-relaxed">{{ truncate(d.explanation, 150) }}</p>
                    <p class="text-[10px] text-outline mt-1 font-mono">{{ d.filePath }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="text-center py-6">
            <span class="material-symbols-outlined text-3xl text-outline">check_circle</span>
            <p class="text-sm text-outline mt-2">No findings affecting this skill. Score is at baseline.</p>
          </div>

          <!-- Tips -->
          <div v-if="breakdown.tips.length">
            <h4 class="text-sm font-bold mb-3 flex items-center gap-2">
              <span class="material-symbols-outlined text-sm">lightbulb</span>
              Improvement Tips
            </h4>
            <ul class="space-y-2">
              <li
                v-for="(tip, i) in breakdown.tips"
                :key="i"
                class="flex items-start gap-2 text-sm text-on-surface/80"
              >
                <span class="material-symbols-outlined text-xs text-primary mt-0.5">arrow_right</span>
                {{ tip }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
