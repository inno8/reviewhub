<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { useFindingsStore, type Finding } from '@/stores/findings';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const route = useRoute();
const router = useRouter();
const findingsStore = useFindingsStore();
const auth = useAuthStore();

const findings = ref<Finding[]>([]);
const loading = ref(true);
const selectedFindingId = ref<number | null>(null);
const actionLoading = ref(false);
const toastMessage = ref('');

const filePath = computed(() => route.query.file as string);
const findingIds = computed(() => (route.query.ids as string)?.split(',').map(Number) || []);

onMounted(async () => {
  loading.value = true;
  try {
    // Fetch all findings for this file
    const fetchedFindings: Finding[] = [];
    for (const id of findingIds.value) {
      await findingsStore.fetchFinding(id);
      if (findingsStore.selectedFinding) {
        fetchedFindings.push({ ...findingsStore.selectedFinding });
      }
    }
    findings.value = fetchedFindings;
    if (findings.value.length > 0) {
      selectedFindingId.value = findings.value[0].id;
    }
  } finally {
    loading.value = false;
  }
});

const selectedFinding = computed(() => 
  findings.value.find(f => f.id === selectedFindingId.value) || null
);

const branch = computed(() => selectedFinding.value?.review?.branch || 'main');

// Parse code into lines with issue highlighting
const codeLines = computed(() => {
  if (!selectedFinding.value) return [];
  const original = selectedFinding.value.originalCode || '';
  const lines = original.split('\n');
  return lines.map((content, idx) => ({
    number: idx + 1,
    content,
    isHighlighted: true, // All lines in the snippet are highlighted
  }));
});

const optimizedLines = computed(() => {
  if (!selectedFinding.value) return [];
  const optimized = selectedFinding.value.optimizedCode || '';
  return optimized.split('\n').map((content, idx) => ({
    number: idx + 1,
    content,
    isHighlighted: true,
  }));
});

function getCategoryClass(category: string) {
  const cat = category?.toLowerCase().replace('_', '');
  return {
    security: 'bg-error/10 text-error border-error/20',
    performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    codestyle: 'bg-primary/10 text-primary border-primary/20',
    testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
    architecture: 'bg-secondary/10 text-secondary border-secondary/20',
  }[cat] || 'bg-outline/10 text-outline border-outline/20';
}

function getDifficultyClass(difficulty: string) {
  const diff = difficulty?.toLowerCase();
  return {
    beginner: 'bg-secondary-container/10 text-secondary border-secondary-container/20',
    intermediate: 'bg-tertiary-container/10 text-tertiary-container border-tertiary-container/20',
    advanced: 'bg-error/10 text-error border-error/20',
  }[diff] || 'bg-outline/10 text-outline border-outline/20';
}

async function markUnderstood() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.markUnderstood(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) {
      finding.markedUnderstood = data.markedUnderstood;
    }
    toastMessage.value = 'Understanding state saved.';
  } finally {
    actionLoading.value = false;
  }
}

async function requestExplanation() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    await api.findings.requestExplanation(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) {
      finding.explanationRequested = true;
    }
    toastMessage.value = 'Explanation requested via Telegram.';
  } finally {
    actionLoading.value = false;
  }
}

async function applyFix() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.applyFix(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) {
      finding.prCreated = true;
      finding.prUrl = data.prUrl;
    }
    toastMessage.value = 'Pull request created!';
  } catch (e: any) {
    toastMessage.value = e?.response?.data?.error || 'Failed to create PR';
  } finally {
    actionLoading.value = false;
  }
}

