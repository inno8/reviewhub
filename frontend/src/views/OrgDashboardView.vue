<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';
import AppShell from '@/components/layout/AppShell.vue';

const router = useRouter();
const auth = useAuthStore();

interface Student {
  id: number;
  name: string;
  email: string;
  level: string;
  overall_score: number;
  trend: string;
  weakest_skill: string | null;
  last_active: string | null;
}

interface HeatmapEntry {
  category: string;
  avg_score: number;
  student_count: number;
}

const loading = ref(true);
const error = ref('');
const orgName = ref('');
const studentCount = ref(0);
const students = ref<Student[]>([]);
const heatmap = ref<HeatmapEntry[]>([]);
const searchQuery = ref('');

// Invite form
const showInviteForm = ref(false);
const inviteEmail = ref('');
const inviteRole = ref('developer');
const inviteLoading = ref(false);
const inviteResult = ref<{ success: boolean; message: string } | null>(null);

// Invitations list
const invitations = ref<any[]>([]);

const filteredStudents = computed(() => {
  if (!searchQuery.value.trim()) return students.value;
  const q = searchQuery.value.toLowerCase();
  return students.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q)
  );
});

function trendIcon(trend: string) {
  if (trend === 'improving') return 'trending_up';
  if (trend === 'declining') return 'trending_down';
  return 'trending_flat';
}

function trendColor(trend: string) {
  if (trend === 'improving') return 'text-primary';
  if (trend === 'declining') return 'text-error';
  return 'text-on-surface-variant';
}

function levelBadge(level: string) {
  const map: Record<string, { label: string; color: string }> = {
    beginner: { label: 'Beginner', color: 'bg-error/10 text-error border-error/20' },
    developing: { label: 'Developing', color: 'bg-tertiary/10 text-tertiary border-tertiary/20' },
    proficient: { label: 'Proficient', color: 'bg-primary/10 text-primary border-primary/20' },
    advanced: { label: 'Advanced', color: 'bg-primary/15 text-primary border-primary/30' },
    new: { label: 'New', color: 'bg-on-surface-variant/10 text-on-surface-variant border-outline-variant/20' },
  };
  return map[level] || map.new;
}

function heatmapColor(score: number): string {
  if (score >= 80) return 'bg-primary/20 text-primary';
  if (score >= 60) return 'bg-primary/10 text-primary';
  if (score >= 40) return 'bg-tertiary/10 text-tertiary';
  return 'bg-error/10 text-error';
}

async function loadDashboard() {
  loading.value = true;
  error.value = '';
  try {
    const [dashRes, invRes] = await Promise.all([
      api.org.dashboard(),
      api.org.invitations(),
    ]);
    const d = dashRes.data;
    orgName.value = d.org_name;
    studentCount.value = d.student_count;
    students.value = d.students;
    heatmap.value = d.heatmap;
    invitations.value = Array.isArray(invRes.data) ? invRes.data : [];
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Failed to load dashboard.';
  } finally {
    loading.value = false;
  }
}

async function sendInvite() {
  if (!inviteEmail.value.trim()) return;
  inviteLoading.value = true;
  inviteResult.value = null;
  try {
    await api.org.invite({ email: inviteEmail.value.trim(), role: inviteRole.value });
    inviteResult.value = { success: true, message: `Invitation sent to ${inviteEmail.value}` };
    inviteEmail.value = '';
    // Refresh invitations
    const { data } = await api.org.invitations();
    invitations.value = Array.isArray(data) ? data : [];
  } catch (e: any) {
    const msg = e?.response?.data?.email || e?.response?.data?.error || 'Failed to send invitation.';
    inviteResult.value = { success: false, message: msg };
  } finally {
    inviteLoading.value = false;
  }
}

function goToStudent(id: number) {
  router.push(`/org-dashboard/students/${id}`);
}

onMounted(loadDashboard);
</script>

