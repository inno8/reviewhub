<script setup lang="ts">
defineProps<{
  tone?:
    | 'primary'
    | 'success'
    | 'warning'
    | 'error'
    | 'muted'
    | 'security'
    | 'performance'
    | 'code-style'
    | 'testing'
    | 'beginner'
    | 'intermediate'
    | 'advanced';
}>();
</script>

<template>
  <span
    :class="[
      'inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
      tone === 'muted' && 'bg-bg-elevated text-text-secondary',
      tone === 'success' && 'bg-success/20 text-success',
      tone === 'warning' && 'bg-warning/20 text-warning',
      tone === 'error' && 'bg-error/20 text-error',
      tone === 'security' && 'status-pill-security',
      tone === 'performance' && 'status-pill-performance',
      tone === 'code-style' && 'status-pill-code-style',
      tone === 'testing' && 'status-pill-testing',
      tone === 'beginner' && 'status-pill-beginner',
      tone === 'intermediate' && 'status-pill-intermediate',
      tone === 'advanced' && 'status-pill-advanced',
      (!tone || tone === 'primary') && 'bg-primary/20 text-primary',
    ]"
  >
    <slot />
  </span>
</template>
