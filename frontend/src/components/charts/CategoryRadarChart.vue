<script setup lang="ts">
import { computed } from 'vue';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  type ChartOptions,
} from 'chart.js';
import { Radar } from 'vue-chartjs';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip);

interface Skill {
  id: number;
  displayName: string;
  score: number;
  level: number;
  confidence?: number;
  confidenceLabel?: string;
  levelLabel?: string | null;
  observationCount?: number;
  provenConcepts?: number;
  relapsedConcepts?: number;
}

interface SkillCategory {
  id: number;
  name: string;
  displayName: string;
  description: string;
  icon: string;
  skills: Skill[];
}

const props = defineProps<{
  category: SkillCategory;
}>();

const emit = defineEmits<{
  'click-skill': [skillId: number];
}>();

const categoryAverage = computed(() => {
  if (!props.category.skills.length) return 0;
  const total = props.category.skills.reduce((sum, s) => sum + s.score, 0);
  return Math.round(total / props.category.skills.length);
});

function getAvgColor(avg: number): string {
  if (avg >= 80) return 'text-primary';
  if (avg >= 60) return 'text-green-500';
  if (avg >= 40) return 'text-yellow-500';
  return 'text-red-500';
}

function getLevelLabel(score: number, skill?: Skill): string {
  // Use API-provided label if available (from Bayesian algorithm)
  if (skill?.levelLabel) {
    return skill.levelLabel.charAt(0).toUpperCase() + skill.levelLabel.slice(1);
  }
  // No data at all — neither Bayesian nor legacy
  if (score <= 0) return 'No data';
  // Has legacy score but no Bayesian observations yet — use score-based labels
  if (score >= 85) return 'Master';
  if (score >= 70) return 'Expert';
  if (score >= 50) return 'Proficient';
  if (score >= 30) return 'Competent';
  if (score >= 15) return 'Beginner';
  return 'Novice';
}

function getLevelColor(label: string): string {
  switch (label) {
    case 'Master': return 'text-purple-400';
    case 'Expert': return 'text-primary';
    case 'Proficient': return 'text-green-500';
    case 'Competent': return 'text-yellow-500';
    case 'Beginner': return 'text-orange-500';
    case 'Novice': return 'text-red-500';
    case 'No data': return 'text-outline/50';
    default: return 'text-outline';
  }
}

function getConfidenceOpacity(skill: Skill): string {
  // If no Bayesian data yet but legacy score exists, show at full opacity
  if (!skill.observationCount && skill.score > 0) return 'opacity-100';
  const cl = skill.confidenceLabel || 'insufficient';
  switch (cl) {
    case 'verified': return 'opacity-100';
    case 'established': return 'opacity-100';
    case 'developing': return 'opacity-80';
    case 'preliminary': return 'opacity-60';
    default: return skill.score > 0 ? 'opacity-100' : 'opacity-40';
  }
}

const chartData = computed(() => ({
  labels: props.category.skills.map((s) => s.displayName),
  datasets: [
    {
      label: props.category.displayName,
      data: props.category.skills.map((s) => s.score),
      backgroundColor: 'rgba(162, 201, 255, 0.15)',
      borderColor: 'rgba(162, 201, 255, 0.9)',
      borderWidth: 2,
      pointBackgroundColor: props.category.skills.map((s) => {
        if (s.score >= 80) return 'rgba(96, 165, 250, 1)';
        if (s.score >= 60) return 'rgba(74, 222, 128, 1)';
        if (s.score >= 40) return 'rgba(250, 204, 21, 1)';
        return 'rgba(248, 113, 113, 1)';
      }),
      pointBorderColor: 'transparent',
      pointRadius: 5,
      pointHoverRadius: 7,
    },
  ],
}));

const chartOptions = computed<ChartOptions<'radar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      ticks: {
        stepSize: 25,
        color: 'rgba(148, 163, 184, 0.5)',
        backdropColor: 'transparent',
        font: { size: 9 },
      },
      grid: {
        color: 'rgba(148, 163, 184, 0.08)',
      },
      pointLabels: {
        color: '#94a3b8',
        font: { size: 10, weight: 600 },
        callback: (label: string) =>
          label.length > 14 ? label.slice(0, 12) + '…' : label,
      },
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(148, 163, 184, 0.2)',
      borderWidth: 1,
      padding: 10,
      displayColors: false,
      callbacks: {
        label: (ctx) => `${ctx.label}: ${ctx.parsed.r}/100`,
      },
    },
  },
}));
</script>

<template>
  <div
    class="bg-surface-container-low rounded-xl border border-outline-variant/10 hover:border-primary/20 transition-all flex flex-col"
  >
    <!-- Header -->
    <div class="flex items-center gap-3 px-5 pt-5 pb-3">
      <div class="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
        <span class="material-symbols-outlined text-primary text-lg">{{ category.icon }}</span>
      </div>
      <div class="flex-1 min-w-0">
        <h5 class="font-bold text-sm truncate">{{ category.displayName }}</h5>
        <p class="text-[10px] text-outline">{{ category.skills.length }} skills</p>
      </div>
      <div class="text-right shrink-0">
        <div class="text-xl font-black" :class="getAvgColor(categoryAverage)">
          {{ categoryAverage }}%
        </div>
      </div>
    </div>

    <!-- Radar -->
    <div v-if="category.skills.length >= 3" class="px-3 flex-1 min-h-0">
      <div class="h-[200px]">
        <Radar :data="chartData" :options="chartOptions" />
      </div>
    </div>

    <!-- Fallback for < 3 skills (radar needs at least 3 axes) -->
    <div v-else-if="category.skills.length > 0" class="px-5 pb-2 flex-1">
      <div v-for="skill in category.skills" :key="skill.id" class="py-2">
        <div class="flex justify-between text-xs mb-1">
          <span class="font-medium">{{ skill.displayName }}</span>
          <span class="text-outline">{{ skill.score }}%</span>
        </div>
        <div class="h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
          <div
            class="h-full rounded-full bg-primary transition-all duration-500"
            :style="{ width: skill.score + '%' }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="px-5 py-8 text-center flex-1">
      <span class="material-symbols-outlined text-xl text-outline">school</span>
      <p class="text-xs text-outline mt-1">No data yet</p>
    </div>

    <!-- Skill list (compact) -->
    <div
      v-if="category.skills.length"
      class="px-5 pb-4 pt-2 border-t border-outline-variant/5 space-y-1.5"
    >
      <div
        v-for="skill in category.skills"
        :key="skill.id"
        class="flex items-center justify-between text-xs cursor-pointer hover:bg-surface-container-lowest rounded px-2 py-1 -mx-2 transition-colors"
        :class="getConfidenceOpacity(skill)"
        @click="emit('click-skill', skill.id)"
      >
        <span class="text-on-surface-variant truncate mr-2">{{ skill.displayName }}</span>
        <div class="flex items-center gap-2 shrink-0">
          <span
            class="text-[10px] font-bold"
            :class="getLevelColor(getLevelLabel(skill.score, skill))"
          >
            {{ getLevelLabel(skill.score, skill) }}
          </span>
          <span v-if="skill.confidenceLabel === 'preliminary'" class="text-[8px] text-outline/50 italic">~</span>
          <span class="text-outline w-8 text-right">{{ Math.round(skill.score) }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>
