<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Radar } from 'vue-chartjs';

ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

interface CategoryScore {
  category: string;
  score: number;
  color?: string;
}

const props = withDefaults(
  defineProps<{
    data: CategoryScore[];
    title?: string;
  }>(),
  {
    title: 'Skill Categories'
  }
);

const chartData = computed(() => ({
  labels: props.data.map(d => d.category),
  datasets: [
    {
      label: 'Skill Score',
      data: props.data.map(d => d.score),
      backgroundColor: 'rgba(162, 201, 255, 0.2)',
      borderColor: 'rgba(162, 201, 255, 1)',
      borderWidth: 2,
      pointBackgroundColor: 'rgba(162, 201, 255, 1)',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: 'rgba(162, 201, 255, 1)',
      pointRadius: 4,
      pointHoverRadius: 6,
    }
  ]
}));

const chartOptions = computed<ChartOptions<'radar'>>(() => ({
  responsive: true,
  maintainAspectRatio: true,
  scales: {
    r: {
      beginAtZero: true,
      max: 100,
      ticks: {
        stepSize: 20,
        color: '#64748b',
        backdropColor: 'transparent',
      },
      grid: {
        color: 'rgba(148, 163, 184, 0.1)',
      },
      pointLabels: {
        color: '#cbd5e1',
        font: {
          size: 12,
          weight: 600
        }
      }
    }
  },
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'rgba(30, 41, 59, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(148, 163, 184, 0.2)',
      borderWidth: 1,
      padding: 12,
      displayColors: false,
      callbacks: {
        label: (context) => `Score: ${context.parsed.r}/100`
      }
    }
  }
}));
</script>

<template>
  <div class="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10">
    <h4 class="text-xl font-bold mb-6">{{ title }}</h4>
    <div class="w-full h-[400px] flex items-center justify-center">
      <Radar v-if="data.length > 0" :data="chartData" :options="chartOptions" />
      <div v-else class="text-center">
        <span class="material-symbols-outlined text-4xl text-outline mb-2">radar</span>
        <p class="text-sm text-outline">No skill data available</p>
      </div>
    </div>
  </div>
</template>
