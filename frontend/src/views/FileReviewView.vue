<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
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
const showOptimized = ref(false);

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
      // Try to fetch full file content from GitHub
      try {
        const { data } = await api.findings.getFileContent(findings.value[0].id);
        fileContent.value = data.content;
      } catch {
        // Use original code as fallback
        fileContent.value = findings.value[0].originalCode;
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

// Parse the file into lines with issue annotations
const annotatedLines = computed(() => {
  const content = showOptimized.value && selectedFinding.value 
    ? selectedFinding.value.optimizedCode 
    : fileContent.value || selectedFinding.value?.originalCode || '';
  
  const lines = content.split('\n');
  
  // Find which lines belong to each finding's snippet
  const issueRanges: Map<number, { findingId: number; type: 'start' | 'middle' | 'end' | 'single' }> = new Map();
  
  if (!showOptimized.value) {
    findings.value.forEach(finding => {
      const snippetLines = finding.originalCode.split('\n');
      // Try to find the snippet in the file content
      const fileLines = (fileContent.value || finding.originalCode).split('\n');
      
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
            const lineNum = i + j;
            if (snippetLines.length === 1) {
              issueRanges.set(lineNum, { findingId: finding.id, type: 'single' });
            } else if (j === 0) {
              issueRanges.set(lineNum, { findingId: finding.id, type: 'start' });
            } else if (j === snippetLines.length - 1) {
              issueRanges.set(lineNum, { findingId: finding.id, type: 'end' });
            } else {
              issueRanges.set(lineNum, { findingId: finding.id, type: 'middle' });
            }
          }
          break;
        }
      }
    });
  }
  
  return lines.map((content, idx) => {
    const issue = issueRanges.get(idx);
    return {
      number: idx + 1,
      content,
      hasIssue: !!issue,
      findingId: issue?.findingId,
      isStart: issue?.type === 'start' || issue?.type === 'single',
      isEnd: issue?.type === 'end' || issue?.type === 'single',
      isSelected: issue?.findingId === selectedFindingId.value,
    };
  });
});

