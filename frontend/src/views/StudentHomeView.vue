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
import AppShell from '@/components/layout/AppShell.vue';
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-3xl mx-auto">
        <header class="mb-8">
          <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">My cohort</h1>
          <p class="text-on-surface-variant mt-2 max-w-xl">
            Who teaches you, what courses you're in, which rubrics grade your work.
          </p>
        </header>
        <MyCohortWidget />
      </div>
    </div>
  </AppShell>
</template>
