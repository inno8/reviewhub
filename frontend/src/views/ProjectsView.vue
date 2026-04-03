<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { useProjectsStore } from '@/stores/projects';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const router = useRouter();
const auth = useAuthStore();

interface ProjectRow {
  id: number;
  name: string;
  description: string;
  provider: string;
  repo_url: string | null;
  repo_owner: string;
  repo_name: string;
  default_branch: string;
  full_name: string;
  webhook_url: string;
  webhook_active: boolean;
  created_by_email: string;
  member_count: number;
  created_at: string;
  updated_at: string;
}

const projectsStore = useProjectsStore();
const list = ref<ProjectRow[]>([]);
const loading = ref(false);
const loadError = ref('');
const drawerProject = ref<ProjectRow | null>(null);
const editMode = ref(false);
const saving = ref(false);
const deleting = ref(false);
const formError = ref('');
const unlinkDialogProject = ref<ProjectRow | null>(null);
const unlinkSubmitting = ref(false);
const unlinkError = ref('');
const editForm = ref({
  name: '',
  description: '',
  default_branch: '',
  repo_url: '',
});

const sortedList = computed(() =>
  [...list.value].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })),
);

function mapRow(raw: any): ProjectRow {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description ?? '',
    provider: raw.provider ?? 'github',
    repo_url: raw.repo_url ?? null,
    repo_owner: raw.repo_owner ?? '',
    repo_name: raw.repo_name ?? '',
    default_branch: raw.default_branch ?? 'main',
    full_name: raw.full_name ?? `${raw.repo_owner}/${raw.repo_name}`,
    webhook_url: raw.webhook_url ?? '',
    webhook_active: !!raw.webhook_active,
    created_by_email: raw.created_by_email ?? '',
    member_count: typeof raw.member_count === 'number' ? raw.member_count : 0,
    created_at: raw.created_at ?? '',
    updated_at: raw.updated_at ?? '',
  };
}

async function fetchAllProjects(): Promise<ProjectRow[]> {
  const out: ProjectRow[] = [];
  let page = 1;
  const maxPages = 100;
  for (;;) {
    if (page > maxPages) break;
    const { data } = await api.projects.list({ page });
    const rows = (data as any).results;
    if (Array.isArray(rows)) {
      out.push(...rows.map(mapRow));
      if (!(data as any).next) break;
      page += 1;
      continue;
    }
    if (Array.isArray(data)) {
      out.push(...(data as any[]).map(mapRow));
    }
    break;
  }
  return out;
}

async function loadList() {
  loading.value = true;
  loadError.value = '';
  try {
    list.value = await fetchAllProjects();
    await projectsStore.fetchProjects();
  } catch (e) {
    console.error(e);
    loadError.value = 'Could not load projects.';
    list.value = [];
  } finally {
    loading.value = false;
  }
}

function syncForm(p: ProjectRow) {
  editForm.value = {
    name: p.name,
    description: p.description || '',
    default_branch: p.default_branch || 'main',
    repo_url: p.repo_url || '',
  };
}

async function openDrawer(p: ProjectRow) {
  formError.value = '';
  editMode.value = false;
  drawerProject.value = p;
  try {
    const { data } = await api.projects.get(p.id);
    const row = mapRow(data);
    drawerProject.value = row;
    syncForm(row);
  } catch {
    syncForm(p);
  }
}

function closeDrawer() {
  drawerProject.value = null;
  editMode.value = false;
  formError.value = '';
}

function goToDashboardProject(p: ProjectRow) {
  projectsStore.setSelectedProject(p.id);
  router.push({ path: '/timeline' });
}

function openUnlinkDialog(p: ProjectRow) {
  unlinkDialogProject.value = p;
  unlinkError.value = '';
}

function closeUnlinkDialog() {
  unlinkDialogProject.value = null;
  unlinkError.value = '';
}

async function confirmUnlinkRepo() {
  const p = unlinkDialogProject.value;
  if (!p) return;
  unlinkSubmitting.value = true;
  unlinkError.value = '';
  try {
    await api.projects.unlinkRepo(p.id);
    closeUnlinkDialog();
    if (drawerProject.value?.id === p.id) closeDrawer();
    if (projectsStore.selectedProjectId === p.id) {
      projectsStore.setSelectedProject(null);
    }
    await loadList();
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } } };
    unlinkError.value = ax.response?.data?.detail || 'Could not unlink repository.';
  } finally {
    unlinkSubmitting.value = false;
  }
}

