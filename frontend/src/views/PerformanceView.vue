<script setup lang="ts">
import { onMounted, ref } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Card from '@/components/common/Card.vue';
import TrendChart from '@/components/charts/TrendChart.vue';
import { useApi } from '@/composables/useApi';

const api = useApi();
interface Metric {
  id: number;
  periodType: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  findingCount: number;
  commitCount: number;
}
const metrics = ref<Metric[]>([]);

onMounted(async () => {
  const { data } = await api.get('/performance');
  metrics.value = data.metrics;
});
</script>

<template>
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="space-y-6 p-6">
        <h2 class="text-xl font-semibold">Performance Insights</h2>
        <TrendChart title="Findings Trend" />
        <Card>
          <h3 class="mb-3 text-lg font-semibold">Latest Metrics</h3>
          <div class="space-y-2">
            <div
              v-for="metric in metrics"
              :key="metric.id"
              class="rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-sm"
            >
              {{ metric.periodType }} | Findings: {{ metric.findingCount }} | Commits: {{ metric.commitCount }}
            </div>
          </div>
        </Card>
      </main>
    </div>
  </div>
</template>
