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
    <h3 class="text-lg font-semibold">Explanation</h3>
    <p class="whitespace-pre-line text-sm text-text-secondary">{{ explanation }}</p>

    <div>
      <h4 class="mb-2 text-sm font-semibold text-white">Learning References</h4>
      <ul class="space-y-1 text-sm">
        <li v-for="reference in references || []" :key="reference.url">
          <a :href="reference.url" target="_blank" rel="noreferrer" class="text-primary hover:underline">
            {{ reference.title }} ({{ reference.type }})
          </a>
        </li>
      </ul>
    </div>
  </Card>
</template>
