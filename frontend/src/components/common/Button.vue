<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'outlined' | 'danger';
  type?: 'button' | 'submit' | 'reset';
  disabled?: boolean;
}>();
</script>

<template>
  <button
    :type="type || 'button'"
    :disabled="disabled"
    :class="[
      'inline-flex items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
      variant === 'secondary' && 'border-border bg-bg-elevated text-text-primary hover:bg-secondary',
      variant === 'outlined' && 'border-border bg-transparent text-text-primary hover:border-primary hover:text-primary',
      variant === 'danger' && 'border-error bg-error text-white hover:opacity-90',
      (!variant || variant === 'primary') && 'border-primary bg-primary text-bg-darkest hover:border-primary-hover hover:bg-primary-hover',
    ]"
  >
    <slot />
  </button>
</template>
