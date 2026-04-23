<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';

// Unified Org Members view. Replaces the member-management halves of
// /team (UserManagementView) and /org-dashboard (OrgDashboardView).
// Old routes redirect here; old view files stay on disk until a cleanup pass.

interface Member {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  role: string;
  created_at?: string;
}

interface Invitation {
  id: number;
  email: string;
  role: string;
  status: string;
  expires_at?: string;
  created_at?: string;
}

const auth = useAuthStore();

const members = ref<Member[]>([]);
const invitations = ref<Invitation[]>([]);
const loading = ref(true);
const error = ref('');
const searchQuery = ref('');
const activeTab = ref<'all' | 'admin' | 'teacher' | 'developer'>('all');

// Invite modal state
const showInviteModal = ref(false);
const inviteEmail = ref('');
const inviteRole = ref<'developer' | 'teacher' | 'viewer'>('developer');
const inviteLoading = ref(false);
const inviteResult = ref<{ success: boolean; message: string } | null>(null);

// ── Permissions ────────────────────────────────────────────────────
// Admin: can invite teachers + students
// Teacher: can invite students only
const canInviteTeacher = computed(() => auth.isSchoolAdmin || auth.isSuperuser);
const canInviteStudent = computed(
  () => auth.isSchoolAdmin || auth.isTeacher || auth.isSuperuser,
);
const canInviteAny = computed(
  () => canInviteTeacher.value || canInviteStudent.value,
);

// Pending-by-email for quick lookup (members list doesn't include invite status)
const pendingInviteEmails = computed(() => {
  return new Set(
    invitations.value
      .filter((i) => i.status === 'pending')
      .map((i) => i.email.toLowerCase()),
  );
});

// Build the tab-filtered + search-filtered unified list.
// We show members AND pending-invite emails as rows, so teachers can see
// "invited, not yet joined" people.
interface Row {
  id: string; // stable composite id
  kind: 'member' | 'invite';
  name: string;
  email: string;
  role: string;
  status: 'active' | 'pending';
  joined: string;
  rawMember?: Member;
  rawInvite?: Invitation;
}

const allRows = computed<Row[]>(() => {
  const memberRows: Row[] = members.value.map((m) => ({
    id: `m:${m.id}`,
    kind: 'member',
    name:
      [m.first_name, m.last_name].filter(Boolean).join(' ').trim() ||
      m.username ||
      m.email,
    email: m.email,
    role: m.role,
    status: 'active',
    joined: m.created_at
      ? new Date(m.created_at).toLocaleDateString()
      : '—',
    rawMember: m,
  }));

  const memberEmails = new Set(
    members.value.map((m) => m.email.toLowerCase()),
  );
  const inviteRows: Row[] = invitations.value
    .filter(
      (i) =>
        i.status === 'pending' &&
        !memberEmails.has(i.email.toLowerCase()),
    )
    .map((i) => ({
      id: `i:${i.id}`,
      kind: 'invite',
      name: i.email,
      email: i.email,
      role: i.role,
      status: 'pending',
      joined: i.created_at
        ? new Date(i.created_at).toLocaleDateString()
        : '—',
      rawInvite: i,
    }));

  return [...memberRows, ...inviteRows];
});

const filteredRows = computed(() => {
  let rows = allRows.value;
  if (activeTab.value !== 'all') {
    rows = rows.filter((r) => r.role === activeTab.value);
  }
  const q = searchQuery.value.trim().toLowerCase();
  if (q) {
    rows = rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.email.toLowerCase().includes(q),
    );
  }
  return rows;
});

const counts = computed(() => {
  const tally = { all: 0, admin: 0, teacher: 0, developer: 0 };
  for (const r of allRows.value) {
    tally.all += 1;
    if (r.role === 'admin') tally.admin += 1;
    else if (r.role === 'teacher') tally.teacher += 1;
    else if (r.role === 'developer') tally.developer += 1;
  }
  return tally;
});

async function loadData() {
  loading.value = true;
  error.value = '';
  try {
    const [membersRes, invRes] = await Promise.all([
      api.org.members(),
      api.org.invitations(),
    ]);
    members.value = Array.isArray(membersRes.data) ? membersRes.data : [];
    invitations.value = Array.isArray(invRes.data) ? invRes.data : [];
  } catch (e: any) {
    error.value =
      e?.response?.data?.error ||
      e?.response?.data?.detail ||
      'Failed to load organization members.';
  } finally {
    loading.value = false;
  }
}

function openInviteModal(defaultRole: 'developer' | 'teacher' = 'developer') {
  // Guard: don't open with a role the user can't invite.
  if (defaultRole === 'teacher' && !canInviteTeacher.value) {
    defaultRole = 'developer';
  }
  inviteEmail.value = '';
  inviteRole.value = defaultRole;
  inviteResult.value = null;
  showInviteModal.value = true;
}

