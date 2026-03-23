<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import logoHorizontal from '@/assets/logo-horizontal.svg';

const route = useRoute();
const auth = useAuthStore();
</script>

<template>
  <aside class="w-64 border-r border-dark-border bg-dark-card p-4">
    <div class="mb-8">
      <img :src="logoHorizontal" alt="ReviewHub" class="h-8" />
    </div>
    <nav class="space-y-2">
      <RouterLink
        to="/"
        class="block rounded-lg px-3 py-2 text-sm"
        :class="route.path === '/' ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-dark-border'"
      >
        Dashboard
      </RouterLink>
      <RouterLink
        to="/performance"
        class="block rounded-lg px-3 py-2 text-sm"
        :class="route.path.startsWith('/performance') ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-dark-border'"
      >
        Performance
      </RouterLink>
      <RouterLink
        v-if="auth.user?.role === 'ADMIN'"
        to="/users"
        class="block rounded-lg px-3 py-2 text-sm"
        :class="route.path.startsWith('/users') ? 'bg-primary/20 text-primary' : 'text-text-secondary hover:bg-dark-border'"
      >
        User Management
      </RouterLink>
    </nav>
  </aside>
</template>
