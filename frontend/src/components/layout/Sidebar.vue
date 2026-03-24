<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useProjectsStore } from '@/stores/projects';
import { useFindingsStore } from '@/stores/findings';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const projectsStore = useProjectsStore();
const findingsStore = useFindingsStore();

const selectedDate = ref<string | null>(null);

onMounted(() => {
  projectsStore.fetchProjects();
});

const navItems = [
  { name: 'Dashboard', icon: 'dashboard', path: '/' },
  { name: 'Insights', icon: 'analytics', path: '/insights' },
  { name: 'Team Management', icon: 'group', path: '/team', adminOnly: true },
];

function isActive(path: string) {
  return route.path === path;
}

// Calendar data
const currentMonth = ref(new Date());

const monthName = computed(() => 
  currentMonth.value.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
);

const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const today = new Date();
const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

const firstDayOffset = computed(() => 
  new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth(), 1).getDay()
);

const daysInMonth = computed(() => 
  new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 0).getDate()
);

const calendarCells = computed(() => {
  const blanks = Array.from({ length: firstDayOffset.value }, () => null);
  const monthDays = Array.from({ length: daysInMonth.value }, (_, i) => i + 1);
  return [...blanks, ...monthDays];
});

// Simulated activity dates (would come from API)
const activityDates = ref<Set<string>>(new Set(['2026-03-08', '2026-03-11', '2026-03-16', '2026-03-19', '2026-03-23']));

function formatDateStr(day: number): string {
  const year = currentMonth.value.getFullYear();
  const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
  const dayStr = String(day).padStart(2, '0');
  return `${year}-${month}-${dayStr}`;
}

function isToday(day: number): boolean {
  return formatDateStr(day) === todayStr;
}

function hasActivity(day: number): boolean {
  return activityDates.value.has(formatDateStr(day));
}

function isSelected(day: number): boolean {
  return formatDateStr(day) === selectedDate.value;
}

async function selectDate(day: number) {
  const dateStr = formatDateStr(day);
  
  if (selectedDate.value === dateStr) {
    // Deselect - show all findings
    selectedDate.value = null;
    if (projectsStore.selectedProjectId) {
      await findingsStore.fetchFindings({ projectId: projectsStore.selectedProjectId });
    }
  } else {
    // Select - filter by date
    selectedDate.value = dateStr;
    if (projectsStore.selectedProjectId) {
      await findingsStore.fetchFindings({ 
        projectId: projectsStore.selectedProjectId,
        date: dateStr 
      });
    }
  }
  
  // Navigate to dashboard if not already there
  if (route.path !== '/') {
    router.push('/');
  }
}

function prevMonth() {
  currentMonth.value = new Date(
    currentMonth.value.getFullYear(),
    currentMonth.value.getMonth() - 1,
    1
  );
}

function nextMonth() {
  currentMonth.value = new Date(
    currentMonth.value.getFullYear(),
    currentMonth.value.getMonth() + 1,
    1
  );
}

// Clear date filter when project changes
watch(() => projectsStore.selectedProjectId, () => {
  selectedDate.value = null;
});
</script>

