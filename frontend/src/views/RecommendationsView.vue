<script setup lang="ts">
import AppShell from '@/components/layout/AppShell.vue';
import RecommendationsWidget from '@/components/skills/RecommendationsWidget.vue';
import { useProjectsStore } from '@/stores/projects';

const projectsStore = useProjectsStore();
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1 max-w-4xl mx-auto w-full">
      <header class="mb-8">
        <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Learning Path</span>
        <h1 class="text-3xl font-black tracking-tight text-on-surface mt-2">Recommendations</h1>
        <p class="text-outline text-sm mt-2">
          Personalized learning recommendations based on your code patterns, skill gaps, and progress.
        </p>
      </header>

      <RecommendationsWidget
        :project-id="projectsStore.selectedProjectId != null ? String(projectsStore.selectedProjectId) : undefined"
      />
    </div>
  </AppShell>
</template>
