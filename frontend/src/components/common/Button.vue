<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'danger';
  type?: 'button' | 'submit' | 'reset';
  disabled?: boolean;
}>();
</script>

<template>
  <button
    :type="type || 'button'"
    :disabled="disabled"
    :class="[
      'rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
      variant === 'secondary' && 'bg-dark-border text-white hover:bg-secondary',
      variant === 'danger' && 'bg-error text-white hover:opacity-90',
      (!variant || variant === 'primary') && 'bg-primary text-dark-bg hover:opacity-90',
    ]"
  >
    <slot />
  </button>
</template>
