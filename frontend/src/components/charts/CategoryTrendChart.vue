<script setup lang="ts">
import { computed } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip as ChartTooltip,
  Legend,
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, ChartTooltip, Legend);

interface TrendBucket {
  date: string;
  categories: Record<string, number>;
  // Legacy support
  weekStart?: string;
}

const props = withDefaults(
  defineProps<{
    trends: TrendBucket[];
    categoryColors: Record<string, string>;
    height?: number;
  }>(),
  { height: 340 },
);

const FALLBACK_COLORS = [
  '#6366f1', '#ef4444', '#eab308', '#10b981', '#f97316',
  '#8b5cf6', '#06b6d4', '#ec4899',
];

function formatDayLabel(d: string): string {
  const date = new Date(d + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatCategoryName(key: string): string {
  return key.split('_').map(p => p.charAt(0) + p.slice(1).toLowerCase()).join(' ');
}

function getDate(bucket: TrendBucket): string {
  return bucket.date || bucket.weekStart || '';
}

// Only show days that have at least one finding (skip empty days for cleaner chart)
const nonEmptyTrends = computed(() => {
  return props.trends.filter(t => Object.values(t.categories).some(v => v > 0));
});

// Collect all category keys that have at least one non-zero value
const activeCategories = computed(() => {
  const counts: Record<string, number> = {};
  for (const bucket of props.trends) {
    for (const [cat, val] of Object.entries(bucket.categories)) {
      counts[cat] = (counts[cat] || 0) + val;
    }
  }
  return Object.entries(counts)
    .filter(([, total]) => total > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([cat]) => cat);
});

// Per-category trend direction: compare first-half avg vs second-half avg
const categoryTrends = computed(() => {
  const result: Record<string, 'up' | 'down' | 'stable'> = {};
  const data = nonEmptyTrends.value;
  if (data.length < 2) return result;

  const mid = Math.floor(data.length / 2);
  for (const cat of activeCategories.value) {
    const firstHalf = data.slice(0, mid);
    const secondHalf = data.slice(mid);
    const avgFirst = firstHalf.reduce((s, w) => s + (w.categories[cat] || 0), 0) / firstHalf.length;
    const avgSecond = secondHalf.reduce((s, w) => s + (w.categories[cat] || 0), 0) / secondHalf.length;
    const diff = avgSecond - avgFirst;
    if (diff < -0.5) result[cat] = 'down';
    else if (diff > 0.5) result[cat] = 'up';
    else result[cat] = 'stable';
  }
  return result;
});

const chartConfig = computed(() => {
  const data = nonEmptyTrends.value;
  const labels = data.map(t => formatDayLabel(getDate(t)));

  const datasets = activeCategories.value.map((cat, i) => {
    const color = props.categoryColors[cat] || FALLBACK_COLORS[i % FALLBACK_COLORS.length];
    return {
      label: formatCategoryName(cat),
      data: data.map(t => t.categories[cat] || 0),
      borderColor: color,
      backgroundColor: color + '18',
      pointBackgroundColor: color,
      pointBorderColor: '#1c2026',
      pointBorderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 7,
      tension: 0.3,
      fill: false,
      borderWidth: 2.5,
    };
  });

  return {
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index' as const,
        intersect: false,
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: {
            color: 'rgba(255,255,255,0.4)',
            font: { size: 11 },
            stepSize: 1,
            precision: 0,
          },
        },
        x: {
          grid: { display: false },
          ticks: {
            color: 'rgba(255,255,255,0.4)',
            font: { size: 11 },
            maxRotation: 45,
          },
        },
      },
      plugins: {
        legend: {
          display: true,
          position: 'top' as const,
          align: 'end' as const,
          labels: {
            color: 'rgba(255,255,255,0.6)',
            font: { size: 11 },
            boxWidth: 12,
            boxHeight: 12,
            borderRadius: 3,
            useBorderRadius: true,
            padding: 16,
          },
        },
        tooltip: {
          backgroundColor: 'rgba(28, 32, 38, 0.95)',
          titleColor: '#dfe2eb',
          bodyColor: '#c0c7d4',
          borderColor: 'rgba(65, 71, 82, 0.5)',
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12,
        },
      },
    },
  };
});
</script>

<template>
  <div>
    <div :style="{ height: height + 'px' }">
      <Line v-if="nonEmptyTrends.length" :data="chartConfig.data" :options="chartConfig.options" />
      <div v-else class="flex items-center justify-center h-full text-outline text-sm">
        No trend data available
      </div>
    </div>

    <!-- Per-category trend indicators -->
    <div v-if="activeCategories.length && nonEmptyTrends.length >= 2" class="flex flex-wrap gap-2 mt-4">
      <div v-for="cat in activeCategories" :key="cat"
        class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium"
        :class="{
          'bg-green-500/10 text-green-400': categoryTrends[cat] === 'down',
          'bg-red-500/10 text-red-400': categoryTrends[cat] === 'up',
          'bg-surface-container text-outline': categoryTrends[cat] === 'stable',
        }">
        <span class="material-symbols-outlined" style="font-size: 14px">
          {{ categoryTrends[cat] === 'down' ? 'trending_down' : categoryTrends[cat] === 'up' ? 'trending_up' : 'trending_flat' }}
        </span>
        {{ formatCategoryName(cat) }}
      </div>
    </div>
  </div>
</template>
