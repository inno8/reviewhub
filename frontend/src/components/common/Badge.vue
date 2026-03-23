<script setup lang="ts">
defineProps<{
  tone?: 'primary' | 'success' | 'warning' | 'error';
}>();
</script>

<template>
  <span
    :class="[
      'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold',
      tone === 'success' && 'bg-success/20 text-success',
      tone === 'warning' && 'bg-warning/20 text-warning',
      tone === 'error' && 'bg-error/20 text-error',
      (!tone || tone === 'primary') && 'bg-primary/20 text-primary',
    ]"
  >
    <slot />
  </span>
</template>
