<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';

const router = useRouter();

const notifications = ref<any[]>([]);
const loading = ref(false);
const filter = ref<string>('all');

const notificationTypes = [
  { value: 'all', label: 'All' },
  { value: 'new_finding', label: 'Findings' },
  { value: 'skill_improvement', label: 'Skills' },
  { value: 'weekly_summary', label: 'Summaries' },
  { value: 'team_update', label: 'Team' }
];

const filteredNotifications = computed(() => {
  if (filter.value === 'all') {
    return notifications.value;
  }
  return notifications.value.filter(n => n.type === filter.value);
});

const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.read).length;
});

async function fetchNotifications() {
  try {
    loading.value = true;
    const response = await api.notifications.list(100);
    notifications.value = response.data.results || response.data;
  } catch (error) {
    console.error('Failed to fetch notifications:', error);
  } finally {
    loading.value = false;
  }
}

async function markAsRead(notification: any) {
  try {
    await api.notifications.markAsRead(notification.id);
    notification.read = true;
    
    // Navigate based on notification type
    if (notification.type === 'weekly_summary') {
      router.push('/dashboard');
    } else if (notification.type === 'batch_summary') {
      router.push('/dashboard');
    } else if (notification.data?.finding_id) {
      router.push(`/findings/${notification.data.finding_id}`);
    } else if (notification.data?.skill_id || notification.type === 'skill_improvement') {
      router.push('/skills');
    } else if (notification.type === 'team_update') {
      router.push('/dashboard');
    }
  } catch (error) {
    console.error('Failed to mark notification as read:', error);
  }
}

async function markAllRead() {
  try {
    await api.notifications.markAllRead();
    notifications.value.forEach(n => n.read = true);
  } catch (error) {
    console.error('Failed to mark all as read:', error);
  }
}

function formatTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} minutes ago`;
  if (diffHours < 24) return `${diffHours} hours ago`;
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
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

function getNotificationColor(type: string) {
  const colors: Record<string, string> = {
    new_finding: 'text-error',
    skill_improvement: 'text-success',
    weekly_summary: 'text-info',
    team_update: 'text-primary'
  };
  return colors[type] || 'text-on-surface-variant';
}

onMounted(() => {
  fetchNotifications();
});
</script>

<template>
  <div class="max-w-4xl mx-auto p-6">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-on-surface mb-2">Notifications</h1>
      <p class="text-on-surface-variant">
        Stay updated on your code reviews and skill progress
      </p>
    </div>

    <!-- Filter Tabs -->
    <div class="flex gap-2 mb-6 border-b border-outline-variant/20 pb-2">
      <button
        v-for="type in notificationTypes"
        :key="type.value"
        @click="filter = type.value"
        :class="[
          'px-4 py-2 text-sm font-medium rounded-t-lg transition-colors',
          filter === type.value
            ? 'bg-primary text-on-primary'
            : 'text-on-surface-variant hover:bg-surface-container'
        ]"
      >
        {{ type.label }}
      </button>

      <div class="ml-auto flex items-center gap-2">
        <span class="text-sm text-on-surface-variant">
          {{ unreadCount }} unread
        </span>
        <button
          v-if="unreadCount > 0"
          @click="markAllRead"
          class="px-3 py-1 text-sm text-primary hover:bg-primary/10 rounded transition-colors"
        >
          Mark all read
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-12">
      <div class="inline-block animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="filteredNotifications.length === 0" 
      class="text-center py-12 bg-surface-container rounded-lg"
    >
      <span class="material-symbols-outlined text-6xl text-on-surface-variant mb-4">
        notifications_off
      </span>
      <p class="text-on-surface-variant">
        {{ filter === 'all' ? 'No notifications yet' : `No ${filter.replace('_', ' ')} notifications` }}
      </p>
    </div>

    <!-- Notifications List -->
    <div v-else class="space-y-2">
      <button
        v-for="notification in filteredNotifications"
        :key="notification.id"
        @click="markAsRead(notification)"
        :class="[
          'w-full text-left p-4 rounded-lg border transition-all hover:shadow-md',
          !notification.read
            ? 'bg-primary/5 border-primary/20'
            : 'bg-surface-container border-outline-variant/20'
        ]"
      >
        <div class="flex gap-4">
          <!-- Icon -->
          <div :class="['p-3 rounded-full bg-surface-container-highest', getNotificationColor(notification.type)]">
            <span class="material-symbols-outlined text-2xl">
              {{ getNotificationIcon(notification.type) }}
            </span>
          </div>

          <!-- Content -->
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-2 mb-1">
              <h3 :class="['text-base font-semibold', !notification.read && 'text-primary']">
                {{ notification.title }}
              </h3>
              <div class="flex items-center gap-2">
                <span class="text-xs text-on-surface-variant whitespace-nowrap">
                  {{ formatTimestamp(notification.created_at) }}
                </span>
                <span
                  v-if="!notification.read"
                  class="h-2 w-2 rounded-full bg-primary"
                ></span>
              </div>
            </div>

            <p class="text-sm text-on-surface-variant mb-2">
              {{ notification.message }}
            </p>

            <!-- Weekly Digest Details -->
            <div v-if="notification.type === 'weekly_summary' && notification.data" class="mt-2">
              <div class="flex flex-wrap gap-3 text-xs mb-2">
                <span class="px-2 py-1 bg-primary/10 text-primary rounded font-medium">
                  {{ notification.data.eval_count }} commits
                </span>
                <span class="px-2 py-1 bg-surface-container-highest rounded font-medium"
                  :class="notification.data.avg_score >= 70 ? 'text-success' : notification.data.avg_score >= 50 ? 'text-warning' : 'text-error'">
                  {{ notification.data.avg_score }}/100 avg
                </span>
                <span v-if="notification.data.total_findings" class="px-2 py-1 bg-error/10 text-error rounded font-medium">
                  {{ notification.data.total_findings }} issues
                </span>
                <span v-if="notification.data.fixed_count" class="px-2 py-1 bg-success/10 text-success rounded font-medium">
                  {{ notification.data.fixed_count }} fixed
                </span>
                <span class="px-2 py-1 rounded font-medium"
                  :class="notification.data.trend === 'improving' ? 'bg-success/10 text-success' : notification.data.trend === 'declining' ? 'bg-error/10 text-error' : 'bg-surface-container-highest text-on-surface-variant'">
                  {{ notification.data.trend === 'improving' ? 'Improving' : notification.data.trend === 'declining' ? 'Declining' : 'Stable' }}
                </span>
              </div>
              <div v-if="notification.data.actions?.length" class="flex flex-wrap gap-2 text-xs">
                <span v-for="action in notification.data.actions" :key="action"
                  class="px-2 py-1 bg-primary/5 text-primary/80 rounded border border-primary/10">
                  {{ action }}
                </span>
              </div>
            </div>

            <!-- Additional Data (findings, team updates) -->
            <div v-else-if="notification.data" class="flex flex-wrap gap-2 text-xs">
              <span
                v-if="notification.data.file_path"
                class="px-2 py-1 bg-surface-container-highest rounded text-on-surface-variant"
              >
                {{ notification.data.file_path }}
              </span>
              <span
                v-if="notification.data.severity"
                :class="[
                  'px-2 py-1 rounded font-medium',
                  notification.data.severity === 'critical' && 'bg-error/10 text-error',
                  notification.data.severity === 'warning' && 'bg-warning/10 text-warning',
                  notification.data.severity === 'info' && 'bg-info/10 text-info'
                ]"
              >
                {{ notification.data.severity }}
              </span>
            </div>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