function goBack() {
  router.push('/');
}
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-7xl mx-auto">
        <!-- Header -->
        <div class="flex items-center gap-4 mb-6">
          <button
            @click="goBack"
            class="p-2 hover:bg-surface-container rounded-lg transition-colors"
          >
            <span class="material-symbols-outlined text-outline">arrow_back</span>
          </button>
          <div>
            <div class="flex items-center gap-2 text-outline text-sm font-mono">
              <span class="material-symbols-outlined text-sm">description</span>
              {{ filePath }}
            </div>
            <div class="flex items-center gap-2 mt-1">
              <span class="material-symbols-outlined text-xs text-outline">account_tree</span>
              <span class="text-xs text-primary-fixed-dim">{{ branch }}</span>
            </div>
          </div>
        </div>

        <!-- Finding Tabs -->
        <div class="flex gap-2 mb-6 overflow-x-auto pb-2">
          <button
            v-for="(finding, idx) in findings"
            :key="finding.id"
            :class="[
              'flex items-center gap-2 px-4 py-2 rounded-lg border transition-all whitespace-nowrap',
              selectedFindingId === finding.id
                ? 'bg-primary/10 border-primary/30 text-primary'
                : 'bg-surface-container border-outline-variant/20 text-on-surface-variant hover:border-primary/20'
            ]"
            @click="selectedFindingId = finding.id"
          >
            <span class="text-sm font-medium">Issue #{{ idx + 1 }}</span>
            <span :class="['px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border', getCategoryClass(finding.category)]">
              {{ finding.category.replace('_', ' ') }}
            </span>
          </button>
        </div>

        <!-- Main Content -->
        <div v-if="selectedFinding" class="space-y-6">
          <!-- Issue Header -->
          <div class="flex flex-wrap items-center gap-3">
            <span :class="['px-3 py-1 rounded-full text-xs font-bold border', getCategoryClass(selectedFinding.category)]">
              {{ selectedFinding.category.replace('_', ' ') }}
            </span>
            <span :class="['px-3 py-1 rounded-full text-xs font-bold border', getDifficultyClass(selectedFinding.difficulty)]">
              {{ selectedFinding.difficulty }}
            </span>
            <span class="text-xs text-outline">
              by <span class="text-on-surface font-medium">{{ selectedFinding.commitAuthor }}</span>
            </span>
          </div>

          <!-- Code Comparison -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <!-- Original Code -->
            <div class="bg-surface-container-low rounded-xl overflow-hidden border border-outline-variant/10">
              <div class="px-4 py-2 bg-surface-container-highest/50 flex items-center justify-between border-b border-outline-variant/10">
                <span class="text-xs font-bold uppercase tracking-widest text-outline">Original Code</span>
                <span class="text-[10px] text-error font-bold">NEEDS FIX</span>
              </div>
              <div class="p-4 font-mono text-sm overflow-x-auto max-h-[500px] overflow-y-auto">
                <div class="flex">
                  <div class="text-outline/40 text-right select-none pr-4 border-r border-outline-variant/20">
                    <div v-for="line in codeLines" :key="`orig-num-${line.number}`" class="leading-6">
                      {{ line.number }}
                    </div>
                  </div>
                  <div class="pl-4 flex-1">
                    <div
                      v-for="line in codeLines"
                      :key="`orig-line-${line.number}`"
                      :class="['leading-6 whitespace-pre', line.isHighlighted ? 'bg-error/10 -mx-4 px-4 border-l-2 border-error' : '']"
                    >{{ line.content || ' ' }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Optimized Code -->
            <div class="bg-surface-container rounded-xl overflow-hidden border border-primary/20 ring-1 ring-primary/10">
              <div class="px-4 py-2 bg-primary/10 flex items-center justify-between border-b border-primary/20">
                <span class="text-xs font-bold uppercase tracking-widest text-primary">Optimized Fix</span>
                <span class="text-[10px] bg-primary text-on-primary px-1.5 py-0.5 rounded font-bold">RECOMMENDED</span>
              </div>
              <div class="p-4 font-mono text-sm overflow-x-auto max-h-[500px] overflow-y-auto">
                <div class="flex">
                  <div class="text-outline/40 text-right select-none pr-4 border-r border-outline-variant/20">
                    <div v-for="line in optimizedLines" :key="`opt-num-${line.number}`" class="leading-6">
                      {{ line.number }}
                    </div>
                  </div>
                  <div class="pl-4 flex-1">
                    <div
                      v-for="line in optimizedLines"
                      :key="`opt-line-${line.number}`"
                      :class="['leading-6 whitespace-pre', line.isHighlighted ? 'bg-primary/10 -mx-4 px-4 border-l-2 border-primary' : '']"
                    >{{ line.content || ' ' }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Explanation -->
          <div class="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
            <h3 class="text-lg font-bold text-on-surface mb-3 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary">auto_awesome</span>
              Why This Is Better
            </h3>
            <p class="text-on-surface-variant leading-relaxed">
              {{ selectedFinding.explanation }}
            </p>
            
            <!-- References -->
            <div v-if="selectedFinding.references?.length" class="mt-4 pt-4 border-t border-outline-variant/10">
              <h4 class="text-xs font-bold uppercase tracking-wider text-outline mb-2">References</h4>
              <div class="flex flex-wrap gap-2">
                <a
                  v-for="(ref, idx) in selectedFinding.references"
                  :key="idx"
                  :href="ref.url"
                  target="_blank"
                  class="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  <span class="material-symbols-outlined text-sm">link</span>
                  {{ ref.title }}
                </a>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex flex-col md:flex-row items-center justify-between gap-4 pt-4 border-t border-outline-variant/10">
            <label class="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                :checked="!!selectedFinding.markedUnderstood"
                :disabled="actionLoading"
                class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary focus:ring-primary"
                @change="markUnderstood"
              />
              <span class="text-sm font-medium text-on-surface-variant group-hover:text-on-surface">
                Mark as understood
              </span>
            </label>
            
            <div class="flex items-center gap-3">
              <button
                :disabled="actionLoading || selectedFinding.explanationRequested"
                class="px-6 py-3 border border-outline-variant/30 rounded-lg flex items-center gap-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all disabled:opacity-50"
                @click="requestExplanation"
              >
                <span class="material-symbols-outlined">call</span>
                {{ selectedFinding.explanationRequested ? 'Requested' : 'Request Explanation' }}
              </button>
              
              <button
                v-if="auth.isAdmin"
                :disabled="actionLoading || selectedFinding.prCreated"
                class="px-6 py-3 primary-gradient text-on-primary font-bold rounded-lg flex items-center gap-2 shadow-lg shadow-primary/10 transition-all disabled:opacity-50"
                @click="applyFix"
              >
                <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">rocket_launch</span>
                {{ selectedFinding.prCreated ? 'PR Created' : 'Apply Fix & Create PR' }}
              </button>
            </div>
          </div>

          <!-- PR Link -->
          <div v-if="selectedFinding.prUrl" class="p-4 bg-primary/10 rounded-lg border border-primary/20">
            <p class="text-sm text-primary">
              <span class="font-bold">Pull Request Created:</span>
              <a :href="selectedFinding.prUrl" target="_blank" class="ml-2 underline hover:opacity-80">
                {{ selectedFinding.prUrl }}
              </a>
            </p>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="flex items-center justify-center py-20">
          <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg cursor-pointer"
      @click="toastMessage = ''"
    >
      {{ toastMessage }}
    </div>
  </AppShell>
</template>
