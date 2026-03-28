<script setup lang="ts">
import { computed } from 'vue';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions
} from 'chart.js';
import { Line } from 'vue-chartjs';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface WeeklyData {
  week_start: string;
  week_end: string;
  avg_score: number;
  evaluation_count: number;
  finding_count: number;
}

const props = withDefaults(
  defineProps<{
    data: WeeklyData[];
    title?: string;
  }>(),
  {
    title: 'Progress Over Time'
  }
);

const chartData = computed(() => {
  const labels = props.data.map((d, idx) => {
    const date = new Date(d.week_start);
    const weekNum = Math.ceil((date.getTime() - new Date(date.getFullYear(), 0, 1).getTime()) / (7 * 24 * 60 * 60 * 1000));
    return `W${weekNum}`;
  });

  return {
    labels,
    datasets: [
      {
        label: 'Avg Score',
        data: props.data.map(d => d.avg_score),
        borderColor: 'rgba(162, 201, 255, 1)',
        backgroundColor: 'rgba(162, 201, 255, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: 'rgba(162, 201, 255, 1)',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
      },
      {
        label: 'Findings',
        data: props.data.map(d => d.finding_count),
        borderColor: 'rgba(251, 146, 60, 1)',
        backgroundColor: 'rgba(251, 146, 60, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: 'rgba(251, 146, 60, 1)',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        yAxisID: 'y1',
      }
    ]
  };
});

// @ts-ignore - Chart.js type compatibility
const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index' as const,
    intersect: false,
  },
  scales: {
    x: {
      grid: {
        color: 'rgba(148, 163, 184, 0.1)',
        drawBorder: false,
      },
      ticks: {
        color: '#64748b',
        font: {
          size: 11
        }
      }
    },
    y: {
      type: 'linear' as const,
      display: true,
      position: 'left' as const,
      beginAtZero: true,
      max: 100,
      grid: {
        color: 'rgba(148, 163, 184, 0.1)',
        drawBorder: false,
      },
      ticks: {
        color: '#64748b',
        callback: (value: number | string) => `${value}%`
      },
      title: {
        display: true,
        text: 'Average Score',
        color: '#cbd5e1',
        font: {
          size: 12,
          weight: 600
        }
      }
    },
    y1: {
      type: 'linear' as const,
      display: true,
      position: 'right' as const,
      beginAtZero: true,
      grid: {
        drawOnChartArea: false,
      },
      ticks: {
        color: '#64748b',
      },
      title: {
        display: true,
        text: 'Findings',
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
      display: true,
      position: 'top' as const,
      align: 'end' as const,
      labels: {
        color: '#cbd5e1',
        usePointStyle: true,
        padding: 15,
        font: {
          size: 12,
          weight: 600
        }
      }
    },
    tooltip: {
      backgroundColor: 'rgba(30, 41, 59, 0.95)',
      titleColor: '#f1f5f9',
      bodyColor: '#cbd5e1',
      borderColor: 'rgba(148, 163, 184, 0.2)',
      borderWidth: 1,
      padding: 12,
      displayColors: true,
      callbacks: {
        label: (context: any) => {
          const label = context.dataset.label || '';
          const value = context.parsed.y;
          if (label === 'Avg Score') {
            return `${label}: ${value}%`;
          }
          return `${label}: ${value}`;
        }
      }
    }
  }
}));
</script>

<template>
  <div class="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10">
    <h4 class="text-xl font-bold mb-6">{{ title }}</h4>
    <div class="w-full h-[300px]">
      <!-- @ts-ignore -->
      <Line v-if="data.length > 0" :data="chartData" :options="chartOptions" />
      <div v-else class="h-full flex items-center justify-center">
        <div class="text-center">
          <span class="material-symbols-outlined text-4xl text-outline mb-2">trending_up</span>
          <p class="text-sm text-outline">No progress data available</p>
        </div>
      </div>
    </div>
  </div>
</template>