function startEdit() {
  if (!drawerProject.value) return;
  syncForm(drawerProject.value);
  editMode.value = true;
  formError.value = '';
}

function cancelEdit() {
  if (drawerProject.value) syncForm(drawerProject.value);
  editMode.value = false;
  formError.value = '';
}

async function saveProject() {
  const p = drawerProject.value;
  if (!p) return;
  const name = editForm.value.name.trim();
  if (!name) {
    formError.value = 'Name is required.';
    return;
  }
  saving.value = true;
  formError.value = '';
  try {
    await api.projects.update(p.id, {
      name,
      description: editForm.value.description.trim(),
      default_branch: editForm.value.default_branch.trim() || 'main',
    });
    const repoTrim = editForm.value.repo_url.trim();
    const prevRepo = (p.repo_url || '').trim();
    if (repoTrim && repoTrim !== prevRepo) {
      await api.projects.linkRepo(p.id, repoTrim);
    }
    const { data } = await api.projects.get(p.id);
    const row = mapRow(data);
    drawerProject.value = row;
    syncForm(row);
    editMode.value = false;
    await loadList();
  } catch (e: any) {
    const d = e?.response?.data;
    formError.value =
      d?.detail || d?.error || d?.name?.[0] || d?.repo_url?.[0] || 'Failed to save changes.';
  } finally {
    saving.value = false;
  }
}

async function deleteProject() {
  const p = drawerProject.value;
  if (!p) return;
  if (!confirm(`Delete project "${p.name}"? This cannot be undone.`)) return;
  deleting.value = true;
  formError.value = '';
  try {
    await api.projects.delete(p.id);
    closeDrawer();
    await loadList();
    if (projectsStore.selectedProjectId === p.id) {
      projectsStore.setSelectedProject(list.value[0]?.id ?? null);
    }
  } catch (e: any) {
    formError.value = e?.response?.data?.detail || e?.response?.data?.error || 'Failed to delete.';
  } finally {
    deleting.value = false;
  }
}

