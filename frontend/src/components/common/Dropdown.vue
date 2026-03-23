<script setup lang="ts">
defineProps<{
  modelValue: string | number | null;
  id?: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>();
</script>

<template>
  <div class="relative">
    <select
      :id="id"
      :disabled="disabled"
      :value="modelValue ?? ''"
      class="h-10 w-full appearance-none rounded-lg border border-border bg-bg-elevated px-3 pr-8 text-sm text-text-primary outline-none transition focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-60"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <slot />
    </select>
    <span class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-muted">v</span>
  </div>
</template>
