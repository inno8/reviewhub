<script setup lang="ts">
import Card from '@/components/common/Card.vue';
import Badge from '@/components/common/Badge.vue';
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { Finding } from '@/stores/findings';

const props = defineProps<{ finding: Finding }>();
const router = useRouter();

const difficultyTone = computed(() => {
  if (props.finding.difficulty === 'ADVANCED') return 'advanced';
  if (props.finding.difficulty === 'INTERMEDIATE') return 'intermediate';
  return 'beginner';
});

const categoryTone = computed(() => {
  if (props.finding.category === 'SECURITY') return 'security';
  if (props.finding.category === 'PERFORMANCE') return 'performance';
  if (props.finding.category === 'CODE_STYLE') return 'code-style';
  if (props.finding.category === 'TESTING') return 'testing';
  return 'muted';
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
  <Card class="cursor-pointer space-y-3 border border-border bg-bg-card p-5 transition hover:border-primary" @click="openFinding">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="font-mono text-sm text-text-primary">{{ finding.filePath }}</p>
        <p class="text-xs text-text-secondary">{{ finding.review?.branch || 'unknown-branch' }}</p>
      </div>
      <Badge tone="muted">{{ finding.review?.project?.displayName || 'Unknown Project' }}</Badge>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <Badge :tone="categoryTone as any">{{ finding.category.replace('_', ' ') }}</Badge>
      <Badge :tone="difficultyTone as any">{{ finding.difficulty }}</Badge>
    </div>
    <p class="line-clamp-2 text-sm text-text-secondary">{{ finding.explanation }}</p>
    <div class="flex items-center justify-between pt-1">
      <div class="flex items-center gap-2 text-xs text-text-secondary">
        <div class="flex h-7 w-7 items-center justify-center rounded-full bg-bg-elevated text-[11px] font-semibold text-white">
          {{ authorInitials }}
        </div>
        <span>{{ authorName }}</span>
      </div>
      <button class="text-sm font-medium text-primary transition hover:text-primary-hover">View Details</button>
    </div>
  </Card>
</template>
