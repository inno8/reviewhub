<script setup lang="ts">
/**
 * StudentHomeView — /my-cohort
 *
 * Lightweight student landing that mounts the MyCohortWidget. Separate from
 * DashboardView (WIP in a parallel bucket) so this workstream can ship the
 * widget without touching shared files.
 *
 * Workstream E4 of Nakijken Copilot v1 Scope B1.
 */
import MyCohortWidget from '@/components/grading/MyCohortWidget.vue';
</script>

<template>
  <div class="student-home">
    <header class="page-header">
      <h1>My cohort</h1>
      <p class="muted">Who teaches you, what courses you're in, which rubrics grade your work.</p>
    </header>
    <div class="widget-wrap">
      <MyCohortWidget />
    </div>
  </div>
</template>

<style scoped>
.student-home {
  max-width: 720px;
  margin: 0 auto;
  padding: 1.5rem;
  color: rgb(226 232 240);
}
.page-header { margin-bottom: 1.2rem; }
.page-header h1 {
  font-size: 1.4rem;
  font-weight: 600;
  color: rgb(241 245 249);
  margin: 0;
}
.muted {
  color: rgb(148 163 184);
  font-size: 0.85rem;
  margin: 0.25rem 0 0 0;
}
</style>
