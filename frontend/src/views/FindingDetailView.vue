<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import DiffViewer from '@/components/code/DiffViewer.vue';
import FileViewer from '@/components/code/FileViewer.vue';
import { useFindingsStore } from '@/stores/findings';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const route = useRoute();
const findingsStore = useFindingsStore();
const auth = useAuthStore();
const toastMessage = ref('');
const actionLoading = ref(false);
const applyFixLoading = ref(false);
const errorMessage = ref('');
const showFileViewer = ref(false);

const findingId = computed(() => Number(route.params.id));
const finding = computed(() => findingsStore.selectedFinding);
const references = computed(() => {
  const raw = finding.value?.references;
  if (!raw) return [];
  return Array.isArray(raw) ? raw : [];
});

const hasRealCode = computed(() => {
  const code = finding.value?.originalCode;
  return code && code.trim() !== '' && !code.trim().startsWith('//');
});

const categoryClass = computed(() => {
  const cat = finding.value?.category?.toLowerCase().replace('_', '');
  return {
    security: 'bg-error/10 text-error border-error/20',
    performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    codestyle: 'bg-primary/10 text-primary border-primary/20',
    testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
  }[cat || ''] || 'bg-outline/10 text-outline border-outline/20';
});

const difficultyClass = computed(() => {
  const diff = finding.value?.difficulty?.toLowerCase();
  return {
    beginner: 'bg-secondary-container/10 text-secondary border-secondary-container/20',
    intermediate: 'bg-tertiary-container/10 text-tertiary-container border-tertiary-container/20',
    advanced: 'bg-error/10 text-error border-error/20',
  }[diff || ''] || 'bg-outline/10 text-outline border-outline/20';
});

onMounted(async () => {
  if (!Number.isNaN(findingId.value)) {
    await findingsStore.fetchFinding(findingId.value);
  }
});

async function markUnderstood() {
  if (!findingId.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.markUnderstood(findingId.value);
    if (finding.value) {
      finding.value.markedUnderstood = data.markedUnderstood;
    }
    toastMessage.value = 'Understanding state saved.';
  } finally {
    actionLoading.value = false;
  }
}

async function requestExplanation() {
  if (!findingId.value) return;
  actionLoading.value = true;
  try {
    await api.findings.requestExplanation(findingId.value);
    if (finding.value) {
      finding.value.explanationRequested = true;
    }
    toastMessage.value = 'Explanation requested successfully.';
  } finally {
    actionLoading.value = false;
  }
}

async function markFixed() {
  if (!findingId.value || !finding.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.markFixed(findingId.value);
    finding.value.fixedAt = data.fixedAt;
    toastMessage.value = data.fixedAt ? 'Marked as fixed.' : 'Unmarked as fixed.';
  } finally {
    actionLoading.value = false;
  }
}

async function applyFixAndCreatePr() {
  if (!findingId.value || !finding.value) return;
  applyFixLoading.value = true;
  errorMessage.value = '';
  try {
    const { data } = await api.findings.applyFix(findingId.value);
    finding.value.prCreated = true;
    finding.value.prUrl = data.prUrl;
    toastMessage.value = 'Pull request created successfully.';
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.error || 'Failed to create pull request.';
  } finally {
    applyFixLoading.value = false;
  }
}

