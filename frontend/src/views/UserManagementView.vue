<script setup lang="ts">
import { onMounted, ref } from 'vue';
import Header from '@/components/layout/Header.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import Card from '@/components/common/Card.vue';
import Badge from '@/components/common/Badge.vue';
import Button from '@/components/common/Button.vue';
import Dropdown from '@/components/common/Dropdown.vue';
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
  <div class="app-shell flex">
    <Sidebar />
    <div class="flex min-h-screen flex-1 flex-col">
      <Header />
      <main class="space-y-6 p-6">
        <div class="flex items-center justify-between">
          <h2 class="text-2xl font-semibold">Team Management</h2>
          <Button @click="openCreateModal">Add User</Button>
        </div>
        <p v-if="errorMessage" class="text-sm text-error">{{ errorMessage }}</p>
        <Card>
          <div v-if="loading" class="text-sm text-text-secondary">Loading users...</div>
          <div v-else class="overflow-x-auto">
            <div class="mb-2 grid min-w-[900px] grid-cols-[56px_1fr_1.2fr_120px_1.4fr_130px] px-3 py-2 text-xs font-medium uppercase tracking-wide text-text-secondary">
              <span>Avatar</span>
              <span>Username</span>
              <span>Email</span>
              <span>Role</span>
              <span>Projects</span>
              <span class="text-right">Actions</span>
            </div>
            <div
              v-for="user in users"
              :key="user.id"
              class="mb-2 grid min-w-[900px] cursor-pointer grid-cols-[56px_1fr_1.2fr_120px_1.4fr_130px] items-center rounded-lg border border-border bg-bg-darkest px-3 py-3 transition odd:bg-bg-card hover:border-primary/60"
              @click="openEditModal(user)"
            >
              <div class="flex h-9 w-9 items-center justify-center rounded-full bg-bg-elevated text-xs font-semibold">
                {{ user.username.slice(0, 2).toUpperCase() }}
              </div>
              <p class="text-sm font-semibold">{{ user.username }}</p>
              <p class="text-sm text-text-secondary">{{ user.email }}</p>
              <Badge :tone="user.role === 'ADMIN' ? 'primary' : 'muted'">{{ user.role }}</Badge>
              <div class="flex flex-wrap gap-1">
                <Badge v-for="project in user.projects || []" :key="project.id" tone="success">{{ project.displayName }}</Badge>
              </div>
              <div class="flex items-center justify-end gap-2">
                <Button variant="outlined" @click.stop="openEditModal(user)">Edit</Button>
                <Button
                  variant="danger"
                  @click.stop="deleteUser(user)"
                >
                  Del
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Modal :open="isModalOpen" :title="editingUserId ? 'Edit User' : 'Add User'" @close="closeModal">
          <form class="space-y-3" @submit.prevent="saveUser">
            <div>
              <label class="field-label">Username</label>
              <input
                v-model="form.username"
                type="text"
                required
                class="h-10 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm"
              />
            </div>
            <div>
              <label class="field-label">Email</label>
              <input
                v-model="form.email"
                type="email"
                required
                class="h-10 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm"
              />
            </div>
            <div>
              <label class="field-label">
                {{ editingUserId ? 'Password (leave blank to keep)' : 'Password' }}
              </label>
              <input
                v-model="form.password"
                type="password"
                :required="!editingUserId"
                class="h-10 w-full rounded-lg border border-border bg-bg-elevated px-3 text-sm"
              />
            </div>
            <div>
              <label class="field-label">Role</label>
              <Dropdown v-model="form.role">
                <option value="ADMIN">Admin</option>
                <option value="INTERN">Intern</option>
              </Dropdown>
            </div>
            <div>
              <p class="field-label">Projects</p>
              <div class="max-h-40 space-y-2 overflow-auto rounded-lg border border-border bg-bg-darkest p-2">
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
