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
const fileContent = ref<string>('');
const loading = ref(true);
const selectedFindingId = ref<number | null>(null);
const actionLoading = ref(false);
const toastMessage = ref('');

const filePath = computed(() => route.query.file as string);
const findingIds = computed(() => (route.query.ids as string)?.split(',').map(Number) || []);

onMounted(async () => {
  loading.value = true;
  try {
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
      // Try to fetch full file content from GitHub
      try {
        const { data } = await api.findings.getFileContent(findings.value[0].id);
        fileContent.value = data.content;
      } catch {
        // Use original code as fallback - combine all snippets
        fileContent.value = findings.value.map(f => f.originalCode).join('\n\n// --- Next Issue ---\n\n');
      }
    }
  } finally {
    loading.value = false;
  }
});

const selectedFinding = computed(() => 
  findings.value.find(f => f.id === selectedFindingId.value) || null
);

const branch = computed(() => selectedFinding.value?.review?.branch || 'main');

// Parse original file into lines with issue annotations
const originalLines = computed(() => {
  const content = fileContent.value || selectedFinding.value?.originalCode || '';
  const lines = content.split('\n');
  
  // Find which lines belong to each finding's snippet
  const issueRanges: Map<number, number> = new Map(); // lineIndex -> findingId
  
  findings.value.forEach(finding => {
    const snippetLines = finding.originalCode.split('\n');
    const fileLines = content.split('\n');
    
    for (let i = 0; i <= fileLines.length - snippetLines.length; i++) {
      let match = true;
      for (let j = 0; j < snippetLines.length; j++) {
        if (fileLines[i + j]?.trim() !== snippetLines[j]?.trim()) {
          match = false;
          break;
        }
      }
      if (match) {
        for (let j = 0; j < snippetLines.length; j++) {
          issueRanges.set(i + j, finding.id);
        }
        break;
      }
    }
  });
  
  return lines.map((content, idx) => ({
    number: idx + 1,
    content,
    findingId: issueRanges.get(idx) || null,
    isSelected: issueRanges.get(idx) === selectedFindingId.value,
  }));
});

