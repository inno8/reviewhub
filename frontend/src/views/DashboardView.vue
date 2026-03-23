<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import FindingCard from '@/components/findings/FindingCard.vue';
import { useFindingsStore } from '@/stores/findings';

const findingsStore = useFindingsStore();

const selectedCategory = ref('all');
const selectedDifficulty = ref('all');
const selectedAuthor = ref('all');

const categories = ['All', 'Security', 'Performance', 'CodeStyle', 'Testing', 'Architecture'];
const difficulties = ['All', 'Beginner', 'Intermediate', 'Advanced'];

onMounted(() => {
  findingsStore.fetchFindings();
});

const filteredFindings = computed(() => {
  return findingsStore.findings.filter((finding) => {
    if (selectedCategory.value !== 'all' && finding.category !== selectedCategory.value) return false;
    if (selectedDifficulty.value !== 'all' && finding.difficulty !== selectedDifficulty.value) return false;
    return true;
  });
});

const currentDate = computed(() => {
  const now = new Date();
  return now.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
});
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <!-- Content Header -->
      <header class="mb-10">
        <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">
          {{ currentDate }}
        </h1>
        <p class="text-outline text-sm">
          Welcome back. You have 
          <span class="text-primary font-semibold">{{ filteredFindings.length }} pending reviews</span>
          across 3 active projects.
        </p>
      </header>

      <!-- Filter Bar -->
      <div class="flex flex-wrap items-center gap-4 mb-8 bg-surface-container-low p-3 rounded-xl border border-outline-variant/10">
        <!-- Category Filter -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">filter_list</span>
          <select
            v-model="selectedCategory"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Category: All</option>
            <option v-for="cat in categories.slice(1)" :key="cat" :value="cat">
              {{ cat }}
            </option>
          </select>
        </div>

        <!-- Difficulty Filter -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">signal_cellular_alt</span>
          <select
            v-model="selectedDifficulty"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Difficulty: All</option>
            <option v-for="diff in difficulties.slice(1)" :key="diff" :value="diff">
              {{ diff }}
            </option>
          </select>
        </div>

        <!-- Author Filter -->
        <div class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-lg border border-outline-variant/20">
          <span class="material-symbols-outlined text-sm text-outline">person</span>
          <select
            v-model="selectedAuthor"
            class="bg-transparent border-none text-xs text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Author: All</option>
          </select>
        </div>

        <!-- Results Count -->
        <div class="ml-auto">
          <span class="text-[10px] text-outline uppercase font-bold tracking-tighter">
            Showing {{ filteredFindings.length }} findings
          </span>
        </div>
      </div>

      <!-- Finding Cards Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        <FindingCard
          v-for="finding in filteredFindings"
          :key="finding.id"
          :finding="finding"
        />

        <!-- Empty State -->
        <div
          v-if="filteredFindings.length === 0"
          class="col-span-full flex flex-col items-center justify-center py-16"
        >
          <span class="material-symbols-outlined text-6xl text-outline mb-4">inbox</span>
          <p class="text-on-surface-variant text-lg">No findings match your filters</p>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <footer class="flex justify-between items-center w-full px-8 py-4 mt-auto bg-background border-t border-outline-variant/15">
      <span class="text-xs uppercase tracking-widest text-outline">© 2024 ReviewHub</span>
      <div class="flex gap-6">
        <a href="#" class="text-xs uppercase tracking-widest text-outline hover:text-primary transition-opacity">Documentation</a>
        <a href="#" class="text-xs uppercase tracking-widest text-outline hover:text-primary transition-opacity">System Status</a>
        <a href="#" class="text-xs uppercase tracking-widest text-outline hover:text-primary transition-opacity">Privacy</a>
      </div>
    </footer>
  </AppShell>
</template>
