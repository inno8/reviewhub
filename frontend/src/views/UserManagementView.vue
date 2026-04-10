<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';

interface Category {
  id: number;
  name: string;
  description: string;
  member_count: number;
}

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  categories?: { id: number; name: string }[];
}

const users = ref<User[]>([]);
const categories = ref<Category[]>([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref('');
const searchQuery = ref('');
const filterCategory = ref<number | null>(null);
const filterProject = ref<number | null>(null);

// User modal
const isUserModalOpen = ref(false);
const editingUserId = ref<number | null>(null);
const userForm = ref({ username: '', email: '', password: '', role: 'developer', categoryId: null as number | null });

// Category modal
const isCategoryModalOpen = ref(false);
const categoryForm = ref({ name: '', description: '' });
const categoryError = ref('');
const categorySaving = ref(false);

function resetUserForm() {
  userForm.value = { username: '', email: '', password: '', role: 'developer', categoryId: null };
}

function openCreateUser() {
  editingUserId.value = null;
  resetUserForm();
  errorMessage.value = '';
  isUserModalOpen.value = true;
}

function openEditUser(user: User) {
  editingUserId.value = user.id;
  userForm.value = {
    username: user.username,
    email: user.email,
    password: '',
    role: user.role,
    categoryId: user.categories?.[0]?.id ?? null,
  };
  errorMessage.value = '';
  isUserModalOpen.value = true;
}

function openCategoryModal() {
  categoryForm.value = { name: '', description: '' };
  categoryError.value = '';
  isCategoryModalOpen.value = true;
}

const filteredUsers = computed(() => {
  let result = users.value;
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase();
    result = result.filter(
      u => u.username.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
    );
  }
  if (filterCategory.value) {
    result = result.filter(u => u.categories?.some(c => c.id === filterCategory.value));
  }
  return result;
});

async function fetchData() {
  loading.value = true;
  try {
    const [usersRes, catsRes] = await Promise.all([
      api.users.adminStats(),
      api.categories.list(),
    ]);
    users.value = usersRes.data;
    categories.value = catsRes.data.results || catsRes.data || [];
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function saveUser() {
  saving.value = true;
  errorMessage.value = '';
  try {
    const payload: any = {
      username: userForm.value.username,
      email: userForm.value.email,
      role: userForm.value.role,
    };
    if (userForm.value.password) payload.password = userForm.value.password;

    if (editingUserId.value) {
      await api.users.update(editingUserId.value, payload);
    } else {
      if (!userForm.value.password) {
        errorMessage.value = 'Password is required for new users.';
        saving.value = false;
        return;
      }
      await api.users.create(payload);
    }

    // If a category is selected, update category membership
    if (userForm.value.categoryId) {
      const cat = await api.categories.get(userForm.value.categoryId);
      const existingIds: number[] = (cat.data.members || []).map((m: any) => m.id);
      const userId = editingUserId.value || users.value.find(u => u.email === userForm.value.email)?.id;
      if (userId && !existingIds.includes(userId)) {
        await api.categories.update(userForm.value.categoryId, {
          member_ids: [...existingIds, userId],
        });
      }
    }

    await fetchData();
    isUserModalOpen.value = false;
  } catch (e: any) {
    const data = e?.response?.data;
    if (data && typeof data === 'object' && !data.error) {
      // DRF field errors: { field: ["message", ...], ... }
      const msgs = Object.entries(data)
        .map(([field, errs]: [string, any]) => `${field}: ${Array.isArray(errs) ? errs.join(', ') : errs}`)
        .join(' · ');
      errorMessage.value = msgs || 'Failed to save user.';
    } else {
      errorMessage.value = data?.error || data?.detail || 'Failed to save user.';
    }
  } finally {
    saving.value = false;
  }
}

async function deleteUser(user: User) {
  if (!confirm(`Delete user "${user.username}"?`)) return;
  try {
    await api.users.delete(user.id);
    await fetchData();
  } catch (e: any) {
    errorMessage.value = e?.response?.data?.error || 'Failed to delete user.';
  }
}

async function saveCategory() {
  categorySaving.value = true;
  categoryError.value = '';
  try {
    await api.categories.create({
      name: categoryForm.value.name,
      description: categoryForm.value.description,
    });
    const catsRes = await api.categories.list();
    categories.value = catsRes.data.results || catsRes.data || [];
    isCategoryModalOpen.value = false;
  } catch (e: any) {
    categoryError.value = e?.response?.data?.name?.[0] || 'Failed to create category.';
  } finally {
    categorySaving.value = false;
  }
}

async function deleteCategory(cat: Category) {
  if (!confirm(`Delete category "${cat.name}"?`)) return;
  try {
    await api.categories.delete(cat.id);
    await fetchData();
  } catch (e: any) {
    errorMessage.value = 'Failed to delete category.';
  }
}

onMounted(fetchData);
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <div class="flex justify-between items-end mb-10">
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">Team Management</h1>
            <p class="text-on-surface-variant mt-2 max-w-lg">
              Manage users, categories, and project assignments.
            </p>
          </div>
          <button
            class="primary-gradient text-on-primary px-6 py-3 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
            @click="openCreateUser"
          >
            <span class="material-symbols-outlined">person_add</span>
            Add User
          </button>
        </div>

        <!-- Filters -->
        <div class="flex flex-wrap items-center gap-3 mb-6">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search..."
            class="w-56 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 px-4 text-sm"
          />
          <select
            v-model="filterCategory"
            class="bg-surface-container-lowest border-none rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4"
          >
            <option :value="null">All Categories</option>
            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
          <select
            v-model="filterProject"
            class="bg-surface-container-lowest border-none rounded-lg text-on-surface text-sm focus:ring-1 focus:ring-primary/50 py-2.5 px-4"
          >
            <option :value="null">All Projects</option>
          </select>
        </div>

        <!-- Categories strip -->
        <div class="flex gap-2 flex-wrap mb-6">
          <div
            v-for="cat in categories"
            :key="cat.id"
            class="flex items-center gap-2 px-3 py-1.5 bg-surface-container rounded-full border border-outline-variant/20 text-xs"
          >
            <span class="text-on-surface font-semibold">{{ cat.name }}</span>
            <span class="text-outline">({{ cat.member_count }})</span>
            <button @click="deleteCategory(cat)" class="text-outline hover:text-error transition-colors ml-1">
              <span class="material-symbols-outlined text-[14px]">close</span>
            </button>
          </div>
          <button
            @click="openCategoryModal"
            class="flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-outline-variant/40 rounded-full text-xs text-outline hover:text-primary hover:border-primary/50 transition-colors"
          >
            <span class="material-symbols-outlined text-[14px]">add</span>
            New Category
          </button>
        </div>

        <p v-if="errorMessage" class="text-sm text-error mb-4">{{ errorMessage }}</p>

        <!-- Users Table -->
        <div class="bg-surface-container-low rounded-xl overflow-hidden border border-outline-variant/10">
          <div v-if="loading" class="p-8 text-center text-outline">Loading users...</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold">
                  <th class="px-6 py-4">User</th>
                  <th class="px-6 py-4">Role</th>
                  <th class="px-6 py-4">Category</th>
                  <th class="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/5">
                <tr
                  v-for="user in filteredUsers"
                  :key="user.id"
                  class="hover:bg-surface-container-high/40 transition-colors group"
                >
                  <td class="px-6 py-5">
                    <div class="flex items-center gap-4">
                      <div class="h-10 w-10 rounded-lg bg-secondary-container flex items-center justify-center text-sm font-bold text-primary">
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
                        user.role === 'admin'
                          ? 'bg-primary/10 text-primary border-primary/20'
                          : 'bg-tertiary/10 text-tertiary border-tertiary/20'
                      ]"
                    >
                      {{ user.role }}
                    </span>
                  </td>
                  <td class="px-6 py-5">
                    <div class="flex gap-1.5 flex-wrap">
                      <span
                        v-for="cat in user.categories || []"
                        :key="cat.id"
                        class="text-[11px] bg-surface-container-highest px-2 py-0.5 rounded text-on-surface-variant"
                      >
                        {{ cat.name }}
                      </span>
                      <span v-if="!user.categories?.length" class="text-[11px] text-outline">None</span>
                    </div>
                  </td>
                  <td class="px-6 py-5 text-right">
                    <div class="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        class="p-2 hover:bg-surface-container-highest rounded-lg text-on-surface-variant hover:text-primary transition-colors"
                        @click="openEditUser(user)"
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
                <tr v-if="!filteredUsers.length && !loading">
                  <td colspan="4" class="px-6 py-8 text-center text-outline text-sm">No users found.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- User Modal -->
    <div v-if="isUserModalOpen" class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm">
      <div class="glass-panel w-full max-w-lg rounded-xl overflow-hidden shadow-2xl">
        <div class="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center">
          <h3 class="text-xl font-bold text-on-surface">{{ editingUserId ? 'Edit User' : 'Add User' }}</h3>
          <button class="text-outline hover:text-on-surface transition-colors" @click="isUserModalOpen = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <form class="p-8 space-y-6" @submit.prevent="saveUser">
          <div class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Username</label>
                <input v-model="userForm.username" type="text" required placeholder="e.g. jdoe"
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
              </div>
              <div class="space-y-1.5">
                <label class="text-xs font-bold uppercase tracking-widest text-outline">Role</label>
                <select v-model="userForm.role"
                  class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4">
                  <option value="admin">Admin</option>
                  <option value="developer">Developer</option>
                  <option value="viewer">Viewer</option>
                </select>
              </div>
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">Email Address</label>
              <input v-model="userForm.email" type="email" required placeholder="john@company.com"
                class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">
                {{ editingUserId ? 'Password (leave blank to keep)' : 'Password' }}
              </label>
              <input v-model="userForm.password" type="password" :required="!editingUserId" placeholder="••••••••"
                class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
            </div>

            <!-- Category select with + button -->
            <div class="space-y-1.5">
              <label class="text-xs font-bold uppercase tracking-widest text-outline">Category</label>
              <div class="flex gap-2">
                <select v-model="userForm.categoryId"
                  class="flex-1 bg-surface-container-lowest border-none rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4">
                  <option :value="null">No category</option>
                  <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                </select>
                <button type="button" @click="openCategoryModal"
                  class="px-4 bg-surface-container-highest text-on-surface-variant rounded-lg hover:text-primary hover:bg-primary/10 transition-colors flex items-center justify-center"
                  title="Create new category">
                  <span class="material-symbols-outlined">add</span>
                </button>
              </div>
            </div>
          </div>

          <p v-if="errorMessage" class="text-sm text-error">{{ errorMessage }}</p>

          <div class="flex gap-4 pt-4">
            <button type="button" @click="isUserModalOpen = false"
              class="flex-1 bg-surface-container-highest text-on-surface font-bold py-3 rounded-lg hover:bg-outline-variant transition-colors">
              Cancel
            </button>
            <button type="submit" :disabled="saving"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 shadow-lg shadow-primary/20 disabled:opacity-50">
              {{ saving ? 'Saving...' : 'Save User' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Category Modal -->
    <div v-if="isCategoryModalOpen" class="fixed inset-0 z-[110] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm">
      <div class="glass-panel w-full max-w-sm rounded-xl overflow-hidden shadow-2xl">
        <div class="px-6 py-5 border-b border-outline-variant/10 flex justify-between items-center">
          <h3 class="text-lg font-bold text-on-surface">New Category</h3>
          <button class="text-outline hover:text-on-surface" @click="isCategoryModalOpen = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>
        <form class="p-6 space-y-4" @submit.prevent="saveCategory">
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Name</label>
            <input v-model="categoryForm.name" type="text" required placeholder="e.g. Frontend Team"
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-bold uppercase tracking-widest text-outline">Description</label>
            <input v-model="categoryForm.description" type="text" placeholder="Optional description"
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4" />
          </div>
          <p v-if="categoryError" class="text-sm text-error">{{ categoryError }}</p>
          <div class="flex gap-3 pt-2">
            <button type="button" @click="isCategoryModalOpen = false"
              class="flex-1 py-3 bg-surface-container-highest text-on-surface font-bold rounded-lg hover:bg-outline-variant transition-colors">
              Cancel
            </button>
            <button type="submit" :disabled="categorySaving"
              class="flex-1 py-3 primary-gradient text-on-primary font-bold rounded-lg disabled:opacity-50">
              {{ categorySaving ? 'Creating...' : 'Create' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppShell>
</template>