// Optimized code lines (for the selected finding)
const optimizedLines = computed(() => {
  if (!selectedFinding.value) return [];
  return selectedFinding.value.optimizedCode.split('\n').map((content, idx) => ({
    number: idx + 1,
    content,
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

function scrollToIssue(findingId: number) {
  selectedFindingId.value = findingId;
  // Find first line of this issue
  const lineIdx = originalLines.value.findIndex(l => l.findingId === findingId);
  if (lineIdx >= 0) {
    const element = document.getElementById(`line-${lineIdx + 1}`);
    element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

async function markUnderstood() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.markUnderstood(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) finding.markedUnderstood = data.markedUnderstood;
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
    if (finding) finding.explanationRequested = true;
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
    <div class="p-4 flex-1 flex flex-col h-[calc(100vh-64px)]">
      <div class="w-full flex flex-col h-full">
        <!-- Header -->
        <div class="flex items-center justify-between mb-4 flex-shrink-0">
          <div class="flex items-center gap-4">
            <button
              @click="goBack"
              class="p-2 hover:bg-surface-container rounded-lg transition-colors"
            >
              <span class="material-symbols-outlined text-outline">arrow_back</span>
            </button>
            <div>
              <div class="flex items-center gap-2 text-on-surface font-mono text-sm">
                <span class="material-symbols-outlined text-sm text-outline">description</span>
                {{ filePath }}
              </div>
              <div class="flex items-center gap-2 mt-1">
                <span class="material-symbols-outlined text-xs text-outline">account_tree</span>
                <span class="text-xs text-primary-fixed-dim">{{ branch }}</span>
                <span class="text-xs text-outline mx-2">•</span>
                <span class="text-xs text-outline">{{ findings.length }} issues found</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Main Content Area -->
        <div class="flex gap-4 flex-1 min-h-0">
          <!-- Issue Navigator Sidebar -->
          <div class="w-64 flex-shrink-0 bg-surface-container-low rounded-xl border border-outline-variant/10 flex flex-col">
            <div class="p-3 border-b border-outline-variant/10">
              <h3 class="text-sm font-bold text-on-surface">Issues in this file</h3>
            </div>
            <div class="flex-1 overflow-y-auto p-2">
              <button
                v-for="(finding, idx) in findings"
                :key="finding.id"
                :class="[
                  'w-full text-left p-3 rounded-lg mb-2 transition-all',
                  selectedFindingId === finding.id
                    ? 'bg-primary/10 border border-primary/30'
                    : 'bg-surface-container border border-transparent hover:border-outline-variant/30'
                ]"
                @click="scrollToIssue(finding.id)"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs font-bold text-outline">#{{ idx + 1 }}</span>
                  <span :class="['px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border', getCategoryClass(finding.category)]">
                    {{ finding.category.replace('_', ' ') }}
                  </span>
                </div>
                <p class="text-xs text-on-surface-variant line-clamp-2">
                  {{ finding.explanation.slice(0, 80) }}...
                </p>
                <div class="flex items-center gap-2 mt-2 text-[10px] text-outline">
                  <span v-if="finding.markedUnderstood" class="text-primary">✓ Understood</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Code Panels + Explanation -->
          <div class="flex-1 flex flex-col min-w-0 gap-4">
            <!-- Code Comparison Row -->
            <div class="flex gap-4 flex-1 min-h-0">
              <!-- Original Code (Full File) -->
              <div class="flex-1 bg-surface-container-lowest rounded-xl border border-outline-variant/10 flex flex-col min-w-0 overflow-hidden">
                <div class="px-4 py-2 bg-surface-container border-b border-outline-variant/10 flex items-center justify-between flex-shrink-0">
                  <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-sm text-error">warning</span>
                    <span class="text-xs font-bold uppercase tracking-widest text-outline">Original</span>
                  </div>
                  <span class="text-[10px] text-outline">{{ originalLines.length }} lines</span>
                </div>
                <div class="flex-1 overflow-auto font-mono text-sm">
                  <table class="w-full border-collapse">
                    <tbody>
                      <tr
                        v-for="line in originalLines"
                        :key="line.number"
                        :id="`line-${line.number}`"
                        :class="[
                          line.isSelected ? 'bg-error/20' : '',
                          line.findingId && !line.isSelected ? 'bg-tertiary/10' : ''
                        ]"
                      >
                        <td class="w-10 text-right pr-3 py-0.5 text-outline/40 select-none border-r border-outline-variant/10 sticky left-0 bg-surface-container-lowest text-xs">
                          {{ line.number }}
                        </td>
                        <td 
                          :class="[
                            'pl-3 py-0.5 whitespace-pre text-on-surface-variant',
                            line.isSelected ? 'border-l-4 border-error' : '',
                            line.findingId && !line.isSelected ? 'border-l-4 border-tertiary/50' : ''
                          ]"
                        >{{ line.content }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Optimized Code (Selected Finding) -->
              <div class="flex-1 bg-surface-container rounded-xl border border-primary/20 ring-1 ring-primary/10 flex flex-col min-w-0 overflow-hidden">
                <div class="px-4 py-2 bg-primary/10 border-b border-primary/20 flex items-center justify-between flex-shrink-0">
                  <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-sm text-primary">check_circle</span>
                    <span class="text-xs font-bold uppercase tracking-widest text-primary">Optimized</span>
                  </div>
                  <span class="text-[10px] bg-primary text-on-primary px-1.5 py-0.5 rounded font-bold">RECOMMENDED</span>
                </div>
                <div class="flex-1 overflow-auto font-mono text-sm">
                  <table class="w-full border-collapse">
                    <tbody>
                      <tr
                        v-for="line in optimizedLines"
                        :key="line.number"
                        class="bg-primary/5"
                      >
                        <td class="w-10 text-right pr-3 py-0.5 text-outline/40 select-none border-r border-outline-variant/10 sticky left-0 bg-surface-container text-xs">
                          {{ line.number }}
                        </td>
                        <td class="pl-3 py-0.5 whitespace-pre text-on-surface-variant border-l-4 border-primary">{{ line.content }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- Explanation Box (Bottom) -->
            <div v-if="selectedFinding" class="flex-shrink-0 bg-surface-container-low rounded-xl border border-outline-variant/10 p-4">
              <div class="flex items-start justify-between gap-6">
                <!-- Explanation Content -->
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-3">
                    <span :class="['px-2 py-1 rounded-full text-[10px] font-bold uppercase border', getCategoryClass(selectedFinding.category)]">
                      {{ selectedFinding.category.replace('_', ' ') }}
                    </span>
                    <span class="text-xs text-outline">by {{ selectedFinding.commitAuthor }}</span>
                  </div>
                  
                  <h3 class="text-lg font-bold text-on-surface mb-2">Why This Is Better</h3>
                  <p class="text-sm text-on-surface-variant leading-relaxed mb-3">
                    {{ selectedFinding.explanation }}
                  </p>
                  
                  <!-- References -->
                  <div v-if="selectedFinding.references?.length" class="flex items-center gap-4">
                    <span class="text-xs font-bold uppercase tracking-wider text-outline">References:</span>
                    <div class="flex flex-wrap gap-3">
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

                  <!-- PR Link -->
                  <div v-if="selectedFinding.prUrl" class="mt-3 p-2 bg-primary/10 rounded-lg border border-primary/20 inline-block">
                    <p class="text-xs text-primary">
                      <span class="font-bold">PR Created:</span>
                      <a :href="selectedFinding.prUrl" target="_blank" class="ml-1 underline">View on GitHub</a>
                    </p>
                  </div>
                </div>

                <!-- Actions -->
                <div class="flex flex-col gap-3 items-end">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      :checked="!!selectedFinding.markedUnderstood"
                      :disabled="actionLoading"
                      class="h-4 w-4 rounded border-outline-variant bg-surface-container text-primary"
                      @change="markUnderstood"
                    />
                    <span class="text-sm text-on-surface-variant">Mark as understood</span>
                  </label>
                  
                  <div class="flex gap-2">
                    <button
                      :disabled="actionLoading || selectedFinding.explanationRequested"
                      class="px-4 py-2 border border-outline-variant/30 rounded-lg text-sm font-medium text-on-surface-variant hover:bg-surface-container transition-all disabled:opacity-50"
                      @click="requestExplanation"
                    >
                      {{ selectedFinding.explanationRequested ? '✓ Requested' : 'Request Help' }}
                    </button>
                    
                    <button
                      v-if="auth.isAdmin"
                      :disabled="actionLoading || selectedFinding.prCreated"
                      class="px-4 py-2 primary-gradient text-on-primary text-sm font-bold rounded-lg disabled:opacity-50"
                      @click="applyFix"
                    >
                      {{ selectedFinding.prCreated ? '✓ PR Created' : 'Apply Fix' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg cursor-pointer z-50"
      @click="toastMessage = ''"
    >
      {{ toastMessage }}
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="fixed inset-0 bg-background/80 flex items-center justify-center z-50">
      <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
    </div>
  </AppShell>
</template>
