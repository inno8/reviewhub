<script setup lang="ts">
import { onMounted } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import CalendarWidget from '@/components/calendar/CalendarWidget.vue';
import FindingCard from '@/components/findings/FindingCard.vue';
import { useFindingsStore } from '@/stores/findings';
import { useProjectsStore } from '@/stores/projects';

const findingsStore = useFindingsStore();
const projectsStore = useProjectsStore();

onMounted(async () => {
  await Promise.all([projectsStore.fetchProjects(), findingsStore.fetchFindings()]);
});
</script>

<template>
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="grid flex-1 gap-6 p-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section class="space-y-4">
          <h2 class="text-lg font-semibold">Latest Findings</h2>
          <div class="grid gap-4">
            <FindingCard v-for="finding in findingsStore.findings" :key="finding.id" :finding="finding" />
          </div>
        </section>
        <section class="space-y-4">
          <CalendarWidget />
        </section>
      </main>
    </div>
  </div>
</template>
