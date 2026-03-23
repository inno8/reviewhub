<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import CalendarWidget from '@/components/calendar/CalendarWidget.vue';

const route = useRoute();
const auth = useAuthStore();

const navItems = [
  { name: 'Dashboard', icon: 'dashboard', path: '/' },
  { name: 'Insights', icon: 'analytics', path: '/insights' },
  { name: 'Team Management', icon: 'group', path: '/team', adminOnly: true },
];

function isActive(path: string) {
  return route.path === path;
}
</script>

<template>
  <aside class="fixed left-0 top-16 h-[calc(100vh-64px)] w-64 flex flex-col py-4 bg-surface-container-low z-40">
    <!-- New Review Button -->
    <div class="px-4 mb-6">
      <button class="w-full primary-gradient text-on-primary font-bold py-3 px-4 rounded-lg flex items-center justify-center gap-2 active:scale-95 transition-transform">
        <span class="material-symbols-outlined text-xl">add</span>
        <span class="text-sm">New Review</span>
      </button>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        v-show="!item.adminOnly || auth.isAdmin"
        :class="[
          'rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium',
          isActive(item.path)
            ? 'bg-surface-container text-primary'
            : 'text-surface-container-highest hover:bg-surface-container/50'
        ]"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.name }}</span>
      </router-link>

      <!-- Calendar Widget -->
      <div class="mt-8 px-4">
        <h3 class="text-[10px] uppercase tracking-widest text-outline mb-4 font-bold">
          Activity — March 2026
        </h3>
        <CalendarWidget />
      </div>
    </nav>

    <!-- Bottom Section -->
    <div class="mt-auto border-t border-outline-variant/10 pt-4">
      <router-link
        to="/settings"
        :class="[
          'rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium',
          isActive('/settings')
            ? 'bg-surface-container text-primary'
            : 'text-surface-container-highest hover:bg-surface-container/50'
        ]"
      >
        <span class="material-symbols-outlined">settings</span>
        <span>Settings</span>
      </router-link>
      <a
        href="#"
        class="text-surface-container-highest hover:bg-surface-container/50 rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium"
      >
        <span class="material-symbols-outlined">help</span>
        <span>Support</span>
      </a>
    </div>
  </aside>
</template>
