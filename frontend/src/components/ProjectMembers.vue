<template>
  <div class="bg-gray-800 rounded-lg p-6">
    <div class="flex justify-between items-center mb-6">
      <h3 class="text-lg font-medium text-white">Team Members</h3>
      <button
        v-if="canManage"
        @click="showInviteModal = true"
        class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm"
      >
        Invite Member
      </button>
    </div>
    
    <!-- Members List -->
    <div v-if="loading" class="text-gray-400 text-center py-8">Loading...</div>
    
    <div v-else-if="members.length === 0" class="text-gray-400 text-center py-8">
      No members yet. Invite someone to get started.
    </div>
    
    <div v-else class="space-y-3">
      <div
        v-for="member in members"
        :key="member.id"
        class="flex items-center justify-between p-3 bg-gray-700 rounded-lg"
      >
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 bg-indigo-600 rounded-full flex items-center justify-center text-white font-medium">
            {{ getInitials(member.user) }}
          </div>
          <div>
            <p class="text-white font-medium">{{ member.user.display_name || member.user.email }}</p>
            <p class="text-gray-400 text-sm">{{ member.user.email }}</p>
          </div>
        </div>
        
        <div class="flex items-center space-x-3">
          <!-- Role Badge -->
          <span :class="getRoleBadgeClass(member.role)" class="px-2 py-1 rounded text-xs font-medium">
            {{ member.role }}
          </span>
          
          <!-- Role Selector (for managers) -->
          <select
            v-if="canManage && member.user.id !== currentUserId"
            v-model="member.role"
            @change="updateRole(member)"
            class="bg-gray-600 text-white text-sm rounded px-2 py-1 border-none"
          >
            <option value="owner">Owner</option>
            <option value="maintainer">Maintainer</option>
            <option value="developer">Developer</option>
            <option value="viewer">Viewer</option>
          </select>
          
          <!-- Remove Button -->
          <button
            v-if="canManage && member.user.id !== currentUserId"
            @click="removeMember(member)"
            class="text-red-400 hover:text-red-300 p-1"
            title="Remove member"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Invite Modal -->
    <div v-if="showInviteModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-gray-800 rounded-lg p-6 w-full max-w-md">
        <h4 class="text-lg font-medium text-white mb-4">Invite Team Member</h4>
        
        <form @submit.prevent="inviteMember">
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Email address</label>
              <input
                v-model="inviteForm.email"
                type="email"
                required
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400"
                placeholder="colleague@example.com"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Role</label>
              <select
                v-model="inviteForm.role"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white"
              >
                <option value="developer">Developer</option>
                <option value="maintainer">Maintainer</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
          </div>
          
          <div v-if="inviteError" class="mt-4 text-red-400 text-sm">
            {{ inviteError }}
          </div>
          
          <div class="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              @click="showInviteModal = false"
              class="px-4 py-2 text-gray-300 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="inviting"
              class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {{ inviting ? 'Inviting...' : 'Send Invite' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useApi } from '@/composables/useApi'

const props = defineProps<{
  projectId: number
}>()

const authStore = useAuthStore()
const api = useApi()

const members = ref<any[]>([])
const loading = ref(true)
const showInviteModal = ref(false)
const inviting = ref(false)
const inviteError = ref('')

const inviteForm = reactive({
  email: '',
  role: 'developer'
})

const currentUserId = computed(() => authStore.user?.id)

const canManage = computed(() => {
  // Check if current user is owner or maintainer
  const currentMember = members.value.find(m => m.user.id === currentUserId.value)
  return currentMember && ['owner', 'maintainer'].includes(currentMember.role)
})

function getInitials(user: any): string {
  if (user.first_name && user.last_name) {
    return `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
  }
  return user.email[0].toUpperCase()
}

function getRoleBadgeClass(role: string): string {
  const classes: Record<string, string> = {
    owner: 'bg-yellow-600 text-yellow-100',
    maintainer: 'bg-blue-600 text-blue-100',
    developer: 'bg-green-600 text-green-100',
    viewer: 'bg-gray-600 text-gray-100'
  }
  return classes[role] || classes.viewer
}

async function loadMembers() {
  loading.value = true
  try {
    const data = await api.getProjectMembers(props.projectId)
    members.value = data
  } catch (err) {
    console.error('Failed to load members:', err)
  } finally {
    loading.value = false
  }
}

async function inviteMember() {
  inviteError.value = ''
  inviting.value = true
  
  try {
    const newMember = await api.inviteProjectMember(props.projectId, inviteForm.email, inviteForm.role)
    members.value.push(newMember)
    showInviteModal.value = false
    inviteForm.email = ''
    inviteForm.role = 'developer'
  } catch (err: any) {
    inviteError.value = err.message || 'Failed to invite member'
  } finally {
    inviting.value = false
  }
}

async function updateRole(member: any) {
  try {
    await api.updateProjectMemberRole(props.projectId, member.user.id, member.role)
  } catch (err) {
    console.error('Failed to update role:', err)
    // Reload to get correct state
    await loadMembers()
  }
}

async function removeMember(member: any) {
  if (!confirm(`Remove ${member.user.email} from the project?`)) return
  
  try {
    await api.removeProjectMember(props.projectId, member.user.id)
    members.value = members.value.filter(m => m.id !== member.id)
  } catch (err) {
    console.error('Failed to remove member:', err)
  }
}

onMounted(() => {
  loadMembers()
})
</script>
