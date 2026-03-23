<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import CalendarWidget from '@/components/calendar/CalendarWidget.vue';
import logo from '@/assets/logo.svg';
import { useProjectsStore } from '@/stores/projects';

const route = useRoute();
const auth = useAuthStore();
const projectsStore = useProjectsStore();
</script>

<template>
  <aside class="flex w-[280px] flex-col border-r border-border bg-bg-dark p-4">
    <div class="mb-5">
      <img :src="logo" alt="ReviewHub" class="h-8 w-auto" />
    </div>
    <div class="mb-5 rounded-lg border border-border bg-bg-card p-3">
      <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary">Activity</p>
      <CalendarWidget :project-id="projectsStore.selectedProjectId" compact />
    </div>
    <nav class="space-y-1">
      <RouterLink
        to="/"
        class="flex items-center rounded-md px-3 py-2 text-sm font-medium"
        :class="route.path === '/' ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'"
      >
        Dashboard
      </RouterLink>
      <RouterLink
        to="/performance"
        class="flex items-center rounded-md px-3 py-2 text-sm font-medium"
        :class="route.path.startsWith('/performance') ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'"
      >
        Insights
      </RouterLink>
      <RouterLink
        v-if="auth.user?.role === 'ADMIN'"
        to="/users"
        class="flex items-center rounded-md px-3 py-2 text-sm font-medium"
        :class="route.path.startsWith('/users') ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'"
      >
        Team Management
      </RouterLink>
    </nav>
    <div class="mt-auto space-y-1 pt-4">
      <a class="block rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary" href="#">
        Settings
      </a>
      <a class="block rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary" href="#">
        Support
      </a>
    </div>
  </aside>
</template>