function closeInviteModal() {
  showInviteModal.value = false;
  inviteResult.value = null;
}

async function submitInvite() {
  const email = inviteEmail.value.trim();
  if (!email) return;
  inviteLoading.value = true;
  inviteResult.value = null;
  try {
    await api.org.invite({ email, role: inviteRole.value });
    inviteResult.value = {
      success: true,
      message: `Invitation sent to ${email}.`,
    };
    inviteEmail.value = '';
    // Refresh invitations list
    const { data } = await api.org.invitations();
    invitations.value = Array.isArray(data) ? data : [];
  } catch (e: any) {
    const data = e?.response?.data;
    let msg = 'Failed to send invitation.';
    if (data) {
      if (typeof data === 'string') msg = data;
      else if (data.error) msg = data.error;
      else if (data.detail) msg = data.detail;
      else if (data.email) {
        msg = Array.isArray(data.email) ? data.email.join(', ') : data.email;
      } else if (data.role) {
        msg = Array.isArray(data.role) ? data.role.join(', ') : data.role;
      }
    }
    inviteResult.value = { success: false, message: msg };
  } finally {
    inviteLoading.value = false;
  }
}

function roleBadgeClass(role: string) {
  if (role === 'admin') return 'bg-primary/10 text-primary border-primary/20';
  if (role === 'teacher')
    return 'bg-secondary/10 text-secondary border-secondary/20';
  if (role === 'developer')
    return 'bg-tertiary/10 text-tertiary border-tertiary/20';
  return 'bg-on-surface-variant/10 text-on-surface-variant border-outline-variant/20';
}

function roleLabel(role: string) {
  if (role === 'developer') return 'Student';
  if (role === 'admin') return 'Admin';
  if (role === 'teacher') return 'Teacher';
  return role;
}

