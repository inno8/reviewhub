<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

function logout() {
  auth.logout();
  router.push('/login');
}

const navItems = [
  { name: 'Dashboard', path: '/' },
  { name: 'Projects', path: '/projects' },
];

function isActive(path: string) {
  return route.path === path;
}
</script>

<template>
  <header class="flex justify-between items-center w-full px-6 h-16 fixed top-0 z-50 bg-background">
    <div class="flex items-center gap-8">
      <!-- Logo -->
      <span class="text-xl font-bold bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent tracking-tight">
        ReviewHub
      </span>

      <!-- Nav Links -->
      <nav class="hidden md:flex gap-6">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'py-1 text-sm transition-colors',
            isActive(item.path)
              ? 'text-primary font-semibold border-b-2 border-primary'
              : 'text-surface-container-highest hover:text-primary'
          ]"
        >
          {{ item.name }}
        </router-link>
      </nav>
    </div>

    <div class="flex items-center gap-4">
      <!-- Notifications -->
      <button class="p-2 text-surface-container-highest hover:bg-surface-container transition-all duration-200 rounded-full active:scale-95">
        <span class="material-symbols-outlined">notifications</span>
      </button>

      <!-- Settings -->
      <button class="p-2 text-surface-container-highest hover:bg-surface-container transition-all duration-200 rounded-full active:scale-95">
        <span class="material-symbols-outlined">settings</span>
      </button>

      <!-- User Avatar -->
      <div class="relative group">
        <div class="h-8 w-8 rounded-full bg-surface-container-highest overflow-hidden border border-outline-variant/20 cursor-pointer">
          <div class="w-full h-full flex items-center justify-center text-primary text-sm font-bold">
            {{ auth.user?.username?.charAt(0).toUpperCase() || 'U' }}
          </div>
        </div>

        <!-- Dropdown -->
        <div class="absolute right-0 top-full mt-2 w-48 bg-surface-container-low rounded-lg border border-outline-variant/20 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
          <div class="px-4 py-3 border-b border-outline-variant/10">
            <p class="text-sm font-medium text-on-surface">{{ auth.user?.username }}</p>
            <p class="text-xs text-on-surface-variant">{{ auth.user?.email }}</p>
          </div>
          <button
            @click="logout"
            class="w-full px-4 py-2 text-left text-sm text-error hover:bg-error/10 transition-colors flex items-center gap-2"
          >
            <span class="material-symbols-outlined text-sm">logout</span>
            Sign out
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
