<script setup lang="ts">
defineProps<{
  modelValue: string;
  type?: 'text' | 'email' | 'password';
  placeholder?: string;
  icon?: string;
  id?: string;
  required?: boolean;
  disabled?: boolean;
}>();

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>();
</script>

<template>
  <div class="relative">
    <span v-if="icon" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
      {{ icon }}
    </span>
    <input
      :id="id"
      :value="modelValue"
      :type="type || 'text'"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :class="[
        'h-11 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm text-text-primary outline-none transition placeholder:text-text-muted focus:border-primary focus:ring-1 focus:ring-primary',
        icon ? 'pl-10' : '',
      ]"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </div>
</template>
