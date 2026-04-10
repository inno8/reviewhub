<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';
import Prism from 'prismjs';
// NOTE: We intentionally do NOT import prismjs/themes/prism.css (light theme).
// Dark token colors are defined in <style> below to match VS Code Dark+.
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-go';
import 'prismjs/components/prism-java';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-ruby';
import 'prismjs/components/prism-php';

const router = useRouter();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const findings = ref<any[]>([]);
const loading = ref(false);
const selectedProject = ref('');
const selectedUser = ref('');
const users = ref<any[]>([]);
const expandedId = ref<number | null>(null);

const isAdmin = computed(() => authStore.user?.role === 'admin' || authStore.user?.role === 'ADMIN');

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id;
}

async function loadFindings() {
  loading.value = true;
  try {
    const params: Record<string, any> = {};
    if (selectedProject.value) params.project = selectedProject.value;
    if (selectedUser.value && isAdmin.value) params.user = selectedUser.value;
    const { data } = await api.findings.resolved(params);
    findings.value = data.results || data || [];
  } catch {
    findings.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadUsers() {
  if (!isAdmin.value) return;
  try {
    const { data } = await api.users.list();
    users.value = (data.results || data || []).filter((u: any) => u.role !== 'admin');
  } catch {
    users.value = [];
  }
}

function goToReview(finding: any) {
  router.push({
    path: '/file-review',
    query: { evaluation: finding.evaluation_id, project: finding.project_id },
  });
}

function severityColor(sev: string) {
  const map: Record<string, string> = {
    critical: 'text-red-400 bg-red-500/10',
    warning: 'text-amber-400 bg-amber-500/10',
    info: 'text-blue-400 bg-blue-500/10',
    suggestion: 'text-teal-400 bg-teal-500/10',
  };
  return map[sev] || 'text-on-surface-variant bg-surface-container';
}

function understandingBadge(level: string) {
  const map: Record<string, { label: string; class: string }> = {
    got_it: { label: 'Understood', class: 'text-green-400 bg-green-500/10' },
    partial: { label: 'Partial', class: 'text-amber-400 bg-amber-500/10' },
    not_yet: { label: 'Not Yet', class: 'text-red-400 bg-red-500/10' },
  };
  return map[level] || { label: '-', class: 'text-on-surface-variant bg-surface-container' };
}

function formatDate(d: string) {
  if (!d) return '-';
  return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function shortSha(sha: string) {
  return sha ? sha.substring(0, 7) : '-';
}

function detectLanguage(filePath: string): string {
  if (!filePath) return 'python';
  const ext = filePath.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescript',
    go: 'go', java: 'java', rb: 'ruby', php: 'php', sh: 'bash',
    sql: 'sql', html: 'markup', css: 'css', json: 'json', vue: 'markup',
  };
  return map[ext] || 'python';
}

function highlightCode(code: string, filePath: string): string {
  if (!code) return '';
  const lang = detectLanguage(filePath);
  const grammar = Prism.languages[lang];
  if (grammar) {
    return Prism.highlight(code, grammar, lang);
  }
  return code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

watch([selectedProject, selectedUser], () => loadFindings());

onMounted(async () => {
  await projectsStore.fetchProjects();
  await loadUsers();
  await loadFindings();
});
</script>

<template>
  <AppShell>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 py-6">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-on-surface flex items-center gap-2">
            <span class="material-symbols-outlined text-green-400">task_alt</span>
            Resolved Issues
          </h1>
          <p class="text-sm text-on-surface-variant mt-1">Track fixed findings and understanding progress</p>
        </div>
        <div class="flex items-center gap-1 px-3 py-1.5 bg-green-500/10 rounded-full">
          <span class="material-symbols-outlined text-green-400 text-sm">check_circle</span>
          <span class="text-sm font-bold text-green-400">{{ findings.length }} resolved</span>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex flex-wrap gap-3 mb-6">
        <select v-model="selectedProject"
          class="px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20 text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
          <option value="">All Projects</option>
          <option v-for="p in projectsStore.projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <select v-if="isAdmin" v-model="selectedUser"
          class="px-3 py-2 bg-surface-container rounded-lg border border-outline-variant/20 text-on-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/50">
          <option value="">All Developers</option>
          <option v-for="u in users" :key="u.id" :value="u.id">{{ u.display_name || u.username || u.email }}</option>
        </select>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-20">
        <span class="material-symbols-outlined text-4xl text-primary animate-spin">progress_activity</span>
      </div>

      <!-- Empty state -->
      <div v-else-if="!findings.length" class="text-center py-20">
        <span class="material-symbols-outlined text-5xl text-outline mb-3">fact_check</span>
        <p class="text-on-surface-variant">No resolved findings yet.</p>
        <p class="text-sm text-outline mt-1">Complete Fix & Learn and mark issues as fixed to see them here.</p>
      </div>

      <!-- Cards list -->
      <div v-else class="space-y-3">
        <div v-for="f in findings" :key="f.id"
          class="bg-surface-container rounded-xl border border-outline-variant/10 overflow-hidden transition-all"
          :class="expandedId === f.id ? 'ring-1 ring-primary/30' : ''">

          <!-- Summary row (always visible) -->
          <div class="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-surface-container-high/50 transition-colors"
            @click="toggleExpand(f.id)">
            <!-- Expand icon -->
            <span class="material-symbols-outlined text-lg text-outline transition-transform"
              :class="expandedId === f.id ? 'rotate-90' : ''">
              chevron_right
            </span>

            <!-- Severity -->
            <span :class="severityColor(f.severity)" class="px-2 py-0.5 rounded-full text-xs font-bold uppercase shrink-0">
              {{ f.severity }}
            </span>

            <!-- Title -->
            <p class="text-on-surface font-medium flex-1 truncate">{{ f.title }}</p>

            <!-- Understanding badge -->
            <span :class="understandingBadge(f.understanding_level).class"
              class="px-2 py-0.5 rounded-full text-xs font-bold shrink-0">
              {{ understandingBadge(f.understanding_level).label }}
            </span>

            <!-- Fix commit -->
            <span v-if="f.fixed_in_commit" class="font-mono text-xs text-primary shrink-0">{{ shortSha(f.fixed_in_commit) }}</span>

            <!-- Fixed date -->
            <span class="text-xs text-green-400 shrink-0 whitespace-nowrap">{{ formatDate(f.fixed_at) }}</span>

            <!-- Project / Author -->
            <span class="text-xs text-on-surface-variant shrink-0 hidden sm:inline">{{ f.project_name }}</span>
            <span v-if="isAdmin" class="text-xs text-outline shrink-0 hidden md:inline">{{ f.author_name }}</span>
          </div>

          <!-- Expanded detail panel -->
          <div v-if="expandedId === f.id" class="border-t border-outline-variant/10 px-5 py-5 space-y-5 bg-surface/50">

            <!-- Meta row -->
            <div class="flex flex-wrap gap-x-6 gap-y-2 text-xs text-on-surface-variant">
              <span><b class="text-on-surface">File:</b> {{ f.file_path }}:{{ f.line_start }}</span>
              <span><b class="text-on-surface">Found:</b> {{ formatDate(f.evaluation_date) }} in commit {{ shortSha(f.commit_sha) }}</span>
              <span><b class="text-on-surface">Fixed:</b> {{ formatDate(f.fixed_at) }}
                <span v-if="f.fixed_in_commit"> in commit <span class="text-primary font-mono">{{ shortSha(f.fixed_in_commit) }}</span></span>
              </span>
              <span v-if="isAdmin"><b class="text-on-surface">Developer:</b> {{ f.author_name }} ({{ f.author_email }})</span>
            </div>

            <!-- Description -->
            <div>
              <h4 class="text-xs font-bold text-on-surface-variant uppercase tracking-wide mb-1.5">Issue Description</h4>
              <p class="text-sm text-on-surface leading-relaxed">{{ f.description }}</p>
            </div>

            <!-- Code: Original vs Suggested -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div v-if="f.original_code">
                <h4 class="text-xs font-bold text-red-400 uppercase tracking-wide mb-1.5">Original Code</h4>
                <pre class="code-block code-block--original text-xs bg-red-500/5 border border-red-500/10 rounded-lg p-3 overflow-x-auto font-mono whitespace-pre-wrap"><code v-html="highlightCode(f.original_code, f.file_path)"></code></pre>
              </div>
              <div v-if="f.suggested_code">
                <h4 class="text-xs font-bold text-green-400 uppercase tracking-wide mb-1.5">Suggested Fix</h4>
                <pre class="code-block code-block--suggested text-xs bg-green-500/5 border border-green-500/10 rounded-lg p-3 overflow-x-auto font-mono whitespace-pre-wrap"><code v-html="highlightCode(f.suggested_code, f.file_path)"></code></pre>
              </div>
            </div>

            <!-- Explanation from LLM -->
            <div v-if="f.explanation">
              <h4 class="text-xs font-bold text-blue-400 uppercase tracking-wide mb-1.5">Why This Matters</h4>
              <p class="text-sm text-on-surface-variant leading-relaxed">{{ f.explanation }}</p>
            </div>

            <!-- Developer's understanding -->
            <div v-if="f.developer_explanation" class="bg-surface-container rounded-lg border border-outline-variant/10 p-4 space-y-3">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-sm" :class="{
                  'text-green-400': f.understanding_level === 'got_it',
                  'text-amber-400': f.understanding_level === 'partial',
                  'text-red-400': f.understanding_level === 'not_yet',
                }">school</span>
                <h4 class="text-xs font-bold text-on-surface uppercase tracking-wide">Developer's Explanation</h4>
                <span :class="understandingBadge(f.understanding_level).class"
                  class="px-2 py-0.5 rounded-full text-xs font-bold ml-auto">
                  {{ understandingBadge(f.understanding_level).label }}
                </span>
              </div>
              <p class="text-sm text-on-surface leading-relaxed">{{ f.developer_explanation }}</p>
              <div v-if="f.understanding_feedback" class="pt-2 border-t border-outline-variant/10">
                <p class="text-xs font-bold text-on-surface-variant mb-1">AI Feedback:</p>
                <p class="text-sm text-on-surface-variant">{{ f.understanding_feedback }}</p>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex gap-3 pt-2">
              <button @click="goToReview(f)"
                class="flex items-center gap-1.5 px-4 py-2 bg-primary/10 text-primary text-sm font-bold rounded-lg hover:bg-primary/20 transition-all">
                <span class="material-symbols-outlined text-sm">open_in_new</span>
                View Full Review
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
/* VS Code Dark+ inspired Prism token colors */
.code-block :deep(.token.keyword) { color: #c586c0; }
.code-block :deep(.token.builtin) { color: #4ec9b0; }
.code-block :deep(.token.string),
.code-block :deep(.token.attr-value) { color: #ce9178; }
.code-block :deep(.token.function) { color: #dcdcaa; }
.code-block :deep(.token.number) { color: #b5cea8; }
.code-block :deep(.token.boolean) { color: #569cd6; }
.code-block :deep(.token.comment) { color: #6a9955; font-style: italic; }
.code-block :deep(.token.operator),
.code-block :deep(.token.punctuation) { color: #d4d4d4; }
.code-block :deep(.token.class-name),
.code-block :deep(.token.constant) { color: #4ec9b0; }
.code-block :deep(.token.property),
.code-block :deep(.token.parameter) { color: #9cdcfe; }
.code-block :deep(.token.decorator),
.code-block :deep(.token.attr-name) { color: #dcdcaa; }
.code-block :deep(.token.tag) { color: #569cd6; }
</style>
