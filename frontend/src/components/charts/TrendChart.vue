<script setup lang="ts">
import Card from '@/components/common/Card.vue';

defineProps<{ title?: string }>();
</script>

<template>
  <Card>
    <h3 class="mb-3 text-lg font-semibold">{{ title || 'Trend Chart' }}</h3>
    <div class="h-56 rounded-lg border border-dashed border-dark-border p-4">
      <div class="flex h-full items-end gap-3">
        <div class="h-[30%] w-8 rounded-t bg-primary"></div>
        <div class="h-[45%] w-8 rounded-t bg-primary"></div>
        <div class="h-[55%] w-8 rounded-t bg-primary"></div>
        <div class="h-[70%] w-8 rounded-t bg-primary"></div>
        <div class="h-[80%] w-8 rounded-t bg-primary"></div>
      </div>
    </div>
  </Card>
</template>