onMounted(() => {
  loadList();
});
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1 w-full">
      <header class="mb-10">
        <h1 class="text-4xl font-black text-on-surface tracking-tight mb-2">Projects</h1>
        <p class="text-outline text-sm">
          All projects you can access. Open one to view findings on the dashboard<span v-if="auth.isAdmin">
            — admins use the settings icon for edit or delete</span>.
        </p>
      </header>

      <div v-if="loading" class="flex justify-center py-20">
        <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
      </div>
      <div v-else-if="loadError" class="p-4 rounded-xl bg-error/10 border border-error/20 text-error text-sm">
        {{ loadError }}
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div
          v-for="p in sortedList"
          :key="p.id"
          class="bg-surface-container-low rounded-xl border border-outline-variant/10 hover:border-primary/30 transition-all group flex flex-col h-full"
        >
          <button
            type="button"
            class="text-left p-6 flex-1 flex flex-col rounded-t-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
            @click="goToDashboardProject(p)"
          >
            <div class="flex items-start justify-between mb-4">
              <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                <span class="material-symbols-outlined text-primary text-2xl">terminal</span>
              </div>
              <span class="material-symbols-outlined text-outline group-hover:text-primary transition-colors">arrow_forward</span>
            </div>
            <h3 class="text-lg font-bold text-on-surface mb-1">{{ p.name }}</h3>
            <p class="text-xs text-outline mb-4 line-clamp-2 flex-1">{{ p.description || 'No description' }}</p>
            <div class="flex flex-wrap gap-2 text-[10px] uppercase tracking-wider text-outline mb-3">
              <span class="px-2 py-0.5 rounded bg-surface-container-highest">{{ p.provider }}</span>
              <span v-if="p.repo_url" class="px-2 py-0.5 rounded bg-surface-container-highest font-mono normal-case">{{
                p.full_name
              }}</span>
              <span v-else class="px-2 py-0.5 rounded bg-surface-container-highest text-outline/80">No repo linked</span>
              <span class="px-2 py-0.5 rounded bg-surface-container-highest">{{ p.member_count }} members</span>
            </div>
            <div class="flex items-center gap-3 text-xs text-outline mt-auto">
              <span class="flex items-center gap-1"><span class="material-symbols-outlined text-sm">code</span>Project</span>
            </div>
          </button>
          <div
            v-if="auth.isAdmin || (p.repo_url && !auth.isAdmin)"
            class="flex items-center justify-end gap-1 px-6 pb-4 pt-0 border-t border-outline-variant/10"
            @click.stop
          >
            <button
              v-if="p.repo_url && !auth.isAdmin"
              type="button"
              class="p-2 rounded-lg text-outline hover:bg-error/15 hover:text-error transition-colors"
              title="Unlink repository from project"
              aria-label="Unlink repository"
              @click="openUnlinkDialog(p)"
            >
              <span class="material-symbols-outlined text-xl">link_off</span>
            </button>
            <button
              v-if="auth.isAdmin"
              type="button"
              class="p-2 rounded-lg text-outline hover:bg-surface-container-high hover:text-primary transition-colors"
              title="Project details and settings"
              aria-label="Open project settings"
              @click="openDrawer(p)"
            >
              <span class="material-symbols-outlined text-xl">settings</span>
            </button>
          </div>
        </div>

        <div v-if="!sortedList.length" class="col-span-full flex flex-col items-center justify-center py-20">
          <span class="material-symbols-outlined text-6xl text-outline mb-4">folder_off</span>
          <p class="text-on-surface-variant text-lg">No projects yet</p>
          <p class="text-outline text-sm">Create one from the sidebar if you are an admin, or ask to be added to a project.</p>
        </div>
      </div>
    </div>

    <Transition name="slide-right">
      <div v-if="drawerProject" class="fixed inset-y-0 right-0 z-[90] flex" @click.self="closeDrawer">
        <div class="flex-1 min-w-0" @click="closeDrawer" aria-hidden="true"></div>
        <div
          class="w-full max-w-md mt-16 bg-surface-container-low border-l border-outline-variant/20 shadow-2xl overflow-y-auto flex flex-col"
          @click.stop
        >
          <div class="p-6 border-b border-outline-variant/10 flex items-start justify-between gap-4 sticky top-0 bg-surface-container-low z-10">
            <div class="min-w-0">
              <h2 class="text-xl font-bold text-on-surface truncate">{{ drawerProject.name }}</h2>
              <p class="text-xs text-outline font-mono mt-0.5">{{ drawerProject.full_name }}</p>
            </div>
            <button type="button" class="text-outline hover:text-on-surface shrink-0" aria-label="Close" @click="closeDrawer">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>

          <div class="p-6 flex-1 space-y-6">
            <template v-if="!editMode">
              <dl class="space-y-4 text-sm">
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Description</dt>
                  <dd class="text-on-surface-variant whitespace-pre-wrap">{{ drawerProject.description || '—' }}</dd>
                </div>
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Provider</dt>
                  <dd class="text-on-surface capitalize">{{ drawerProject.provider }}</dd>
                </div>
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Repository</dt>
                  <dd class="text-on-surface-variant break-all font-mono text-xs">{{ drawerProject.repo_url || 'Not linked' }}</dd>
                </div>
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Default branch</dt>
                  <dd class="text-on-surface font-mono text-xs">{{ drawerProject.default_branch }}</dd>
                </div>
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Webhook</dt>
                  <dd class="text-on-surface-variant text-xs break-all">{{ drawerProject.webhook_url }}</dd>
                  <dd class="text-[10px] mt-1" :class="drawerProject.webhook_active ? 'text-primary' : 'text-outline'">
                    {{ drawerProject.webhook_active ? 'Active' : 'Inactive' }}
                  </dd>
                </div>
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Created by</dt>
                  <dd class="text-on-surface-variant text-xs">{{ drawerProject.created_by_email || '—' }}</dd>
                </div>
                <div>
                  <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Members</dt>
                  <dd class="text-on-surface">{{ drawerProject.member_count }}</dd>
                </div>
                <div class="grid grid-cols-2 gap-3 pt-2">
                  <div>
                    <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Created</dt>
                    <dd class="text-on-surface-variant text-xs">{{ drawerProject.created_at?.split('T')[0] || '—' }}</dd>
                  </div>
                  <div>
                    <dt class="text-[10px] font-bold uppercase tracking-widest text-outline mb-1">Updated</dt>
                    <dd class="text-on-surface-variant text-xs">{{ drawerProject.updated_at?.split('T')[0] || '—' }}</dd>
                  </div>
                </div>
              </dl>

              <div v-if="auth.isAdmin" class="flex flex-col gap-2 pt-2">
                <button
                  type="button"
                  class="w-full py-3 rounded-lg primary-gradient text-on-primary font-bold text-sm"
                  @click="startEdit"
                >
                  Edit project
                </button>
                <button
                  type="button"
                  class="w-full py-3 rounded-lg border border-error/40 text-error font-bold text-sm hover:bg-error/10 transition-colors"
                  :disabled="deleting"
                  @click="deleteProject"
                >
                  {{ deleting ? 'Deleting…' : 'Delete project' }}
                </button>
              </div>
            </template>

            <template v-else>
              <div class="space-y-4">
                <div>
                  <label class="text-[10px] font-bold uppercase tracking-widest text-outline block mb-1.5">Name</label>
                  <input
                    v-model="editForm.name"
                    type="text"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-2.5 px-3"
                  />
                </div>
                <div>
                  <label class="text-[10px] font-bold uppercase tracking-widest text-outline block mb-1.5">Description</label>
                  <textarea
                    v-model="editForm.description"
                    rows="3"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-2.5 px-3 resize-y"
                  />
                </div>
                <div>
                  <label class="text-[10px] font-bold uppercase tracking-widest text-outline block mb-1.5">Default branch</label>
                  <input
                    v-model="editForm.default_branch"
                    type="text"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-2.5 px-3 font-mono"
                  />
                </div>
                <div>
                  <label class="text-[10px] font-bold uppercase tracking-widest text-outline block mb-1.5">Repository URL</label>
                  <input
                    v-model="editForm.repo_url"
                    type="url"
                    placeholder="https://github.com/org/repo"
                    class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-2.5 px-3 font-mono"
                  />
                  <p class="text-[10px] text-outline mt-1.5">
                    Changing the URL re-parses provider and owner/repo. Leave unchanged to keep the current link.
                  </p>
                </div>
              </div>

              <div v-if="formError" class="p-3 rounded-lg bg-error/10 border border-error/20 text-error text-sm">
                {{ formError }}
              </div>

              <div class="flex gap-2 pt-2">
                <button
                  type="button"
                  class="flex-1 py-3 rounded-lg bg-surface-container-highest text-on-surface font-bold text-sm"
                  :disabled="saving"
                  @click="cancelEdit"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  class="flex-1 py-3 rounded-lg primary-gradient text-on-primary font-bold text-sm disabled:opacity-50"
                  :disabled="saving"
                  @click="saveProject"
                >
                  {{ saving ? 'Saving…' : 'Save' }}
                </button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Transition>

    <Teleport to="body">
      <div
        v-if="unlinkDialogProject"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50"
        role="presentation"
        @click.self="closeUnlinkDialog"
      >
        <div
          class="bg-surface-container-low max-w-md w-full rounded-2xl border border-outline-variant/20 shadow-2xl p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="unlink-dialog-title"
          @click.stop
        >
          <h2 id="unlink-dialog-title" class="text-lg font-bold text-on-surface mb-2">Unlink repository?</h2>
          <p class="text-sm text-on-surface-variant leading-relaxed mb-3">
            You are about to remove the Git connection from
            <span class="font-semibold text-on-surface">« {{ unlinkDialogProject.name }} »</span>.
            For <span class="font-semibold text-on-surface">your account only</span>, all reviews tied to this
            project will be permanently deleted: findings, evaluations, skills metrics for this project,
            detected patterns, batch analysis history, and related notifications.
          </p>
          <p class="text-sm text-error font-semibold mb-4">
            This cannot be undone. Other team members are not affected, but you will lose your review data for
            this project.
          </p>
          <div v-if="unlinkError" class="mb-4 p-3 rounded-lg bg-error/10 border border-error/30 text-error text-sm">
            {{ unlinkError }}
          </div>
          <div class="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
            <button
              type="button"
              class="px-4 py-2.5 rounded-lg text-on-surface font-medium border border-outline-variant/30 hover:bg-surface-container-high"
              :disabled="unlinkSubmitting"
              @click="closeUnlinkDialog"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-4 py-2.5 rounded-lg bg-error text-on-error font-bold hover:bg-error/90 disabled:opacity-50"
              :disabled="unlinkSubmitting"
              @click="confirmUnlinkRepo"
            >
              {{ unlinkSubmitting ? 'Working…' : 'Unlink and delete my data' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </AppShell>
</template>

<style scoped>
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
