<template>
  <aside
    class="hidden xl:flex fixed top-24 right-6 w-[380px] max-h-[90vh] overflow-y-auto rounded-xl border border-outline-variant/10 bg-surface-container-low flex-col gap-3 p-3"
    data-testid="right-sidebar"
  >
    <!-- File tree (top) -->
    <FileTreeSidebar :files="files" inline />

    <!-- Divider -->
    <div class="h-px w-full bg-outline-variant/15 my-1" aria-hidden="true"></div>

    <!-- Rubric (bottom) -->
    <RubricPanel
      :criteria="criteria"
      :scores="scores"
      :editable="editable"
      :course-name="courseName"
      :cohort-name="cohortName"
      @update-score="(id, score) => $emit('update-score', id, score)"
    />
  </aside>
</template>

<script setup lang="ts">
import FileTreeSidebar from './FileTreeSidebar.vue';
import RubricPanel from './RubricPanel.vue';

interface FileEntry {
  path: string;
  isAdded?: boolean;
}

defineProps<{
  files: FileEntry[];
  criteria: any[];
  scores: Record<string, { score: number; evidence?: string }>;
  editable: boolean;
  courseName?: string | null;
  cohortName?: string | null;
}>();

defineEmits<{
  (e: 'update-score', criterionId: string, score: number): void;
}>();
</script>
