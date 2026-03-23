<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import Card from '@/components/common/Card.vue';
import { api } from '@/composables/useApi';

const days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const props = defineProps<{ projectId: number | null; compact?: boolean }>();
const emit = defineEmits<{ (e: 'select-date', date: string): void }>();

const currentMonth = ref(new Date());
const selectedDate = ref('');
const activeDates = ref<Set<string>>(new Set());

const monthLabel = computed(() =>
  currentMonth.value.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }),
);
const monthKey = computed(() => {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
});

const firstDayOffset = computed(() => {
  const day = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth(), 1).getDay();
  return day === 0 ? 6 : day - 1;
});

const daysInMonth = computed(() =>
  new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 0).getDate(),
);

const calendarCells = computed(() => {
  const blanks = Array.from({ length: firstDayOffset.value }, () => null);
  const monthDays = Array.from({ length: daysInMonth.value }, (_, i) => i + 1);
  return [...blanks, ...monthDays];
});

function toDateString(day: number): string {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  const paddedDay = String(day).padStart(2, '0');
  return `${year}-${month}-${paddedDay}`;
}

function isHighlighted(day: number) {
  return activeDates.value.has(toDateString(day));
}

function isSelected(day: number) {
  return selectedDate.value === toDateString(day);
}

async function fetchCalendarDates() {
  if (!props.projectId) {
    activeDates.value = new Set();
    return;
  }
  const { data } = await api.reviews.calendar(props.projectId, monthKey.value);
  activeDates.value = new Set<string>(data.dates || []);
}

function prevMonth() {
  currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() - 1, 1);
}

function nextMonth() {
  currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 1);
}

function onSelectDay(day: number) {
  const date = toDateString(day);
  selectedDate.value = selectedDate.value === date ? '' : date;
  emit('select-date', selectedDate.value);
}

onMounted(fetchCalendarDates);
watch(() => props.projectId, fetchCalendarDates);
watch(monthKey, fetchCalendarDates);
</script>

<template>
  <Card :class="props.compact ? 'p-0' : ''">
    <div class="mb-3 flex items-center justify-between">
      <h3 :class="props.compact ? 'text-sm font-semibold' : 'text-lg font-semibold'">{{ monthLabel }}</h3>
      <div class="flex items-center gap-2">
        <button class="rounded border border-border px-2 py-1 text-xs text-text-secondary transition hover:border-primary hover:text-primary" @click="prevMonth">
          <
        </button>
        <button class="rounded border border-border px-2 py-1 text-xs text-text-secondary transition hover:border-primary hover:text-primary" @click="nextMonth">
          >
        </button>
      </div>
    </div>
    <div v-if="!props.compact" class="mb-3">
      <span class="text-sm text-text-secondary">Review activity</span>
    </div>
    <div class="mb-2 grid grid-cols-7 gap-1 text-center text-[11px] text-text-secondary">
      <span v-for="day in days" :key="day">{{ day }}</span>
    </div>
    <div class="grid grid-cols-7 gap-1">
      <button
        v-for="(day, index) in calendarCells"
        :key="`${monthKey}-${index}`"
        :disabled="!day"
        :class="[
          props.compact ? 'aspect-square rounded border text-xs' : 'aspect-square rounded-md border text-sm',
          day ? 'border-border text-text-secondary hover:border-primary hover:text-primary' : 'border-transparent',
          day && isHighlighted(day) && 'border-primary/80 bg-primary/20 text-primary',
          day && isSelected(day) && 'ring-2 ring-primary',
        ]"
        @click="day && onSelectDay(day)"
      >
        {{ day || '' }}
      </button>
    </div>
  </Card>
</template>
