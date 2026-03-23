<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Button from '@/components/common/Button.vue';
import Badge from '@/components/common/Badge.vue';
import CodeComparison from '@/components/findings/CodeComparison.vue';
import ExplanationSection from '@/components/findings/ExplanationSection.vue';
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
  <div class="app-shell flex">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main v-if="finding" class="space-y-6 p-6">
        <section class="surface-card flex flex-wrap items-start justify-between gap-4 p-5">
          <div>
            <p class="text-xs text-text-muted">
              {{ finding.review?.project?.displayName }} / {{ finding.filePath }} -> {{ finding.review?.branch }}
            </p>
            <h2 class="mt-1 text-xl font-semibold">{{ finding.filePath }}</h2>
            <div class="mt-3 flex flex-wrap items-center gap-2">
              <Badge
                :tone="finding.category === 'SECURITY' ? 'security' : finding.category === 'PERFORMANCE' ? 'performance' : finding.category === 'CODE_STYLE' ? 'code-style' : finding.category === 'TESTING' ? 'testing' : 'muted'"
              >
                {{ finding.category.replace('_', ' ') }}
              </Badge>
              <Badge
                :tone="finding.difficulty === 'ADVANCED' ? 'advanced' : finding.difficulty === 'INTERMEDIATE' ? 'intermediate' : 'beginner'"
              >
                {{ finding.difficulty }}
              </Badge>
              <Badge tone="muted">ID #{{ finding.id }}</Badge>
            </div>
          </div>
          <div class="flex gap-3">
            <Button variant="outlined" :disabled="actionLoading" @click="requestExplanation">
              {{ finding.explanationRequested ? 'Explanation Requested' : 'Request Explanation' }}
            </Button>
            <Button
              v-if="auth.isAdmin"
              :disabled="applyFixLoading || !!finding.prCreated"
              @click="applyFixAndCreatePr"
            >
              {{
                finding.prCreated
                  ? 'PR Created'
                  : applyFixLoading
                    ? 'Creating PR...'
                    : 'Apply Fix & Create PR'
              }}
            </Button>
          </div>
        </section>

        <p v-if="finding.prUrl" class="text-sm text-success">
          Pull request:
          <a :href="finding.prUrl" target="_blank" rel="noopener noreferrer" class="underline hover:opacity-80">
            {{ finding.prUrl }}
          </a>
        </p>
        <p v-if="errorMessage" class="text-sm text-error">{{ errorMessage }}</p>

        <label class="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            :checked="!!finding.markedUnderstood"
            :disabled="actionLoading"
            @change="markUnderstood"
          />
          Mark as understood
        </label>

        <CodeComparison
          :original-code="finding.originalCode"
          :optimized-code="finding.optimizedCode"
          :file-path="finding.filePath"
        />
        <ExplanationSection :explanation="finding.explanation" :references="references" />
        <div
          v-if="toastMessage"
          class="fixed bottom-4 right-4 rounded-lg border border-success/50 bg-success/20 px-4 py-2 text-sm text-success shadow-lg"
          @click="clearToast"
        >
          {{ toastMessage }}
        </div>
      </main>
    </div>
  </div>
</template>
