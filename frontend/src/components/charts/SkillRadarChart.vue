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
  /** Backend flag: confidence < 0.15 (CONFIDENCE_PRELIMINARY). When all
   * spokes are preliminary the whole shape is faded; per-spoke we
   * dotted-outline the point to flag low-evidence categories. */
  is_preliminary?: boolean;
  confidence?: number;
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

// Honesty pass: if every spoke is preliminary, fade the whole dataset
// (light fill, dashed border) so a teacher reading it knows we're
// guessing from too few observations. Per-spoke, paint preliminary
// points with the muted ring instead of the bright primary color.
const allPreliminary = computed(() =>
  props.data.length > 0 && props.data.every(d => d.is_preliminary === true),
);

const chartData = computed(() => {
  const PRIMARY = 'rgba(162, 201, 255, 1)';
  const PRIMARY_FILL = 'rgba(162, 201, 255, 0.2)';
  const MUTED = 'rgba(148, 163, 184, 0.7)';
  const MUTED_FILL = 'rgba(148, 163, 184, 0.08)';
  return {
    labels: props.data.map(d => d.category),
    datasets: [
      {
        label: 'Skill Score',
        data: props.data.map(d => d.score),
        backgroundColor: allPreliminary.value ? MUTED_FILL : PRIMARY_FILL,
        borderColor: allPreliminary.value ? MUTED : PRIMARY,
        borderWidth: 2,
        borderDash: allPreliminary.value ? [4, 4] : [],
        // Per-point colors so individual preliminary spokes stay
        // visually distinguishable inside an otherwise confident chart.
        pointBackgroundColor: props.data.map(d =>
          d.is_preliminary ? MUTED : PRIMARY,
        ),
        pointBorderColor: props.data.map(d =>
          d.is_preliminary ? 'rgba(148, 163, 184, 0.4)' : '#fff',
        ),
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: PRIMARY,
        pointRadius: 4,
        pointHoverRadius: 6,
      },
    ],
  };
});

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
        label: (context) => {
          const item = props.data[context.dataIndex];
          const lines = [`Score: ${context.parsed.r}/100`];
          if (item?.is_preliminary) {
            lines.push('Voorlopig — te weinig observaties.');
          }
          return lines;
        },
      },
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
    <p
      v-if="allPreliminary"
      class="mt-3 text-[11px] text-on-surface-variant text-center italic"
      data-testid="radar-preliminary-banner"
    >
      Voorlopige scores. Verschijnt definitief zodra elke categorie meer observaties heeft.
    </p>
  </div>
</template>
