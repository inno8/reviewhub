<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Button from '@/components/common/Button.vue';
import CodeComparison from '@/components/findings/CodeComparison.vue';
import ExplanationSection from '@/components/findings/ExplanationSection.vue';
import { useFindingsStore } from '@/stores/findings';
import { useApi } from '@/composables/useApi';

const route = useRoute();
const findingsStore = useFindingsStore();
const api = useApi();

const findingId = computed(() => Number(route.params.id));
const finding = computed(() => findingsStore.selectedFinding);
const references = computed(() => {
  const raw = finding.value?.references;
  if (!raw) return [];
  return Array.isArray(raw) ? raw : [];
});

onMounted(async () => {
  if (!Number.isNaN(findingId.value)) {
    await findingsStore.fetchFinding(findingId.value);
  }
});

async function markUnderstood() {
  if (!findingId.value) return;
  await api.post(`/findings/${findingId.value}/understand`);
}

async function requestExplanation() {
  if (!findingId.value) return;
  await api.post(`/findings/${findingId.value}/request-explanation`);
}
</script>

<template>
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main v-if="finding" class="space-y-6 p-6">
        <section class="flex items-center justify-between">
          <div>
            <h2 class="text-xl font-semibold">{{ finding.filePath }}</h2>
            <p class="text-sm text-text-secondary">{{ finding.category }} - {{ finding.difficulty }}</p>
          </div>
          <div class="flex gap-3">
            <Button variant="secondary" @click="requestExplanation">Request Explanation</Button>
            <Button @click="markUnderstood">Mark Understood</Button>
          </div>
        </section>

        <CodeComparison :original-code="finding.originalCode" :optimized-code="finding.optimizedCode" />
        <ExplanationSection :explanation="finding.explanation" :references="references" />
      </main>
    </div>
  </div>
</template>
