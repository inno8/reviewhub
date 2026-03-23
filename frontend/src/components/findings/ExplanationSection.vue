<script setup lang="ts">
import Card from '@/components/common/Card.vue';

interface ReferenceLink {
  type: 'docs' | 'article' | 'tutorial';
  title: string;
  url: string;
}

defineProps<{ explanation: string; references?: ReferenceLink[] | null }>();
</script>

<template>
  <Card class="space-y-3">
    <h3 class="text-lg font-semibold">Why This Is Better</h3>
    <p class="whitespace-pre-line text-sm leading-6 text-text-secondary">{{ explanation }}</p>

    <div>
      <h4 class="mb-2 text-sm font-semibold text-white">Reference Links</h4>
      <ul class="space-y-1.5 text-sm">
        <li v-for="reference in references || []" :key="reference.url">
          <a :href="reference.url" target="_blank" rel="noreferrer" class="inline-flex items-center gap-2 text-primary transition hover:text-primary-hover">
            <span class="text-success">✓</span>
            <span>{{ reference.title }} ({{ reference.type }})</span>
          </a>
        </li>
      </ul>
    </div>
  </Card>
</template>
