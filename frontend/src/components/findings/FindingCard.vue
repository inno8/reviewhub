<script setup lang="ts">
import Card from '@/components/common/Card.vue';
import Badge from '@/components/common/Badge.vue';
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { Finding } from '@/stores/findings';

const props = defineProps<{ finding: Finding }>();
const router = useRouter();

const difficultyTone = computed(() => {
  if (props.finding.difficulty === 'ADVANCED') return 'error';
  if (props.finding.difficulty === 'INTERMEDIATE') return 'warning';
  return 'success';
});

const authorName = computed(() => props.finding.commitAuthor || 'Unknown');
const authorInitials = computed(() => {
  const parts = authorName.value.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
});

async function openFinding() {
  await router.push(`/findings/${props.finding.id}`);
}
</script>

<template>
  <Card class="space-y-3 cursor-pointer" @click="openFinding">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="font-semibold text-white">{{ finding.filePath }}</p>
        <p class="text-xs text-text-secondary">{{ finding.review?.project?.displayName || 'Unknown Project' }}</p>
      </div>
      <Badge>{{ finding.category }}</Badge>
    </div>
    <p class="text-sm text-text-secondary">{{ finding.explanation }}</p>
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2 text-xs text-text-secondary">
        <div class="flex h-6 w-6 items-center justify-center rounded-full bg-dark-border font-semibold text-white">
          {{ authorInitials }}
        </div>
        <span>{{ authorName }}</span>
      </div>
      <Badge :tone="difficultyTone as any">{{ finding.difficulty }}</Badge>
    </div>
  </Card>
</template>