<template>
  <AppShell>
  <div class="space-y-6 p-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-extrabold text-on-surface tracking-tight">{{ orgName || 'Organization' }} Dashboard</h1>
        <p class="text-sm text-on-surface-variant mt-1">{{ studentCount }} student{{ studentCount !== 1 ? 's' : '' }} enrolled</p>
      </div>
      <button @click="showInviteForm = !showInviteForm"
        class="primary-gradient text-on-primary font-bold py-2.5 px-5 rounded-lg flex items-center gap-2 active:scale-[0.98] transition-transform">
        <span class="material-symbols-outlined text-sm">person_add</span>
        Invite Student
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <span class="material-symbols-outlined text-primary text-3xl animate-spin">progress_activity</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="glass-panel rounded-xl p-8 text-center">
      <span class="material-symbols-outlined text-error text-4xl mb-3">error</span>
      <p class="text-on-surface-variant">{{ error }}</p>
    </div>

    <template v-else>
      <!-- Invite form (collapsible) -->
      <div v-if="showInviteForm" class="glass-panel rounded-xl p-6">
        <h2 class="text-sm font-bold text-on-surface mb-4">Invite a Student</h2>
        <form @submit.prevent="sendInvite" class="flex flex-wrap gap-3 items-end">
          <div class="flex-1 min-w-[200px]">
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Email</label>
            <input v-model="inviteEmail" type="email" placeholder="new.user@school.com" required
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-2.5 px-4 focus:ring-1 focus:ring-primary/50" />
          </div>
          <div>
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">Role</label>
            <select v-model="inviteRole"
              class="bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface text-sm py-2.5 px-4">
              <option value="developer">Student</option>
              <option value="viewer">Viewer</option>
              <!-- Only school admins can invite teachers; see InviteStudentView permission ladder -->
              <option v-if="auth.isSchoolAdmin" value="teacher">Teacher</option>
            </select>
          </div>
          <button type="submit" :disabled="inviteLoading"
            class="primary-gradient text-on-primary font-bold py-2.5 px-5 rounded-lg disabled:opacity-50 flex items-center gap-2">
            <span v-if="inviteLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            Send Invite
          </button>
        </form>
        <div v-if="inviteResult" class="mt-3 p-3 rounded-lg"
          :class="inviteResult.success ? 'bg-primary/10 border border-primary/20' : 'bg-error/10 border border-error/20'">
          <p class="text-sm" :class="inviteResult.success ? 'text-primary' : 'text-error'">{{ inviteResult.message }}</p>
        </div>

        <!-- Pending invitations -->
        <div v-if="invitations.length" class="mt-4 pt-4 border-t border-outline-variant/10">
          <h3 class="text-xs font-bold uppercase tracking-widest text-outline mb-3">Pending Invitations</h3>
          <div class="space-y-2">
            <div v-for="inv in invitations" :key="inv.id"
              class="flex items-center justify-between p-3 bg-surface-container-lowest rounded-lg">
              <div>
                <span class="text-sm text-on-surface">{{ inv.email }}</span>
                <span class="text-xs text-on-surface-variant ml-2">{{ inv.role }}</span>
              </div>
              <span class="text-xs px-2 py-1 rounded-full border"
                :class="inv.status === 'pending' ? 'bg-tertiary/10 text-tertiary border-tertiary/20' : 'bg-primary/10 text-primary border-primary/20'">
                {{ inv.status }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Skill Heatmap -->
      <div v-if="heatmap.length" class="glass-panel rounded-xl p-6">
        <h2 class="text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
          <span class="material-symbols-outlined text-primary text-lg">grid_view</span>
          Class Skill Heatmap
        </h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div v-for="h in heatmap" :key="h.category"
            class="p-4 rounded-xl border border-outline-variant/10 text-center"
            :class="heatmapColor(h.avg_score)">
            <div class="text-2xl font-extrabold">{{ h.avg_score }}</div>
            <div class="text-xs font-bold mt-1 opacity-80">{{ h.category }}</div>
            <div class="text-[10px] mt-0.5 opacity-60">{{ h.student_count }} student{{ h.student_count !== 1 ? 's' : '' }}</div>
          </div>
        </div>
      </div>

      <!-- Student table -->
      <div class="glass-panel rounded-xl p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-bold text-on-surface flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-lg">group</span>
            Students
          </h2>
          <div class="relative">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-sm">search</span>
            <input v-model="searchQuery" type="text" placeholder="Search..."
              class="bg-surface-container-lowest border border-outline-variant/20 rounded-lg text-on-surface text-xs py-2 pl-9 pr-4 w-48 focus:ring-1 focus:ring-primary/50" />
          </div>
        </div>

        <div v-if="!filteredStudents.length" class="text-center py-8 text-on-surface-variant text-sm">
          {{ students.length ? 'No students match your search.' : 'No students yet. Invite some above!' }}
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-widest text-outline border-b border-outline-variant/10">
                <th class="pb-3 pr-4">Student</th>
                <th class="pb-3 pr-4">Level</th>
                <th class="pb-3 pr-4">Score</th>
                <th class="pb-3 pr-4">Trend</th>
                <th class="pb-3 pr-4">Weakest Skill</th>
                <th class="pb-3">Last Active</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in filteredStudents" :key="s.id"
                @click="goToStudent(s.id)"
                class="border-b border-outline-variant/5 hover:bg-surface-container-highest/50 cursor-pointer transition-colors">
                <td class="py-3 pr-4">
                  <div>
                    <div class="font-bold text-on-surface">{{ s.name }}</div>
                    <div class="text-xs text-on-surface-variant">{{ s.email }}</div>
                  </div>
                </td>
                <td class="py-3 pr-4">
                  <span class="px-2.5 py-1 rounded-full text-xs font-bold border" :class="levelBadge(s.level).color">
                    {{ levelBadge(s.level).label }}
                  </span>
                </td>
                <td class="py-3 pr-4 font-bold text-on-surface">{{ s.overall_score }}</td>
                <td class="py-3 pr-4">
                  <span class="material-symbols-outlined text-lg" :class="trendColor(s.trend)">{{ trendIcon(s.trend) }}</span>
                </td>
                <td class="py-3 pr-4 text-on-surface-variant">{{ s.weakest_skill || '-' }}</td>
                <td class="py-3 text-on-surface-variant">{{ s.last_active || 'Never' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
  </AppShell>
</template>