<template>
  <aside class="fixed left-0 top-16 h-[calc(100vh-64px)] w-64 flex flex-col py-4 bg-surface-container-low z-40">
    <!-- Project Selector -->
    <div class="px-4 mb-4">
      <div class="flex items-center gap-3 p-3 bg-surface-container rounded-lg border border-outline-variant/20">
        <div class="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
          <span class="material-symbols-outlined text-primary text-lg">terminal</span>
        </div>
        <div class="flex-1 min-w-0">
          <select
            :value="projectsStore.selectedProjectId"
            @change="projectsStore.setSelectedProject(Number(($event.target as HTMLSelectElement).value))"
            class="w-full bg-transparent border-none text-sm font-bold text-primary focus:ring-0 cursor-pointer p-0 truncate"
          >
            <option v-for="project in projectsStore.projects" :key="project.id" :value="project.id">
              {{ project.displayName }}
            </option>
          </select>
          <p class="text-[10px] text-outline uppercase tracking-widest">Active Project</p>
        </div>
      </div>
    </div>

    <!-- New Review Button -->
    <div class="px-4 mb-6">
      <button class="w-full primary-gradient text-on-primary font-bold py-3 px-4 rounded-lg flex items-center justify-center gap-2 active:scale-95 transition-transform">
        <span class="material-symbols-outlined text-xl">add</span>
        <span class="text-sm">New Review</span>
      </button>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        v-show="!item.adminOnly || auth.isAdmin"
        :class="[
          'rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium',
          isActive(item.path)
            ? 'bg-surface-container text-primary'
            : 'text-outline hover:bg-surface-container/50 hover:text-on-surface'
        ]"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        <span>{{ item.name }}</span>
      </router-link>

      <!-- Calendar Widget -->
      <div class="mt-8 px-4">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-[10px] uppercase tracking-widest text-outline font-bold">
            Activity — {{ monthName }}
          </h3>
          <div class="flex gap-1">
            <button 
              @click="prevMonth"
              class="p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors"
            >
              <span class="material-symbols-outlined text-sm">chevron_left</span>
            </button>
            <button 
              @click="nextMonth"
              class="p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors"
            >
              <span class="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </div>
        </div>
        
        <div class="bg-surface-container-lowest rounded-xl p-3 border border-outline-variant/10">
          <!-- Day Headers -->
          <div class="grid grid-cols-7 gap-1 text-center mb-2">
            <span v-for="day in days" :key="day" class="text-[8px] text-outline">
              {{ day }}
            </span>
          </div>

          <!-- Calendar Grid -->
          <div class="grid grid-cols-7 gap-1 text-[10px]">
            <button
              v-for="(day, index) in calendarCells"
              :key="`cell-${index}`"
              :disabled="!day"
              :class="[
                'p-1 text-center rounded transition-all',
                !day && 'invisible',
                day && isToday(day) && !isSelected(day) && 'bg-primary text-on-primary font-bold shadow-lg shadow-primary/20',
                day && isSelected(day) && 'ring-2 ring-primary bg-primary/20 text-primary font-bold',
                day && !isToday(day) && !isSelected(day) && hasActivity(day) && 'bg-primary-container/20 text-primary border border-primary/30 hover:bg-primary-container/40 cursor-pointer',
                day && !isToday(day) && !isSelected(day) && !hasActivity(day) && 'text-on-surface-variant hover:bg-surface-container cursor-pointer',
              ]"
              @click="day && selectDate(day)"
            >
              {{ day || '' }}
            </button>
          </div>
          
          <!-- Selected date indicator -->
          <div v-if="selectedDate" class="mt-3 pt-3 border-t border-outline-variant/10">
            <div class="flex items-center justify-between">
              <span class="text-[10px] text-primary font-bold">
                Filtering: {{ selectedDate }}
              </span>
              <button 
                @click="selectDate(parseInt(selectedDate.split('-')[2]))"
                class="text-[10px] text-outline hover:text-error"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Bottom Section -->
    <div class="mt-auto border-t border-outline-variant/10 pt-4">
      <router-link
        to="/settings"
        :class="[
          'rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium',
          isActive('/settings')
            ? 'bg-surface-container text-primary'
            : 'text-outline hover:bg-surface-container/50 hover:text-on-surface'
        ]"
      >
        <span class="material-symbols-outlined">settings</span>
        <span>Settings</span>
      </router-link>
      <a
        href="#"
        class="text-outline hover:bg-surface-container/50 hover:text-on-surface rounded-lg mx-2 my-1 px-4 py-3 flex items-center gap-3 transition-transform active:translate-x-1 text-sm font-medium"
      >
        <span class="material-symbols-outlined">help</span>
        <span>Support</span>
      </a>
    </div>
  </aside>
</template>
