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
    secondaryPoints?: DataPoint[];
    primaryColor?: string;
    secondaryColor?: string;
    width?: number;
    height?: number;
  }>(),
  {
    title: 'Trend Chart',
    primaryColor: '#58A6FF',
    secondaryColor: '#F78166',
    width: 640,
    height: 240,
  },
);

const padding = { top: 20, right: 20, bottom: 40, left: 36 };

const allValues = computed(() => {
  const values = props.points.map((p) => p.value);
  if (props.secondaryPoints) {
    values.push(...props.secondaryPoints.map((p) => p.value));
  }
  return values;
});

const maxValue = computed(() => Math.max(1, ...allValues.value));
const minValue = computed(() => Math.min(0, ...allValues.value));
const range = computed(() => Math.max(1, maxValue.value - minValue.value));
const chartWidth = computed(() => props.width - padding.left - padding.right);
const chartHeight = computed(() => props.height - padding.top - padding.bottom);

function computeChartPoints(points: DataPoint[]) {
  return points.map((point, index) => {
    const x =
      points.length <= 1
        ? padding.left + chartWidth.value / 2
        : padding.left + (index / (points.length - 1)) * chartWidth.value;
    const y =
      padding.top + ((maxValue.value - point.value) / range.value) * chartHeight.value;
    return { ...point, x, y };
  });
}

function computeLinePath(points: DataPoint[]) {
  const pts = computeChartPoints(points);
  if (!pts.length) return '';
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
}

const chartPoints = computed(() => computeChartPoints(props.points));
const secondaryChartPoints = computed(() =>
  props.secondaryPoints ? computeChartPoints(props.secondaryPoints) : [],
);

const linePath = computed(() => computeLinePath(props.points));
const secondaryLinePath = computed(() =>
  props.secondaryPoints ? computeLinePath(props.secondaryPoints) : '',
);

const areaPath = computed(() => {
  if (!chartPoints.value.length) return '';
  const last = chartPoints.value[chartPoints.value.length - 1];
  const first = chartPoints.value[0];
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
    <div class="rounded-lg border border-border bg-bg-darkest p-3">
      <svg :viewBox="`0 0 ${width} ${height}`" class="h-56 w-full">
        <line
          v-for="tick in yTicks"
          :key="`grid-${tick.y}`"
          :x1="padding.left"
          :x2="width - padding.right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="#30363D"
          stroke-width="1"
          stroke-dasharray="4 4"
        />
        <text
          v-for="tick in yTicks"
          :key="`label-${tick.y}`"
          :x="padding.left - 8"
          :y="tick.y + 4"
          fill="#8B949E"
          font-size="10"
          text-anchor="end"
        >
          {{ tick.value }}
        </text>
        <!-- Primary line + area -->
        <path v-if="areaPath" :d="areaPath" :fill="`${primaryColor}29`" />
        <path v-if="linePath" :d="linePath" fill="none" :stroke="primaryColor" stroke-width="2.5" />
        <circle
          v-for="point in chartPoints"
          :key="point.label"
          :cx="point.x"
          :cy="point.y"
          r="3.5"
          :fill="primaryColor"
        />
        <!-- Secondary line -->
        <path v-if="secondaryLinePath" :d="secondaryLinePath" fill="none" :stroke="secondaryColor" stroke-width="2.5" stroke-dasharray="6 3" />
        <circle
          v-for="point in secondaryChartPoints"
          :key="`s-${point.label}`"
          :cx="point.x"
          :cy="point.y"
          r="3.5"
          :fill="secondaryColor"
        />
        <!-- X-axis labels -->
        <text
          v-for="point in chartPoints"
          :key="`x-${point.label}`"
          :x="point.x"
          :y="height - 14"
          fill="#8B949E"
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
