<script setup lang="ts">
defineProps<{ open: boolean; title?: string }>();
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
    <div class="w-full max-w-lg rounded-xl border border-dark-border bg-dark-card p-5">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-lg font-semibold">{{ title }}</h3>
        <button class="text-text-secondary hover:text-white" @click="emit('close')">x</button>
      </div>
      <slot />
    </div>
  </div>
</template>
