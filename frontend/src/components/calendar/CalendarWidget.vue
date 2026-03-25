<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import { api } from '@/composables/useApi';

const props = defineProps<{
  projectId?: number | null;
}>();

const emit = defineEmits<{
  dateSelected: [date: string | null];
}>();

const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

const currentMonth = ref(new Date());
const activeDates = ref<Set<string>>(new Set());
const selectedDate = ref<string | null>(null);
const today = new Date().toISOString().split('T')[0];

const monthString = computed(() => {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
});

const monthName = computed(() =>
  currentMonth.value.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
);

const firstDayOffset = computed(() => {
  return new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth(), 1).getDay();
});

const daysInMonth = computed(() =>
  new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 0).getDate(),
);

const calendarCells = computed(() => {
  const blanks = Array.from({ length: firstDayOffset.value }, () => null);
  const monthDays = Array.from({ length: daysInMonth.value }, (_, i) => i + 1);
  return [...blanks, ...monthDays];
});

async function fetchActiveDates() {
  if (!props.projectId) {
    activeDates.value = new Set();
    return;
  }
  try {
    const { data } = await api.reviews.calendar(props.projectId, monthString.value);
    activeDates.value = new Set(data.dates);
  } catch {
    activeDates.value = new Set();
  }
}

function toDateString(day: number): string {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  const paddedDay = String(day).padStart(2, '0');
  return `${year}-${month}-${paddedDay}`;
}

function isHighlighted(day: number) {
  return activeDates.value.has(toDateString(day));
}

function isToday(day: number) {
  return toDateString(day) === today;
}

function isSelected(day: number) {
  return toDateString(day) === selectedDate.value;
}

function selectDate(day: number) {
  const dateStr = toDateString(day);
  if (selectedDate.value === dateStr) {
    selectedDate.value = null;
    emit('dateSelected', null);
  } else {
    selectedDate.value = dateStr;
    emit('dateSelected', dateStr);
  }
}

function prevMonth() {
  currentMonth.value = new Date(
    currentMonth.value.getFullYear(),
    currentMonth.value.getMonth() - 1,
    1
  );
}

function nextMonth() {
  currentMonth.value = new Date(
    currentMonth.value.getFullYear(),
    currentMonth.value.getMonth() + 1,
    1
  );
}

onMounted(fetchActiveDates);
watch(() => props.projectId, () => {
  selectedDate.value = null;
  fetchActiveDates();
});
watch(monthString, fetchActiveDates);
</script>

<template>
  <div class="bg-surface-container-lowest rounded-xl p-3 border border-outline-variant/10">
    <!-- Month Navigation -->
    <div class="flex items-center justify-between mb-3">
      <span class="text-[10px] uppercase tracking-widest text-outline font-bold">{{ monthName }}</span>
      <div class="flex gap-1">
        <button @click="prevMonth" class="p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors">
          <span class="material-symbols-outlined text-sm">chevron_left</span>
        </button>
        <button @click="nextMonth" class="p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors">
          <span class="material-symbols-outlined text-sm">chevron_right</span>
        </button>
      </div>
    </div>

    <!-- Day Headers -->
    <div class="grid grid-cols-7 gap-1 text-center mb-2">
      <span v-for="day in days" :key="day" class="text-[8px] text-outline">
        {{ day }}
      </span>
    </div>

    <!-- Calendar Grid -->
    <div class="grid grid-cols-7 gap-1 text-[10px]">
      <button
        v-for="(day, index) in calendarCells"
        :key="`cell-${index}`"
        :disabled="!day"
        :class="[
          'p-1 text-center rounded transition-all',
          !day && 'invisible',
          day && isToday(day) && !isSelected(day) && 'bg-primary text-on-primary font-bold shadow-lg shadow-primary/20',
          day && isSelected(day) && 'ring-2 ring-primary bg-primary/20 text-primary font-bold',
          day && !isToday(day) && !isSelected(day) && isHighlighted(day) && 'bg-primary-container/20 text-primary border border-primary/30 hover:bg-primary-container/40 cursor-pointer',
          day && !isToday(day) && !isSelected(day) && !isHighlighted(day) && 'text-on-surface-variant hover:bg-surface-container cursor-pointer',
        ]"
        @click="day && selectDate(day)"
      >
        {{ day || '' }}
      </button>
    </div>

    <!-- Selected Date Indicator -->
    <div v-if="selectedDate" class="mt-3 pt-3 border-t border-outline-variant/10">
      <div class="flex items-center justify-between">
        <span class="text-[10px] text-primary font-bold">Filtering: {{ selectedDate }}</span>
        <button @click="selectDate(parseInt(selectedDate.split('-')[2]))" class="text-[10px] text-outline hover:text-error">
          Clear
        </button>
      </div>
    </div>
  </div>
</template>
