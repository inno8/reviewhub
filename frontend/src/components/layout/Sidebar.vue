<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import CalendarWidget from '@/components/calendar/CalendarWidget.vue';
import { useProjectsStore } from '@/stores/projects';

const route = useRoute();
const auth = useAuthStore();
const projectsStore = useProjectsStore();
</script>

<template>
  <aside class="flex w-[280px] flex-col border-r border-border bg-bg-dark">
    <!-- Logo & New Review Button -->
    <div class="p-4">
      <div class="mb-4 flex items-center gap-3">
        <div class="flex h-8 w-8 items-center justify-center rounded bg-primary/20">
          <span class="text-primary font-bold text-sm">&lt;/&gt;</span>
        </div>
        <span class="text-lg font-semibold text-white">ReviewHub</span>
        <span class="ml-auto rounded bg-bg-elevated px-2 py-0.5 text-xs text-text-secondary">Dashboard</span>
      </div>
      
      <!-- New Review Button -->
      <button class="flex w-full items-center justify-center gap-2 rounded-md border border-primary bg-transparent px-4 py-2 text-sm font-medium text-primary transition hover:bg-primary/10">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        New Review
      </button>
    </div>

    <!-- Navigation -->
    <nav class="space-y-1 px-4">
      <RouterLink
        to="/"
        class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium"
        :class="route.path === '/' ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
        Dashboard
      </RouterLink>
      <RouterLink
        to="/performance"
        class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium"
        :class="route.path.startsWith('/performance') ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        Insights
      </RouterLink>
      <RouterLink
        v-if="auth.user?.role === 'ADMIN'"
        to="/users"
        class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium"
        :class="route.path.startsWith('/users') ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
        Team Management
      </RouterLink>
    </nav>

    <!-- Activity Calendar (moved to bottom) -->
    <div class="mt-auto px-4 pb-4">
      <div class="mb-4 rounded-lg border border-border bg-bg-card p-3">
        <p class="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">Activity — March 2026</p>
        <CalendarWidget :project-id="projectsStore.selectedProjectId" compact />
      </div>
      
      <!-- Settings & Support -->
      <div class="space-y-1">
        <a class="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary" href="#">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Settings
        </a>
        <a class="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-text-secondary hover:bg-bg-elevated hover:text-text-primary" href="#">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Support
        </a>
      </div>
    </div>
  </aside>
</template>