function clearToast() {
  toastMessage.value = '';
}
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div v-if="finding" class="max-w-[90rem] mx-auto space-y-8">
        <!-- Header Section -->
        <section class="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div class="space-y-3">
            <div class="flex items-center gap-2 text-outline text-sm font-mono bg-surface-container-low px-3 py-1.5 rounded-lg w-fit">
              <span class="material-symbols-outlined text-sm">folder_open</span>
              <span>{{ finding.filePath }}</span>
              <span class="mx-1 text-outline-variant">/</span>
              <span class="material-symbols-outlined text-sm">account_tree</span>
              <span class="text-primary-fixed-dim">{{ finding.review?.branch || 'main' }}</span>
            </div>
            <h1 class="text-3xl font-bold tracking-tight text-on-surface">
              {{ finding.filePath.split('/').pop() }}
            </h1>
            <button
              v-if="finding.review?.project?.id"
              class="mt-2 flex items-center gap-1.5 text-sm text-primary font-medium hover:underline"
              @click="showFileViewer = true"
            >
              <span class="material-symbols-outlined text-sm">visibility</span>
              View full file
            </button>
          </div>
          <div class="flex flex-wrap gap-2">
            <span :class="['px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border', categoryClass]">
              <span class="material-symbols-outlined text-xs" style="font-variation-settings: 'FILL' 1;">security</span>
              {{ finding.category.replace('_', ' ') }}
            </span>
            <span :class="['px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border', difficultyClass]">
              <span class="material-symbols-outlined text-xs">speed</span>
              {{ finding.difficulty }}
            </span>
            <span class="px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20 text-xs font-bold">
              Finding ID: #{{ finding.id }}
            </span>
          </div>
        </section>

        <!-- Full File Diff View or Conceptual Issue -->
        <template v-if="hasRealCode">
          <DiffViewer :finding="finding" />
        </template>
        <template v-else>
          <section class="bg-surface-container rounded-xl p-8 text-center space-y-4 border border-outline-variant/10">
            <span class="material-symbols-outlined text-5xl text-outline/40">info</span>
            <p class="text-on-surface-variant text-lg">This is a conceptual issue — no code snippet available</p>
            <div v-if="finding.optimizedCode" class="bg-surface-container-low rounded-lg p-6 text-left max-w-2xl mx-auto">
              <h3 class="text-sm font-bold text-outline uppercase tracking-wider mb-2">Suggestion</h3>
              <p class="text-on-surface leading-relaxed">{{ finding.optimizedCode }}</p>
            </div>
            <button
              v-if="finding.review?.project?.id"
              class="mt-2 px-6 py-3 primary-gradient text-on-primary font-bold rounded-lg inline-flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-[0.98]"
              @click="showFileViewer = true"
            >
              <span class="material-symbols-outlined">visibility</span>
              View {{ finding.filePath }} on GitHub
            </button>
          </section>
        </template>

        <!-- Explanation Section -->
        <section class="bg-surface-container-low rounded-xl p-8 border border-outline-variant/10 relative overflow-hidden">
          <div class="absolute top-0 right-0 p-8 opacity-5">
            <span class="material-symbols-outlined text-9xl">lightbulb</span>
          </div>
          <div class="relative z-10 max-w-3xl">
            <h2 class="text-xl font-bold text-on-surface mb-4 flex items-center gap-2">
              <span class="material-symbols-outlined text-primary">auto_awesome</span>
              Why This Is Better
            </h2>
            <p class="text-on-surface-variant leading-relaxed mb-6">
              {{ finding.explanation }}
            </p>
            <div v-if="references.length > 0" class="space-y-2">
              <h3 class="text-sm font-bold text-outline uppercase tracking-wider">References</h3>
              <ul class="space-y-1">
                <li v-for="(ref, idx) in references" :key="idx">
                  <a :href="typeof ref === 'string' ? ref : ref.url" target="_blank" class="text-primary text-sm hover:underline flex items-center gap-1">
                    <span class="material-symbols-outlined text-sm">link</span>
                    {{ typeof ref === 'string' ? ref : ref.title || ref.url }}
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <!-- Actions Row -->
        <section class="flex flex-col md:flex-row items-center justify-between gap-6 pt-4 border-t border-outline-variant/10">
          <label class="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              :checked="!!finding.markedUnderstood"
              :disabled="actionLoading"
              class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary focus:ring-primary focus:ring-offset-background"
              @change="markUnderstood"
            />
            <span class="text-sm font-medium text-on-surface-variant group-hover:text-on-surface transition-colors">
              Mark as understood
            </span>
          </label>
          <div class="flex items-center gap-3 w-full md:w-auto">
            <button
              :disabled="actionLoading"
              :class="[
                'flex-1 md:flex-none px-6 py-3 rounded-lg flex items-center justify-center gap-2 font-medium transition-all active:scale-[0.98] disabled:opacity-50',
                finding.fixedAt
                  ? 'bg-primary/10 text-primary border border-primary/30'
                  : 'border border-outline-variant/30 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
              ]"
              @click="markFixed"
            >
              <span class="material-symbols-outlined" :style="finding.fixedAt ? 'font-variation-settings: \'FILL\' 1;' : ''">check_circle</span>
              {{ finding.fixedAt ? 'Fixed' : 'Mark as Fixed' }}
            </button>
            <button
              :disabled="actionLoading || finding.explanationRequested"
              class="flex-1 md:flex-none px-6 py-3 border border-outline-variant/30 rounded-lg flex items-center justify-center gap-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all active:scale-[0.98] disabled:opacity-50"
              @click="requestExplanation"
            >
              <span class="material-symbols-outlined">call</span>
              {{ finding.explanationRequested ? 'Requested' : 'Request Explanation' }}
            </button>
            <button
              v-if="auth.isAdmin"
              :disabled="applyFixLoading || !!finding.prCreated"
              class="flex-1 md:flex-none px-8 py-3 primary-gradient text-on-primary font-bold rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-[0.98] disabled:opacity-50"
              @click="applyFixAndCreatePr"
            >
              <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">rocket_launch</span>
              {{ finding.prCreated ? 'PR Created' : applyFixLoading ? 'Creating...' : 'Apply Fix & Create PR' }}
            </button>
          </div>
        </section>

        <!-- PR Link -->
        <p v-if="finding.prUrl" class="text-sm text-primary">
          Pull request:
          <a :href="finding.prUrl" target="_blank" rel="noopener noreferrer" class="underline hover:opacity-80">
            {{ finding.prUrl }}
          </a>
        </p>
        <p v-if="errorMessage" class="text-sm text-error">{{ errorMessage }}</p>

        <!-- File Viewer Modal -->
        <FileViewer
          v-if="showFileViewer && finding.review?.project?.id"
          :projectId="finding.review.project.id"
          :branch="finding.review?.branch || 'main'"
          :filePath="finding.filePath"
          :lineStart="finding.lineStart || 1"
          :lineEnd="finding.lineEnd || finding.lineStart || 1"
          :finding="finding"
          @close="showFileViewer = false"
        />
      </div>

      <!-- Loading State -->
      <div v-else class="flex items-center justify-center h-64">
        <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg cursor-pointer"
      @click="clearToast"
    >
      {{ toastMessage }}
    </div>
  </AppShell>
</template>