onMounted(loadData);
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <div class="flex flex-wrap gap-4 justify-between items-end mb-8">
          <div>
            <h1 class="text-4xl font-extrabold text-on-surface tracking-tight">
              Organization Members
            </h1>
            <p class="text-on-surface-variant mt-2 max-w-xl">
              Everyone in your organization — admins, teachers, and students —
              in one place. Invite new members below.
            </p>
          </div>
          <div v-if="canInviteAny" class="flex gap-2">
            <button
              v-if="canInviteTeacher"
              @click="openInviteModal('teacher')"
              class="bg-surface-container-highest text-on-surface px-5 py-2.5 rounded-lg font-bold flex items-center gap-2 hover:bg-surface-container-high transition-colors active:scale-95"
            >
              <span class="material-symbols-outlined text-sm">person_add</span>
              Invite Teacher
            </button>
            <button
              v-if="canInviteStudent"
              @click="openInviteModal('developer')"
              class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
            >
              <span class="material-symbols-outlined text-sm">person_add</span>
              Invite Student
            </button>
          </div>
        </div>

        <!-- Tabs + Search -->
        <div class="flex flex-wrap items-center gap-3 mb-6">
          <div class="flex gap-1 bg-surface-container rounded-lg p-1 border border-outline-variant/10">
            <button
              v-for="tab in [
                { key: 'all', label: 'All' },
                { key: 'teacher', label: 'Teachers' },
                { key: 'developer', label: 'Students' },
                { key: 'admin', label: 'Admins' },
              ]"
              :key="tab.key"
              @click="activeTab = tab.key as any"
              :class="[
                'px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider transition-colors flex items-center gap-2',
                activeTab === tab.key
                  ? 'bg-primary/15 text-primary'
                  : 'text-on-surface-variant hover:text-on-surface',
              ]"
            >
              {{ tab.label }}
              <span class="text-[10px] opacity-70">
                {{ counts[tab.key as keyof typeof counts] }}
              </span>
            </button>
          </div>

          <div class="relative ml-auto">
            <span
              class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-sm pointer-events-none"
              >search</span
            >
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search by name or email..."
              class="w-64 bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-2.5 pl-9 pr-4 text-sm"
            />
          </div>
        </div>

        <p v-if="error" class="text-sm text-error mb-4">{{ error }}</p>

        <!-- Members table -->
        <div class="bg-surface-container-low rounded-xl overflow-hidden border border-outline-variant/10">
          <div v-if="loading" class="p-12 text-center text-outline">
            <span class="material-symbols-outlined animate-spin text-2xl text-primary"
              >progress_activity</span
            >
            <p class="mt-2 text-sm">Loading members...</p>
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr
                  class="bg-surface-container text-outline text-xs uppercase tracking-widest font-semibold"
                >
                  <th class="px-6 py-4">Member</th>
                  <th class="px-6 py-4">Role</th>
                  <th class="px-6 py-4">Status</th>
                  <th class="px-6 py-4">Joined</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/5">
                <tr
                  v-for="row in filteredRows"
                  :key="row.id"
                  class="hover:bg-surface-container-high/40 transition-colors"
                >
                  <td class="px-6 py-5">
                    <div class="flex items-center gap-4">
                      <div
                        class="h-10 w-10 rounded-lg bg-secondary-container flex items-center justify-center text-sm font-bold text-primary"
                      >
                        {{ row.name.slice(0, 2).toUpperCase() }}
                      </div>
                      <div>
                        <div class="text-sm font-bold text-on-surface">
                          {{ row.name }}
                        </div>
                        <div class="text-xs text-on-surface-variant">
                          {{ row.email }}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="px-6 py-5">
                    <span
                      :class="[
                        'px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border',
                        roleBadgeClass(row.role),
                      ]"
                    >
                      {{ roleLabel(row.role) }}
                    </span>
                  </td>
                  <td class="px-6 py-5">
                    <span
                      v-if="row.status === 'active'"
                      class="inline-flex items-center gap-1.5 text-xs text-primary"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-primary"></span>
                      Active
                    </span>
                    <span
                      v-else
                      class="inline-flex items-center gap-1.5 text-xs text-tertiary"
                    >
                      <span class="h-1.5 w-1.5 rounded-full bg-tertiary"></span>
                      Pending invite
                    </span>
                  </td>
                  <td class="px-6 py-5 text-xs text-on-surface-variant">
                    {{ row.joined }}
                  </td>
                </tr>
                <tr v-if="!filteredRows.length">
                  <td
                    colspan="4"
                    class="px-6 py-12 text-center text-outline text-sm"
                  >
                    <span class="material-symbols-outlined text-3xl mb-2 block opacity-40"
                      >group_off</span
                    >
                    {{
                      searchQuery
                        ? 'No members match your search.'
                        : 'No members in this tab yet.'
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Invite Modal -->
    <div
      v-if="showInviteModal"
      class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-background/80 backdrop-blur-sm"
    >
      <div
        class="glass-panel w-full max-w-lg rounded-xl overflow-hidden shadow-2xl"
      >
        <div
          class="px-8 py-6 border-b border-outline-variant/10 flex justify-between items-center"
        >
          <h3 class="text-xl font-bold text-on-surface">Invite a Member</h3>
          <button
            class="text-outline hover:text-on-surface transition-colors"
            @click="closeInviteModal"
          >
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <form class="p-8 space-y-5" @submit.prevent="submitInvite">
          <div class="space-y-1.5">
            <label
              class="text-xs font-bold uppercase tracking-widest text-outline"
              >Email Address</label
            >
            <input
              v-model="inviteEmail"
              type="email"
              required
              autofocus
              placeholder="new.member@school.com"
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 py-3 px-4"
            />
          </div>

          <div class="space-y-1.5">
            <label
              class="text-xs font-bold uppercase tracking-widest text-outline"
              >Role</label
            >
            <select
              v-model="inviteRole"
              class="w-full bg-surface-container-lowest border-none rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4"
            >
              <option v-if="canInviteStudent" value="developer">Student</option>
              <option v-if="canInviteTeacher" value="teacher">Teacher</option>
              <option v-if="canInviteStudent" value="viewer">Viewer</option>
            </select>
            <p class="text-[11px] text-outline mt-1">
              <template v-if="inviteRole === 'teacher'">
                Teachers can grade students and manage courses.
              </template>
              <template v-else-if="inviteRole === 'viewer'">
                Viewers have read-only access.
              </template>
              <template v-else>
                Students submit work and receive feedback.
              </template>
            </p>
          </div>

          <div
            v-if="inviteResult"
            class="p-3 rounded-lg"
            :class="
              inviteResult.success
                ? 'bg-primary/10 border border-primary/20'
                : 'bg-error/10 border border-error/20'
            "
          >
            <p
              class="text-sm"
              :class="inviteResult.success ? 'text-primary' : 'text-error'"
            >
              {{ inviteResult.message }}
            </p>
          </div>

          <div class="flex gap-4 pt-2">
            <button
              type="button"
              @click="closeInviteModal"
              class="flex-1 bg-surface-container-highest text-on-surface font-bold py-3 rounded-lg hover:bg-outline-variant transition-colors"
            >
              Close
            </button>
            <button
              type="submit"
              :disabled="inviteLoading || !inviteEmail.trim()"
              class="flex-1 primary-gradient text-on-primary font-bold py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 shadow-lg shadow-primary/20 disabled:opacity-50"
            >
              <span
                v-if="inviteLoading"
                class="material-symbols-outlined animate-spin text-sm mr-1 align-middle"
                >progress_activity</span
              >
              {{ inviteLoading ? 'Sending...' : 'Send Invite' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppShell>
</template>
