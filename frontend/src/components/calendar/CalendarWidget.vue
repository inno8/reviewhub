<script setup lang="ts">
import { computed, ref } from 'vue';

const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

const currentMonth = ref(new Date());

// Simulated active dates (dates with review activity)
const activeDates = new Set(['2026-03-08', '2026-03-11', '2026-03-16', '2026-03-19']);
const today = new Date().toISOString().split('T')[0];

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

function toDateString(day: number): string {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  const paddedDay = String(day).padStart(2, '0');
  return `${year}-${month}-${paddedDay}`;
}

function isHighlighted(day: number) {
  return activeDates.has(toDateString(day));
}

function isToday(day: number) {
  return toDateString(day) === today;
}
</script>

<template>
  <div class="bg-surface-container-lowest rounded-xl p-3 border border-outline-variant/10">
    <!-- Day Headers -->
    <div class="grid grid-cols-7 gap-1 text-center mb-2">
      <span v-for="day in days" :key="day" class="text-[8px] text-outline">
        {{ day }}
      </span>
    </div>

    <!-- Calendar Grid -->
    <div class="grid grid-cols-7 gap-1 text-[10px]">
      <span
        v-for="(day, index) in calendarCells"
        :key="`cell-${index}`"
        :class="[
          'p-1 text-center',
          !day && 'invisible',
          day && isToday(day) && 'bg-primary text-on-primary font-bold rounded shadow-lg shadow-primary/20',
          day && !isToday(day) && isHighlighted(day) && 'rounded bg-primary-container/20 text-primary border border-primary/30',
          day && !isToday(day) && !isHighlighted(day) && 'text-on-surface-variant',
        ]"
      >
        {{ day || '' }}
      </span>
    </div>
  </div>
</template>
