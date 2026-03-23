<script setup lang="ts">
import { onMounted, ref } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Card from '@/components/common/Card.vue';
import Badge from '@/components/common/Badge.vue';
import { useApi } from '@/composables/useApi';

interface User {
  id: number;
  username: string;
  email: string;
  role: 'ADMIN' | 'INTERN';
}

const api = useApi();
const users = ref<User[]>([]);

onMounted(async () => {
  const { data } = await api.get('/users');
  users.value = data.users;
});
</script>

<template>
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="space-y-6 p-6">
        <h2 class="text-xl font-semibold">User Management</h2>
        <Card>
          <div class="space-y-2">
            <div
              v-for="user in users"
              :key="user.id"
              class="flex items-center justify-between rounded-lg border border-dark-border bg-dark-bg px-3 py-2"
            >
              <div>
                <p class="text-sm font-semibold">{{ user.username }}</p>
                <p class="text-xs text-text-secondary">{{ user.email }}</p>
              </div>
              <Badge :tone="user.role === 'ADMIN' ? 'warning' : 'primary'">{{ user.role }}</Badge>
            </div>
          </div>
        </Card>
      </main>
    </div>
  </div>
</template>