// Group consecutive lines with issues for collapse indicators
const issueBlocks = computed(() => {
  const blocks: { startLine: number; endLine: number; findingId: number; finding: Finding }[] = [];
  let currentBlock: { startLine: number; endLine: number; findingId: number } | null = null;
  
  annotatedLines.value.forEach((line) => {
    if (line.hasIssue && line.findingId) {
      if (currentBlock && currentBlock.findingId === line.findingId) {
        currentBlock.endLine = line.number;
      } else {
        if (currentBlock) {
          const finding = findings.value.find(f => f.id === currentBlock!.findingId);
          if (finding) blocks.push({ ...currentBlock, finding });
        }
        currentBlock = { startLine: line.number, endLine: line.number, findingId: line.findingId };
      }
    } else {
      if (currentBlock) {
        const finding = findings.value.find(f => f.id === currentBlock!.findingId);
        if (finding) blocks.push({ ...currentBlock, finding });
        currentBlock = null;
      }
    }
  });
  
  if (currentBlock) {
    const finding = findings.value.find(f => f.id === currentBlock!.findingId);
    if (finding) blocks.push({ ...currentBlock, finding });
  }
  
  return blocks;
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

function getDiffClass(line: typeof annotatedLines.value[0]) {
  if (!line.hasIssue) return '';
  if (showOptimized.value) {
    return 'bg-primary/10 border-l-4 border-primary';
  }
  return line.isSelected 
    ? 'bg-error/20 border-l-4 border-error' 
    : 'bg-tertiary/10 border-l-4 border-tertiary/50';
}

function scrollToIssue(findingId: number) {
  selectedFindingId.value = findingId;
  const block = issueBlocks.value.find(b => b.findingId === findingId);
  if (block) {
    const element = document.getElementById(`line-${block.startLine}`);
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
    <div class="p-6 flex-1 flex flex-col h-[calc(100vh-64px)]">
      <div class="max-w-[1400px] mx-auto w-full flex flex-col h-full">
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
          
          <!-- View Toggle -->
          <div class="flex items-center gap-2 bg-surface-container-low p-1 rounded-lg">
            <button
              :class="[
                'px-4 py-2 rounded-md text-sm font-medium transition-all',
                !showOptimized ? 'bg-error/20 text-error' : 'text-outline hover:text-on-surface'
              ]"
              @click="showOptimized = false"
            >
              <span class="material-symbols-outlined text-sm mr-1 align-middle">warning</span>
              Original
            </button>
            <button
              :class="[
                'px-4 py-2 rounded-md text-sm font-medium transition-all',
                showOptimized ? 'bg-primary/20 text-primary' : 'text-outline hover:text-on-surface'
              ]"
              @click="showOptimized = true"
            >
              <span class="material-symbols-outlined text-sm mr-1 align-middle">check_circle</span>
              Optimized
            </button>
          </div>
        </div>

        <!-- Main Content Area -->
        <div class="flex gap-4 flex-1 min-h-0">
          <!-- Issue Navigator Sidebar -->
          <div class="w-72 flex-shrink-0 bg-surface-container-low rounded-xl border border-outline-variant/10 flex flex-col">
            <div class="p-4 border-b border-outline-variant/10">
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
                  {{ finding.explanation.slice(0, 100) }}...
                </p>
                <div class="flex items-center gap-2 mt-2 text-[10px] text-outline">
                  <span>Lines {{ issueBlocks.find(b => b.findingId === finding.id)?.startLine || '?' }}-{{ issueBlocks.find(b => b.findingId === finding.id)?.endLine || '?' }}</span>
                  <span v-if="finding.markedUnderstood" class="text-primary">✓ Understood</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Code View -->
          <div class="flex-1 bg-surface-container-lowest rounded-xl border border-outline-variant/10 flex flex-col min-w-0 overflow-hidden">
            <!-- Code Header -->
            <div class="px-4 py-3 bg-surface-container border-b border-outline-variant/10 flex items-center justify-between flex-shrink-0">
              <div class="flex items-center gap-4">
                <span class="text-xs font-mono text-outline">{{ annotatedLines.length }} lines</span>
                <div v-if="!showOptimized" class="flex items-center gap-2">
                  <span class="w-3 h-3 bg-error/20 border-l-2 border-error"></span>
                  <span class="text-xs text-outline">Selected issue</span>
                  <span class="w-3 h-3 bg-tertiary/10 border-l-2 border-tertiary/50 ml-2"></span>
                  <span class="text-xs text-outline">Other issues</span>
                </div>
                <div v-else class="flex items-center gap-2">
                  <span class="w-3 h-3 bg-primary/10 border-l-2 border-primary"></span>
                  <span class="text-xs text-outline">Optimized code</span>
                </div>
              </div>
            </div>

            <!-- Code Content -->
            <div class="flex-1 overflow-auto font-mono text-sm">
              <table class="w-full border-collapse">
                <tbody>
                  <tr
                    v-for="line in annotatedLines"
                    :key="line.number"
                    :id="`line-${line.number}`"
                    :class="getDiffClass(line)"
                  >
                    <td class="w-12 text-right pr-4 py-0.5 text-outline/50 select-none border-r border-outline-variant/10 sticky left-0 bg-surface-container-lowest">
                      {{ line.number }}
                    </td>
                    <td class="pl-4 py-0.5 whitespace-pre text-on-surface-variant">{{ line.content }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Issue Detail Panel -->
          <div v-if="selectedFinding" class="w-96 flex-shrink-0 bg-surface-container-low rounded-xl border border-outline-variant/10 flex flex-col">
            <div class="p-4 border-b border-outline-variant/10">
              <div class="flex items-center gap-2 mb-2">
                <span :class="['px-2 py-1 rounded-full text-[10px] font-bold uppercase border', getCategoryClass(selectedFinding.category)]">
                  {{ selectedFinding.category.replace('_', ' ') }}
                </span>
                <span class="text-xs text-outline">by {{ selectedFinding.commitAuthor }}</span>
              </div>
              <h3 class="text-lg font-bold text-on-surface">Why This Is Better</h3>
            </div>
            
            <div class="flex-1 overflow-y-auto p-4">
              <p class="text-sm text-on-surface-variant leading-relaxed mb-4">
                {{ selectedFinding.explanation }}
              </p>
              
              <!-- References -->
              <div v-if="selectedFinding.references?.length" class="mb-4">
                <h4 class="text-xs font-bold uppercase tracking-wider text-outline mb-2">References</h4>
                <div class="space-y-1">
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
              <div v-if="selectedFinding.prUrl" class="p-3 bg-primary/10 rounded-lg border border-primary/20 mb-4">
                <p class="text-xs text-primary">
                  <span class="font-bold">PR Created:</span>
                  <a :href="selectedFinding.prUrl" target="_blank" class="ml-1 underline">
                    View on GitHub
                  </a>
                </p>
              </div>
            </div>

            <!-- Actions -->
            <div class="p-4 border-t border-outline-variant/10 space-y-3">
              <label class="flex items-center gap-3 cursor-pointer">
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
                  class="flex-1 px-3 py-2 border border-outline-variant/30 rounded-lg text-xs font-medium text-on-surface-variant hover:bg-surface-container transition-all disabled:opacity-50"
                  @click="requestExplanation"
                >
                  {{ selectedFinding.explanationRequested ? '✓ Requested' : 'Request Help' }}
                </button>
                
                <button
                  v-if="auth.isAdmin"
                  :disabled="actionLoading || selectedFinding.prCreated"
                  class="flex-1 px-3 py-2 primary-gradient text-on-primary text-xs font-bold rounded-lg disabled:opacity-50"
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

    <!-- Toast -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg cursor-pointer z-50"
      @click="toastMessage = ''"
    >
      {{ toastMessage }}
    </div>
  </AppShell>
</template>
