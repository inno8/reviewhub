<script setup lang="ts">
import { onMounted, ref } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Card from '@/components/common/Card.vue';
import Badge from '@/components/common/Badge.vue';
import Button from '@/components/common/Button.vue';
import Modal from '@/components/common/Modal.vue';
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
      const payload = {
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
  <div class="flex min-h-screen bg-dark-bg">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="space-y-6 p-6">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-semibold">User Management</h2>
          <Button @click="openCreateModal">Add User</Button>
        </div>
        <p v-if="errorMessage" class="text-sm text-error">{{ errorMessage }}</p>
        <Card>
          <div v-if="loading" class="text-sm text-text-secondary">Loading users...</div>
          <div v-else class="space-y-2">
            <div
              v-for="user in users"
              :key="user.id"
              class="flex cursor-pointer items-center justify-between rounded-lg border border-dark-border bg-dark-bg px-3 py-2"
              @click="openEditModal(user)"
            >
              <div class="space-y-1">
                <p class="text-sm font-semibold">{{ user.username }}</p>
                <p class="text-xs text-text-secondary">{{ user.email }}</p>
                <div class="flex flex-wrap gap-1">
                  <Badge v-for="project in user.projects || []" :key="project.id" tone="success">
                    {{ project.displayName }}
                  </Badge>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Badge :tone="user.role === 'ADMIN' ? 'warning' : 'primary'">{{ user.role }}</Badge>
                <Button
                  variant="danger"
                  @click.stop="deleteUser(user)"
                >
                  Delete
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Modal :open="isModalOpen" :title="editingUserId ? 'Edit User' : 'Add User'" @close="closeModal">
          <form class="space-y-3" @submit.prevent="saveUser">
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Username</label>
              <input
                v-model="form.username"
                type="text"
                required
                class="w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Email</label>
              <input
                v-model="form.email"
                type="email"
                required
                class="w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">
                {{ editingUserId ? 'Password (leave blank to keep)' : 'Password' }}
              </label>
              <input
                v-model="form.password"
                type="password"
                :required="!editingUserId"
                class="w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label class="mb-1 block text-xs text-text-secondary">Role</label>
              <select v-model="form.role" class="w-full rounded-lg border border-dark-border bg-dark-bg px-3 py-2 text-sm">
                <option value="ADMIN">Admin</option>
                <option value="INTERN">Intern</option>
              </select>
            </div>
            <div>
              <p class="mb-1 text-xs text-text-secondary">Projects</p>
              <div class="max-h-40 space-y-2 overflow-auto rounded-lg border border-dark-border p-2">
                <label
                  v-for="project in projects"
                  :key="project.id"
                  class="flex items-center gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    :checked="form.projectIds.includes(project.id)"
                    @change="toggleProject(project.id)"
                  />
                  {{ project.displayName }}
                </label>
              </div>
            </div>
            <div class="flex justify-end gap-2 pt-2">
              <Button variant="secondary" :disabled="saving" @click="closeModal">Cancel</Button>
              <Button type="submit" :disabled="saving">
                {{ saving ? 'Saving...' : 'Save' }}
              </Button>
            </div>
          </form>
        </Modal>
      </main>
    </div>
  </div>
</template>
