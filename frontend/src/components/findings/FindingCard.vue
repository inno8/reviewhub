<script setup lang="ts">
import Card from '@/components/common/Card.vue';
import Badge from '@/components/common/Badge.vue';
import { computed } from 'vue';
import type { Finding } from '@/stores/findings';

const props = defineProps<{ finding: Finding }>();
const difficultyTone = computed(() => {
  if (props.finding.difficulty === 'ADVANCED') return 'error';
  if (props.finding.difficulty === 'INTERMEDIATE') return 'warning';
  return 'success';
});
</script>

<template>
  <Card class="space-y-3">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="font-semibold text-white">{{ finding.filePath }}</p>
        <p class="text-xs text-text-secondary">{{ finding.review?.project?.displayName || 'Unknown Project' }}</p>
      </div>
      <Badge>{{ finding.category }}</Badge>
    </div>
    <p class="text-sm text-text-secondary">{{ finding.explanation }}</p>
    <div class="flex justify-between">
      <Badge :tone="difficultyTone as any">{{ finding.difficulty }}</Badge>
      <RouterLink :to="`/findings/${finding.id}`" class="text-sm font-semibold text-primary hover:underline">
        View details
      </RouterLink>
    </div>
  </Card>
</template>
