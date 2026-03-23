<script setup lang="ts">
import Card from '@/components/common/Card.vue';

const days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const calendarDays = Array.from({ length: 31 }, (_, i) => i + 1);
</script>

<template>
  <Card>
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-lg font-semibold">March 2026</h3>
      <span class="text-sm text-text-secondary">Review activity</span>
    </div>
    <div class="mb-2 grid grid-cols-7 gap-2 text-center text-xs text-text-secondary">
      <span v-for="day in days" :key="day">{{ day }}</span>
    </div>
    <div class="grid grid-cols-7 gap-2">
      <button
        v-for="day in calendarDays"
        :key="day"
        class="aspect-square rounded-md border border-dark-border text-sm hover:border-primary hover:text-primary"
      >
        {{ day }}
      </button>
    </div>
  </Card>
</template>
