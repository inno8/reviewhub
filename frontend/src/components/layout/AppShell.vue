<script setup lang="ts">
import { ref, onMounted } from 'vue';
import Header from './Header.vue';
import Sidebar from './Sidebar.vue';

// Welcome-back toast — shown once after a returning user accepts a
// re-invitation (data.returning=true on the AcceptInviteView response).
// The flag is stamped into localStorage by AcceptInviteView; we read +
// clear it here so the toast surfaces regardless of which landing page
// the role-router sent them to (/, /grading, /org/members, /ops).
const welcomeBack = ref<{ orgName: string } | null>(null);

onMounted(() => {
  try {
    const raw = localStorage.getItem('leera.welcomeBack');
    if (!raw) return;
    const parsed = JSON.parse(raw);
    // Only show if stamped within the last 5 minutes — avoids resurrecting
    // stale flags if the user closes a tab without dismissing.
    const fresh = Date.now() - (parsed?.ts ?? 0) < 5 * 60 * 1000;
    if (fresh && parsed?.orgName) {
      welcomeBack.value = { orgName: parsed.orgName };
    }
  } catch {
    // localStorage disabled or value malformed — silently skip.
  }
  // Clear immediately whether or not we showed it. One-shot semantics.
  try { localStorage.removeItem('leera.welcomeBack'); } catch { /* ignore */ }
});

function dismissWelcomeBack() {
  welcomeBack.value = null;
}
</script>

<template>
  <div class="min-h-screen bg-background text-on-surface">
    <Header />
    <Sidebar />
    <main class="ml-64 pt-16 min-h-screen flex flex-col">
      <slot />
    </main>

    <!-- Welcome-back banner. Renders inline at the top of the main
         content area on the next render after a re-invite acceptance.
         Auto-dismissable, doesn't follow scroll, doesn't block the UI. -->
    <Transition name="welcome-fade">
      <div
        v-if="welcomeBack"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-[60] max-w-md w-[calc(100%-2rem)] bg-surface-container-low border border-primary/30 rounded-xl shadow-2xl px-5 py-4 flex items-start gap-3"
      >
        <span class="material-symbols-outlined text-primary text-2xl shrink-0">
          waving_hand
        </span>
        <div class="flex-1">
          <p class="text-sm font-bold text-on-surface mb-0.5">
            Welkom terug bij {{ welcomeBack.orgName }}
          </p>
          <p class="text-xs text-on-surface-variant">
            Je voorgaande data is nog beschikbaar. Eerdere PR's, beoordelingen
            en skill-metingen zie je terug op je dashboard.
          </p>
        </div>
        <button
          type="button"
          @click="dismissWelcomeBack"
          class="text-outline hover:text-on-surface transition-colors"
          aria-label="Sluiten"
        >
          <span class="material-symbols-outlined text-lg">close</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.welcome-fade-enter-active,
.welcome-fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}
.welcome-fade-enter-from,
.welcome-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}
</style>
