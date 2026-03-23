<script setup lang="ts">
import { onMounted, ref } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';

interface User {
  id: number;
  username: string;
  email: string;
  role: 'ADMIN' | 'INTERN';
  projects?: Project[];
}

interface Project {
  id: number;
  name: string;
  displayName: string;
}

interface UserForm {
  username: string;
  email: string;
  password: string;
  role: 'ADMIN' | 'INTERN';
  projectIds: number[];
}

const users = ref<User[]>([]);
const projects = ref<Project[]>([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref('');
const isModalOpen = ref(false);
const editingUserId = ref<number | null>(null);

const form = ref<UserForm>({
  username: '',
  email: '',
  password: '',
  role: 'INTERN',
  projectIds: [],
});

function resetForm() {
  form.value = {
    username: '',
    email: '',
    password: '',
    role: 'INTERN',
    projectIds: [],
  };
}

function toggleProject(projectId: number) {
  const set = new Set(form.value.projectIds);
  if (set.has(projectId)) set.delete(projectId);
  else set.add(projectId);
  form.value.projectIds = Array.from(set);
}

function openCreateModal() {
  editingUserId.value = null;
  resetForm();
  errorMessage.value = '';
  isModalOpen.value = true;
}

function openEditModal(user: User) {
  editingUserId.value = user.id;
  form.value = {
    username: user.username,
    email: user.email,
    password: '',
    role: user.role,
    projectIds: (user.projects || []).map((project) => project.id),
  };
  errorMessage.value = '';
  isModalOpen.value = true;
}

function closeModal() {
  isModalOpen.value = false;
  editingUserId.value = null;
}

async function fetchUsers() {
  loading.value = true;
  try {
    const { data } = await api.users.list();
    users.value = data.users;
  } finally {
    loading.value = false;
  }
}

async function fetchProjects() {
  const { data } = await api.projects.list();
  projects.value = data.projects;
}

async function saveUser() {
  saving.value = true;
  errorMessage.value = '';
  try {
    if (editingUserId.value) {
      const payload: any = {
        username: form.value.username,
        email: form.value.email,
        role: form.value.role,
        projectIds: form.value.projectIds,
      };
      if (form.value.password) {
        payload.password = form.value.password;
      }
      await api.users.update(editingUserId.value, payload);
    } else {
      await api.users.create({
        username: form.value.username,
        email: form.value.email,
        password: form.value.password,
        role: form.value.role,
        projectIds: form.value.projectIds,
      });
    }

    await fetchUsers();
    closeModal();
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.error || 'Failed to save user.';
  } finally {
    saving.value = false;
  }
}

async function deleteUser(user: User) {
  const confirmed = window.confirm(`Delete user "${user.username}"?`);
  if (!confirmed) return;
  try {
    await api.users.delete(user.id);
    await fetchUsers();
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.error || 'Failed to delete user.';
  }
}

onMounted(async () => {
  await Promise.all([fetchProjects(), fetchUsers()]);
});
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <!-- Header Section -->
        <div class="flex justify-between items-end mb-10">
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">Team Management</h1>
            <p class="text-on-surface-variant mt-2 max-w-lg">
              Manage pedagogical access, review assignments, and system-wide collaborator permissions.
            </p>
          </div>
          <button
            class="primary-gradient text-on-primary px-6 py-3 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
            @click="openCreateModal"
          >
            <span class="material-symbols-outlined">person_add</span>
            Add User
          </button>
        </div>

        <p v-if="errorMessage" class="text-sm text-error mb-4">{{ errorMessage }}</p>

        <!-- User Table Container -->
        <div class="bg-surface-container-low rounded-xl overflow-hidden border border-outline-variant/10">
          <div v-if="loading" class="p-8 text-center text-outline">Loading users...</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                  <th class="px-6 py-4">Collaborator</th>
                  <th class="px-6 py-4">Role</th>
                  <th class="px-6 py-4">Active Projects</th>
                  <th class="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/5">
                <tr
                  v-for="user in users"
                  :key="user.id"
                  class="hover:bg-surface-container-high/40 transition-colors group"
                >
                  <td class="px-6 py-5">
                    <div class="flex items-center gap-4">
                      <div class="h-10 w-10 rounded-lg bg-secondary-container flex items-center justify-center overflow-hidden border border-outline-variant/20 text-sm font-bold text-primary">
                        {{ user.username.slice(0, 2).toUpperCase() }}
                      </div>
                      <div>
                        <div class="text-sm font-bold text-on-surface">{{ user.username }}</div>
                        <div class="text-xs text-on-surface-variant">{{ user.email }}</div>
                      </div>
                    </div>
                  </td>
                  <td class="px-6 py-5">
                    <span
                      :class="[
                        'px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border',
                        user.role === 'ADMIN'
                          ? 'bg-primary/10 text-primary border-primary/20'
                          : 'bg-tertiary/10 text-tertiary border-tertiary/20'
                      ]"
                    >
                      {{ user.role }}
                    </span>
                  </td>
                  <td class="px-6 py-5">
                    <div class="flex gap-2 flex-wrap">
                      <span
                        v-for="project in user.projects || []"
                        :key="project.id"
                        class="text-[11px] bg-surface-container-highest px-2 py-0.5 rounded text-on-surface-variant"
                      >
                        {{ project.displayName }}
                      </span>
                      <span v-if="!user.projects?.length" class="text-[11px] text-outline">No projects</span>
                    </div>
                  </td>
                  <td class="px-6 py-5 text-right">
                    <div class="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        class="p-2 hover:bg-surface-container-highest rounded-lg text-on-surface-variant hover:text-primary transition-colors"
                        @click="openEditModal(user)"
                      >
                        <span class="material-symbols-outlined text-[20px]">edit</span>
                      </button>
                      <button
                        class="p-2 hover:bg-error/10 rounded-lg text-on-surface-variant hover:text-error transition-colors"
                        @click="deleteUser(user)"
                      >
                        <span class="material-symbols-outlined text-[20px]">delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal Overlay -->
    <div
      v-if="isModalOpen"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
    >
      <div class="glass-panel w-full max-w-lg rounded-xl overflow-hidden shadow-2xl">
        <!-- Modal Header -->
        <div class="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center">
          <h3 class="text-xl font-bold text-on-surface">
            {{ editingUserId ? 'Edit User' : 'Add User' }}
          </h3>
          <button class="text-outline hover:text-on-surface transition-colors" @click="closeModal">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <!-- Modal Content -->
        <form class="p-8 space-y-6" @submit.prevent="saveUser">
          <div class="space-y-4">
            <!-- Text Inputs -->
            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Username</label>
                <input
                  v-model="form.username"
                  type="text"
                  required
                  placeholder="e.g. jdoe"
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
                />
              </div>
              <div class="space-y-1.5">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Role</label>
                <select
                  v-model="form.role"
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4"
                >
                  <option value="ADMIN">Admin</option>
                  <option value="INTERN">Intern</option>
                </select>
              </div>
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">Email Address</label>
              <input
                v-model="form.email"
                type="email"
                required
                placeholder="john.doe@company.com"
                class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
              />
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">
                {{ editingUserId ? 'Password (leave blank to keep)' : 'Password' }}
              </label>
              <input
                v-model="form.password"
                type="password"
                :required="!editingUserId"
                placeholder="••••••••"
                class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
              />
            </div>

            <!-- Project Checkboxes -->
            <div class="space-y-3">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">Assign Projects</label>
              <div class="grid grid-cols-2 gap-3 p-4 bg-surface-container-lowest rounded-lg">
                <label
                  v-for="project in projects"
                  :key="project.id"
                  class="flex items-center gap-3 cursor-pointer group"
                >
                  <input
                    type="checkbox"
                    :checked="form.projectIds.includes(project.id)"
                    class="w-4 h-4 rounded border-outline-variant bg-surface-container text-primary focus:ring-offset-background"
                    @change="toggleProject(project.id)"
                  />
                  <span class="text-sm text-on-surface-variant group-hover:text-on-surface transition-colors">
                    {{ project.displayName }}
                  </span>
                </label>
              </div>
            </div>
          </div>

          <!-- Modal Actions -->
          <div class="flex gap-4 pt-4">
            <button
              type="button"
              class="flex-1 bg-surface-container-highest text-on-surface font-bold py-3 rounded-lg hover:bg-outline-variant transition-colors"
              @click="closeModal"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 shadow-lg shadow-primary/20 disabled:opacity-50"
            >
              {{ saving ? 'Saving...' : 'Save User' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppShell>
</template>
