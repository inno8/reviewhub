<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const projectsStore = useProjectsStore();
const authStore = useAuthStore();

const findings = ref<any[]>([]);
const loading = ref(false);
const selectedProject = ref('');
const selectedUser = ref('');
const users = ref<any[]>([]);

const isAdmin = computed(() => authStore.user?.role === 'admin' || authStore.user?.role === 'ADMIN');

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

      <!-- Table -->
      <div v-else class="bg-surface-container rounded-2xl border border-outline-variant/10 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-outline-variant/10 text-left">
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Finding</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Severity</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Understanding</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">File</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Found</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Fixed</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Fix Commit</th>
                <th v-if="isAdmin" class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Developer</th>
                <th class="px-4 py-3 text-xs font-bold text-on-surface-variant uppercase tracking-wide">Project</th>
                <th class="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in findings" :key="f.id"
                class="border-b border-outline-variant/5 hover:bg-surface-container-high/50 transition-colors cursor-pointer"
                @click="goToReview(f)">
                <td class="px-4 py-3">
                  <p class="text-on-surface font-medium truncate max-w-[250px]">{{ f.title }}</p>
                </td>
                <td class="px-4 py-3">
                  <span :class="severityColor(f.severity)" class="px-2 py-0.5 rounded-full text-xs font-bold uppercase">
                    {{ f.severity }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span :class="understandingBadge(f.understanding_level).class"
                    class="px-2 py-0.5 rounded-full text-xs font-bold">
                    {{ understandingBadge(f.understanding_level).label }}
                  </span>
                </td>
                <td class="px-4 py-3 text-on-surface-variant font-mono text-xs truncate max-w-[180px]">
                  {{ f.file_path }}
                </td>
                <td class="px-4 py-3 text-on-surface-variant text-xs whitespace-nowrap">
                  {{ formatDate(f.evaluation_date) }}
                </td>
                <td class="px-4 py-3 text-green-400 text-xs whitespace-nowrap">
                  {{ formatDate(f.fixed_at) }}
                </td>
                <td class="px-4 py-3 font-mono text-xs">
                  <span v-if="f.fixed_in_commit" class="text-primary">{{ shortSha(f.fixed_in_commit) }}</span>
                  <span v-else class="text-outline">-</span>
                </td>
                <td v-if="isAdmin" class="px-4 py-3 text-on-surface-variant text-xs">
                  {{ f.author_name || f.author_email }}
                </td>
                <td class="px-4 py-3 text-on-surface-variant text-xs">
                  {{ f.project_name }}
                </td>
                <td class="px-4 py-3">
                  <span class="material-symbols-outlined text-sm text-outline">chevron_right</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </AppShell>
</template>
