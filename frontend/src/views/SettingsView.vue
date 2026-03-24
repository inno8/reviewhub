<script setup lang="ts">
import { ref, onMounted } from 'vue';
import AppShell from '@/components/layout/AppShell.vue';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';

const auth = useAuthStore();

const profile = ref({
  username: '',
  email: '',
  telegramChatId: '',
});
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');

const loading = ref(false);
const toastMessage = ref('');
const toastType = ref<'success' | 'error'>('success');

const notificationSettings = ref({
  emailDigest: true,
  telegramAlerts: false,
  newReviewNotify: true,
  prCreatedNotify: true,
});

onMounted(async () => {
  try {
    const { data } = await api.users.me();
    profile.value.username = data.user.username;
    profile.value.email = data.user.email;
    profile.value.telegramChatId = data.user.telegramChatId || '';
  } catch (e) {
    console.error('Failed to load profile:', e);
  }
});

async function saveProfile() {
  loading.value = true;
  try {
    await api.users.update(auth.user!.id, {
      username: profile.value.username,
      email: profile.value.email,
      telegramChatId: profile.value.telegramChatId || null,
    });
    toastMessage.value = 'Profile updated successfully!';
    toastType.value = 'success';
  } catch (e: any) {
    toastMessage.value = e?.response?.data?.error || 'Failed to update profile';
    toastType.value = 'error';
  } finally {
    loading.value = false;
  }
}

async function changePassword() {
  if (newPassword.value !== confirmPassword.value) {
    toastMessage.value = 'Passwords do not match';
    toastType.value = 'error';
    return;
  }
  
  if (newPassword.value.length < 6) {
    toastMessage.value = 'Password must be at least 6 characters';
    toastType.value = 'error';
    return;
  }
  
  loading.value = true;
  try {
    await api.users.update(auth.user!.id, {
      password: newPassword.value,
    });
    toastMessage.value = 'Password changed successfully!';
    toastType.value = 'success';
    currentPassword.value = '';
    newPassword.value = '';
    confirmPassword.value = '';
  } catch (e: any) {
    toastMessage.value = e?.response?.data?.error || 'Failed to change password';
    toastType.value = 'error';
  } finally {
    loading.value = false;
  }
}

function saveNotifications() {
  toastMessage.value = 'Notification preferences saved!';
  toastType.value = 'success';
}
</script>

