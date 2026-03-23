<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import Button from '@/components/common/Button.vue';
import Dropdown from '@/components/common/Dropdown.vue';
import logo from '@/assets/logo-horizontal.svg';
import { useAuthStore } from '@/stores/auth';
import { useProjectsStore } from '@/stores/projects';

const auth = useAuthStore();
const projectsStore = useProjectsStore();
const router = useRouter();
const canShowProjectPicker = computed(() => router.currentRoute.value.path !== '/login');

async function onLogout() {
  await auth.logout();
  await router.push('/login');
}
</script>

<template>
  <header class="flex items-center justify-between border-b border-border bg-bg-dark px-6 py-4">
    <div class="flex items-center gap-4">
      <img :src="logo" alt="ReviewHub" class="h-8 w-auto" />
      <p class="rounded bg-primary/15 px-2 py-1 text-xs font-semibold text-primary">Dashboard</p>
    </div>

    <div v-if="canShowProjectPicker" class="w-full max-w-sm px-6">
      <Dropdown
        :model-value="projectsStore.selectedProjectId"
        @update:model-value="projectsStore.setSelectedProject($event ? Number($event) : null)"
      >
        <option disabled value="">Select project</option>
        <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
          {{ project.displayName }}
        </option>
      </Dropdown>
    </div>

    <div class="flex items-center gap-3">
      <div class="flex h-9 w-9 items-center justify-center rounded-full bg-bg-elevated text-sm font-semibold">
        {{ auth.user?.username?.slice(0, 1)?.toUpperCase() }}
      </div>
      <div class="text-right text-sm">
        <p class="font-semibold">{{ auth.user?.username }}</p>
        <p class="text-xs text-text-secondary">{{ auth.user?.role }}</p>
      </div>
      <Button variant="outlined" @click="onLogout">Logout</Button>
    </div>
  </header>
</template>
