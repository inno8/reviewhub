<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/services/api';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const notifications = ref<any[]>([]);
const showNotifications = ref(false);
const loading = ref(false);

const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.read).length;
});

async function fetchNotifications() {
  try {
    loading.value = true;
    const response = await api.get('/notifications/?limit=10');
    notifications.value = response.data.results || response.data;
  } catch (error) {
    console.error('Failed to fetch notifications:', error);
  } finally {
    loading.value = false;
  }
}

async function markAsRead(notification: any) {
  try {
    await api.patch(`/notifications/${notification.id}/read/`);
    notification.read = true;
    
    // Navigate based on notification type
    if (notification.data?.finding_id) {
      router.push(`/findings/${notification.data.finding_id}`);
    } else if (notification.data?.skill_id) {
      router.push('/skills');
    }
    
    showNotifications.value = false;
  } catch (error) {
    console.error('Failed to mark notification as read:', error);
  }
}

async function markAllRead() {
  try {
    await api.post('/notifications/mark-all-read/');
    notifications.value.forEach(n => n.read = true);
  } catch (error) {
    console.error('Failed to mark all as read:', error);
  }
}

function toggleNotifications() {
  showNotifications.value = !showNotifications.value;
  if (showNotifications.value && notifications.value.length === 0) {
    fetchNotifications();
  }
}

function viewAllNotifications() {
  router.push('/notifications');
  showNotifications.value = false;
}

function formatTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function getNotificationIcon(type: string) {
  const icons: Record<string, string> = {
    new_finding: 'bug_report',
    skill_improvement: 'trending_up',
    weekly_summary: 'summarize',
    team_update: 'group'
  };
  return icons[type] || 'notifications';
}

function logout() {
  auth.logout();
  router.push('/login');
}

const navItems = [
  { name: 'Dashboard', path: '/' },
  { name: 'Projects', path: '/projects' },
];

function isActive(path: string) {
  return route.path === path;
}

// Fetch notifications on mount
onMounted(() => {
  fetchNotifications();
  
  // Poll for new notifications every 30 seconds
  setInterval(fetchNotifications, 30000);
});
</script>

<template>
  <header class="flex justify-between items-center w-full px-6 h-16 fixed top-0 z-50 bg-background">
    <div class="flex items-center gap-8">
      <!-- Logo -->
      <span class="text-xl font-bold bg-gradient-to-r from-primary to-primary-container bg-clip-text text-transparent tracking-tight">
        ReviewHub
      </span>

      <!-- Nav Links -->
      <nav class="hidden md:flex gap-6">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'py-1 text-sm transition-colors',
            isActive(item.path)
              ? 'text-primary font-semibold border-b-2 border-primary'
              : 'text-surface-container-highest hover:text-primary'
          ]"
        >
          {{ item.name }}
        </router-link>
      </nav>
    </div>

    <div class="flex items-center gap-4">
      <!-- Notifications -->
      <div class="relative">
        <button 
          @click="toggleNotifications"
          class="p-2 text-surface-container-highest hover:bg-surface-container transition-all duration-200 rounded-full active:scale-95 relative"
        >
          <span class="material-symbols-outlined">notifications</span>
          <span 
            v-if="unreadCount > 0" 
            class="absolute top-1 right-1 bg-error text-white text-xs rounded-full h-4 w-4 flex items-center justify-center font-bold"
          >
            {{ unreadCount > 9 ? '9+' : unreadCount }}
          </span>
        </button>

        <!-- Notifications Dropdown -->
        <div 
          v-if="showNotifications" 
          class="absolute right-0 top-full mt-2 w-96 bg-surface-container-low rounded-lg border border-outline-variant/20 shadow-xl max-h-96 overflow-hidden flex flex-col"
        >
          <div class="flex justify-between items-center px-4 py-3 border-b border-outline-variant/10">
            <h3 class="text-sm font-semibold text-on-surface">Notifications</h3>
            <button 
              v-if="unreadCount > 0"
              @click="markAllRead" 
              class="text-xs text-primary hover:underline"
            >
              Mark all read
            </button>
          </div>

          <div class="overflow-y-auto flex-1">
            <div v-if="loading" class="p-8 text-center">
              <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
            </div>

            <div v-else-if="notifications.length === 0" class="p-8 text-center text-on-surface-variant text-sm">
              No notifications yet
            </div>

            <button
              v-for="notification in notifications"
              :key="notification.id"
              @click="markAsRead(notification)"
              :class="[
                'w-full text-left px-4 py-3 border-b border-outline-variant/10 hover:bg-surface-container transition-colors flex gap-3',
                !notification.read && 'bg-primary/5'
              ]"
            >
              <span :class="['material-symbols-outlined text-lg', !notification.read ? 'text-primary' : 'text-on-surface-variant']">
                {{ getNotificationIcon(notification.type) }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-2 mb-1">
                  <p :class="['text-sm font-medium', !notification.read && 'text-primary']">
                    {{ notification.title }}
                  </p>
                  <span class="text-xs text-on-surface-variant whitespace-nowrap">
                    {{ formatTimestamp(notification.created_at) }}
                  </span>
                </div>
                <p class="text-xs text-on-surface-variant line-clamp-2">
                  {{ notification.message }}
                </p>
              </div>
            </button>
          </div>

          <div class="border-t border-outline-variant/10 p-2">
            <button 
              @click="viewAllNotifications"
              class="w-full text-center text-sm text-primary hover:bg-primary/5 py-2 rounded transition-colors"
            >
              View all notifications
            </button>
          </div>
        </div>
      </div>

      <!-- Settings -->
      <button class="p-2 text-surface-container-highest hover:bg-surface-container transition-all duration-200 rounded-full active:scale-95">
        <span class="material-symbols-outlined">settings</span>
      </button>

      <!-- User Avatar -->
      <div class="relative group">
        <div class="h-8 w-8 rounded-full bg-surface-container-highest overflow-hidden border border-outline-variant/20 cursor-pointer">
          <div class="w-full h-full flex items-center justify-center text-primary text-sm font-bold">
            {{ auth.user?.username?.charAt(0).toUpperCase() || 'U' }}
          </div>
        </div>

        <!-- Dropdown -->
        <div class="absolute right-0 top-full mt-2 w-48 bg-surface-container-low rounded-lg border border-outline-variant/20 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
          <div class="px-4 py-3 border-b border-outline-variant/10">
            <p class="text-sm font-medium text-on-surface">{{ auth.user?.username }}</p>
            <p class="text-xs text-on-surface-variant">{{ auth.user?.email }}</p>
          </div>
          <button
            @click="logout"
            class="w-full px-4 py-2 text-left text-sm text-error hover:bg-error/10 transition-colors flex items-center gap-2"
          >
            <span class="material-symbols-outlined text-sm">logout</span>
            Sign out
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
