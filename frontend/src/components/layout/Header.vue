<script setup lang="ts">
import { useRouter } from 'vue-router';
import Button from '@/components/common/Button.vue';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const router = useRouter();

async function onLogout() {
  await auth.logout();
  await router.push('/login');
}
</script>

<template>
  <header class="flex items-center justify-between border-b border-dark-border bg-dark-bg px-6 py-4">
    <div>
      <h1 class="text-xl font-semibold">ReviewHub</h1>
      <p class="text-sm text-text-secondary">Code review learning dashboard</p>
    </div>
    <div class="flex items-center gap-4">
      <div class="text-right text-sm">
        <p class="font-semibold">{{ auth.user?.username }}</p>
        <p class="text-text-secondary">{{ auth.user?.role }}</p>
      </div>
      <Button variant="secondary" @click="onLogout">Logout</Button>
    </div>
  </header>
</template>