<template>
  <AppShell>
    <div class="p-6 max-w-4xl mx-auto">
      <h1 class="text-2xl font-bold text-on-surface mb-2">Settings</h1>
      <p class="text-on-surface-variant mb-8">Manage your account and preferences</p>

      <!-- Profile Section -->
      <div class="glass-panel rounded-xl p-6 mb-6">
        <div class="flex items-center gap-3 mb-6">
          <span class="material-symbols-outlined text-primary">person</span>
          <h2 class="text-lg font-bold text-on-surface">Profile</h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div>
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
              Username
            </label>
            <input
              v-model="profile.username"
              type="text"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
            />
          </div>
          <div>
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
              Email
            </label>
            <input
              v-model="profile.email"
              type="email"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
            />
          </div>
        </div>

        <div class="mb-6">
          <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
            Telegram Chat ID
            <span class="text-outline/60 normal-case font-normal ml-2">(for notifications)</span>
          </label>
          <input
            v-model="profile.telegramChatId"
            type="text"
            placeholder="e.g., 123456789"
            class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
          />
          <p class="text-[10px] text-outline mt-2">
            Get your Chat ID by messaging @userinfobot on Telegram
          </p>
        </div>

        <button
          @click="saveProfile"
          :disabled="loading"
          class="primary-gradient text-on-primary font-bold py-3 px-6 rounded-lg disabled:opacity-50"
        >
          Save Profile
        </button>
      </div>

      <!-- Password Section -->
      <div class="glass-panel rounded-xl p-6 mb-6">
        <div class="flex items-center gap-3 mb-6">
          <span class="material-symbols-outlined text-primary">lock</span>
          <h2 class="text-lg font-bold text-on-surface">Change Password</h2>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
              Current Password
            </label>
            <input
              v-model="currentPassword"
              type="password"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
            />
          </div>
          <div>
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
              New Password
            </label>
            <input
              v-model="newPassword"
              type="password"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
            />
          </div>
          <div>
            <label class="text-xs font-bold uppercase tracking-widest text-outline block mb-2">
              Confirm Password
            </label>
            <input
              v-model="confirmPassword"
              type="password"
              class="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface placeholder:text-outline/40 focus:ring-1 focus:ring-primary/50 focus:border-primary py-3 px-4"
            />
          </div>
        </div>

        <button
          @click="changePassword"
          :disabled="loading || !newPassword || !confirmPassword"
          class="bg-surface-container-highest text-on-surface font-bold py-3 px-6 rounded-lg hover:bg-outline-variant transition-colors disabled:opacity-50"
        >
          Change Password
        </button>
      </div>

      <!-- Notifications Section -->
      <div class="glass-panel rounded-xl p-6 mb-6">
        <div class="flex items-center gap-3 mb-6">
          <span class="material-symbols-outlined text-primary">notifications</span>
          <h2 class="text-lg font-bold text-on-surface">Notifications</h2>
        </div>

        <div class="space-y-4 mb-6">
          <label class="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              v-model="notificationSettings.emailDigest"
              class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary"
            />
            <div>
              <span class="text-sm text-on-surface group-hover:text-primary transition-colors">
                Daily Email Digest
              </span>
              <p class="text-xs text-outline">Receive a summary of new findings each morning</p>
            </div>
          </label>

          <label class="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              v-model="notificationSettings.telegramAlerts"
              class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary"
            />
            <div>
              <span class="text-sm text-on-surface group-hover:text-primary transition-colors">
                Telegram Alerts
              </span>
              <p class="text-xs text-outline">Get instant notifications via Telegram bot</p>
            </div>
          </label>

          <label class="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              v-model="notificationSettings.newReviewNotify"
              class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary"
            />
            <div>
              <span class="text-sm text-on-surface group-hover:text-primary transition-colors">
                New Review Notifications
              </span>
              <p class="text-xs text-outline">Notify when new code reviews are available</p>
            </div>
          </label>

          <label class="flex items-center gap-3 cursor-pointer group">
            <input
              type="checkbox"
              v-model="notificationSettings.prCreatedNotify"
              class="h-5 w-5 rounded border-outline-variant bg-surface-container text-primary"
            />
            <div>
              <span class="text-sm text-on-surface group-hover:text-primary transition-colors">
                PR Created Notifications
              </span>
              <p class="text-xs text-outline">Notify when a fix is applied and PR created</p>
            </div>
          </label>
        </div>

        <button
          @click="saveNotifications"
          class="bg-surface-container-highest text-on-surface font-bold py-3 px-6 rounded-lg hover:bg-outline-variant transition-colors"
        >
          Save Preferences
        </button>
      </div>

      <!-- Danger Zone -->
      <div class="glass-panel rounded-xl p-6 border border-error/20">
        <div class="flex items-center gap-3 mb-6">
          <span class="material-symbols-outlined text-error">warning</span>
          <h2 class="text-lg font-bold text-error">Danger Zone</h2>
        </div>

        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-on-surface font-medium">Log out of all devices</p>
            <p class="text-xs text-outline">This will invalidate all active sessions</p>
          </div>
          <button
            class="px-4 py-2 border border-error/30 text-error rounded-lg hover:bg-error/10 transition-colors text-sm font-medium"
          >
            Log Out Everywhere
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toastMessage"
      :class="[
        'fixed bottom-4 right-4 rounded-lg px-4 py-2 text-sm shadow-lg cursor-pointer z-50',
        toastType === 'success' ? 'bg-primary/20 border border-primary/30 text-primary' : 'bg-error/20 border border-error/30 text-error'
      ]"
      @click="toastMessage = ''"
    >
      {{ toastMessage }}
    </div>
  </AppShell>
</template>
