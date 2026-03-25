<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import type { Finding } from '@/stores/findings';
import FileViewer from '@/components/code/FileViewer.vue';

const props = defineProps<{ finding: Finding }>();
const router = useRouter();
const showFileViewer = ref(false);

const categoryClass = computed(() => {
  const cat = props.finding.category.toLowerCase().replace('_', '');
  return {
    security: 'bg-error/10 text-error border-error/20',
    performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    codestyle: 'bg-primary/10 text-primary border-primary/20',
    testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
    architecture: 'bg-secondary/10 text-secondary border-secondary/20',
  }[cat] || 'bg-outline/10 text-outline border-outline/20';
});

const difficultyClass = computed(() => {
  const diff = props.finding.difficulty.toLowerCase();
  return {
    beginner: 'bg-secondary-container/10 text-secondary border-secondary-container/20',
    intermediate: 'bg-tertiary-container/10 text-tertiary-container border-tertiary-container/20',
    advanced: 'bg-error/10 text-error border-error/20',
  }[diff] || 'bg-outline/10 text-outline border-outline/20';
});

const authorName = computed(() => props.finding.commitAuthor || 'Unknown');

const fileIcon = computed(() => {
  const ext = props.finding.filePath.split('.').pop()?.toLowerCase();
  if (['ts', 'tsx', 'js', 'jsx'].includes(ext || '')) return 'code';
  if (['go', 'rs', 'py'].includes(ext || '')) return 'description';
  if (['test', 'spec'].some(s => props.finding.filePath.includes(s))) return 'biotech';
  return 'folder_open';
});

async function openFinding() {
  await router.push(`/findings/${props.finding.id}`);
}
</script>

<template>
  <div
    class="bg-surface-container-low p-6 rounded-xl border border-outline-variant/5 hover:border-primary/20 transition-all duration-300 cursor-pointer group relative"
    @click="openFinding"
  >
    <!-- File Path & Branch -->
    <div class="flex justify-between items-start mb-4">
      <div class="flex items-center gap-2 text-outline text-xs font-mono">
        <span class="material-symbols-outlined text-sm">{{ fileIcon }}</span>
        {{ finding.filePath }}
      </div>
      <span class="bg-surface-container-highest text-outline text-[10px] px-2 py-0.5 rounded font-medium">
        {{ finding.review?.branch || 'main' }}
      </span>
    </div>

    <!-- Category & Difficulty Badges -->
    <div class="flex gap-2 mb-4">
      <span :class="['px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border', categoryClass]">
        {{ finding.category.replace('_', ' ') }}
      </span>
      <span :class="['px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border', difficultyClass]">
        {{ finding.difficulty }}
      </span>
    </div>

    <!-- Explanation -->
    <p class="text-on-surface text-sm mb-6 line-clamp-2 font-medium">
      {{ finding.explanation }}
    </p>

    <!-- Footer: Author & Action -->
    <div class="flex items-center justify-between mt-auto">
      <div class="flex items-center gap-2">
        <div class="w-6 h-6 rounded-full bg-surface-container-highest flex items-center justify-center text-[10px] font-bold text-primary">
          {{ authorName.charAt(0).toUpperCase() }}
        </div>
        <span class="text-xs text-outline font-medium">{{ authorName }}</span>
      </div>
      <div class="flex items-center gap-3">
        <button
          v-if="finding.review?.project?.id"
          class="text-outline text-xs font-medium flex items-center gap-1 hover:text-primary transition-colors"
          @click.stop="showFileViewer = true"
        >
          <span class="material-symbols-outlined text-sm">visibility</span>
          View File
        </button>
        <button class="text-primary text-xs font-bold flex items-center gap-1 hover:underline">
          View Details
          <span class="material-symbols-outlined text-sm">arrow_forward</span>
        </button>
      </div>
    </div>

    <!-- File Viewer Modal -->
    <FileViewer
      v-if="showFileViewer && finding.review?.project?.id"
      :projectId="finding.review.project.id"
      :branch="finding.review?.branch || 'main'"
      :filePath="finding.filePath"
      :lineStart="finding.lineStart || 1"
      :lineEnd="finding.lineEnd || finding.lineStart || 1"
      :finding="finding"
      @close="showFileViewer = false"
    />
  </div>
</template>
