<script setup lang="ts">
import { computed } from 'vue';
import Card from '@/components/common/Card.vue';

interface DataPoint {
  label: string;
  value: number;
}

const props = withDefaults(
  defineProps<{
    title?: string;
    points: DataPoint[];
    width?: number;
    height?: number;
  }>(),
  {
    title: 'Trend Chart',
    width: 640,
    height: 240,
  },
);

const padding = { top: 20, right: 20, bottom: 40, left: 36 };

const maxValue = computed(() => Math.max(1, ...props.points.map((point) => point.value)));
const minValue = computed(() => Math.min(0, ...props.points.map((point) => point.value)));
const range = computed(() => Math.max(1, maxValue.value - minValue.value));
const chartWidth = computed(() => props.width - padding.left - padding.right);
const chartHeight = computed(() => props.height - padding.top - padding.bottom);

const chartPoints = computed(() =>
  props.points.map((point, index) => {
    const x =
      props.points.length <= 1
        ? padding.left + chartWidth.value / 2
        : padding.left + (index / (props.points.length - 1)) * chartWidth.value;
    const y =
      padding.top + ((maxValue.value - point.value) / range.value) * chartHeight.value;
    return { ...point, x, y };
  }),
);

const linePath = computed(() => {
  if (!chartPoints.value.length) return '';
  return chartPoints.value
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
    .join(' ');
});

const areaPath = computed(() => {
  if (!chartPoints.value.length) return '';
  const first = chartPoints.value[0];
  const last = chartPoints.value[chartPoints.value.length - 1];
  const baseline = props.height - padding.bottom;
  return `${linePath.value} L ${last.x} ${baseline} L ${first.x} ${baseline} Z`;
});

const yTicks = computed(() => {
  const steps = 4;
  return Array.from({ length: steps + 1 }, (_, index) => {
    const value = minValue.value + ((range.value / steps) * index);
    const y = padding.top + chartHeight.value - (index / steps) * chartHeight.value;
    return { value: Math.round(value), y };
  });
});
</script>

<template>
  <Card>
    <h3 class="mb-3 text-lg font-semibold">{{ title }}</h3>
    <div class="rounded-lg border border-dark-border bg-dark-bg p-3">
      <svg :viewBox="`0 0 ${width} ${height}`" class="h-56 w-full">
        <line
          v-for="tick in yTicks"
          :key="`grid-${tick.y}`"
          :x1="padding.left"
          :x2="width - padding.right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="#374151"
          stroke-width="1"
          stroke-dasharray="4 4"
        />
        <text
          v-for="tick in yTicks"
          :key="`label-${tick.y}`"
          :x="padding.left - 8"
          :y="tick.y + 4"
          fill="#9CA3AF"
          font-size="10"
          text-anchor="end"
        >
          {{ tick.value }}
        </text>
        <path v-if="areaPath" :d="areaPath" fill="rgba(34, 211, 238, 0.15)" />
        <path v-if="linePath" :d="linePath" fill="none" stroke="#22d3ee" stroke-width="2.5" />
        <circle
          v-for="point in chartPoints"
          :key="point.label"
          :cx="point.x"
          :cy="point.y"
          r="3.5"
          fill="#22d3ee"
        />
        <text
          v-for="point in chartPoints"
          :key="`x-${point.label}`"
          :x="point.x"
          :y="height - 14"
          fill="#9CA3AF"
          font-size="10"
          text-anchor="middle"
        >
          {{ point.label }}
        </text>
      </svg>
      <p v-if="!points.length" class="px-2 pb-1 text-sm text-text-secondary">
        No trend data yet for this selection.
      </p>
    </div>
  </Card>
</template>
