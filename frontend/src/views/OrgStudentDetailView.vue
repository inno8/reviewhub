<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import AppShell from '@/components/layout/AppShell.vue';

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const error = ref('');

const student = ref<{ id: number; name: string; email: string } | null>(null);
const level = ref('');
const compositeScore = ref(0);
const trend = ref('');
const radar = ref<{ category: string; score: number }[]>([]);
const strengths = ref<string[]>([]);
const weaknesses = ref<string[]>([]);
const evalHistory = ref<any[]>([]);
const scoreHistory = ref<any[]>([]);

const maxRadarScore = computed(() => {
  if (!radar.value.length) return 100;
  return Math.max(...radar.value.map((r) => r.score), 100);
});

function trendIcon(t: string) {
  if (t === 'improving') return 'trending_up';
  if (t === 'declining') return 'trending_down';
  return 'trending_flat';
}

function trendColor(t: string) {
  if (t === 'improving') return 'text-primary';
  if (t === 'declining') return 'text-error';
  return 'text-on-surface-variant';
}

function levelBadge(l: string) {
  const map: Record<string, { label: string; color: string }> = {
    beginner: { label: 'Beginner', color: 'bg-error/10 text-error border-error/20' },
    developing: { label: 'Developing', color: 'bg-tertiary/10 text-tertiary border-tertiary/20' },
    proficient: { label: 'Proficient', color: 'bg-primary/10 text-primary border-primary/20' },
    advanced: { label: 'Advanced', color: 'bg-primary/15 text-primary border-primary/30' },
    new: { label: 'New', color: 'bg-on-surface-variant/10 text-on-surface-variant border-outline-variant/20' },
  };
  return map[l] || map.new;
}

function barWidth(score: number) {
  return `${Math.min(100, (score / maxRadarScore.value) * 100)}%`;
}

function barColor(score: number) {
  if (score >= 80) return 'bg-primary';
  if (score >= 60) return 'bg-primary/70';
  if (score >= 40) return 'bg-tertiary';
  return 'bg-error';
}

async function loadStudent() {
  loading.value = true;
  error.value = '';
  try {
    const { data } = await api.org.studentDetail(Number(route.params.studentId));
    student.value = data.student;
    level.value = data.level;
    compositeScore.value = data.composite_score;
    trend.value = data.trend;
    radar.value = data.radar || [];
    strengths.value = data.strengths || [];
    weaknesses.value = data.weaknesses || [];
    evalHistory.value = data.evaluation_history || [];
    scoreHistory.value = data.score_history || [];
  } catch (e: any) {
    error.value = e?.response?.data?.error || 'Failed to load student details.';
  } finally {
    loading.value = false;
  }
}

onMounted(loadStudent);
</script>

<template>
  <AppShell>
  <div class="space-y-6 p-6">
    <!-- Back + header -->
    <div class="flex items-center gap-4">
      <button @click="router.push('/org-dashboard')"
        class="p-2 rounded-lg hover:bg-surface-container-highest transition-colors">
        <span class="material-symbols-outlined text-on-surface-variant">arrow_back</span>
      </button>
      <div v-if="student">
        <h1 class="text-2xl font-extrabold text-on-surface tracking-tight">{{ student.name }}</h1>
        <p class="text-sm text-on-surface-variant">{{ student.email }}</p>
      </div>
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
      <!-- Summary cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <!-- Level -->
        <div class="glass-panel rounded-xl p-5">
          <div class="text-xs font-bold uppercase tracking-widest text-outline mb-2">Level</div>
          <span class="px-3 py-1.5 rounded-full text-sm font-bold border" :class="levelBadge(level).color">
            {{ levelBadge(level).label }}
          </span>
        </div>
        <!-- Score -->
        <div class="glass-panel rounded-xl p-5">
          <div class="text-xs font-bold uppercase tracking-widest text-outline mb-2">Composite Score</div>
          <div class="text-3xl font-extrabold text-on-surface">{{ compositeScore }}</div>
        </div>
        <!-- Trend -->
        <div class="glass-panel rounded-xl p-5">
          <div class="text-xs font-bold uppercase tracking-widest text-outline mb-2">Trend</div>
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-2xl" :class="trendColor(trend)">{{ trendIcon(trend) }}</span>
            <span class="text-sm font-bold capitalize" :class="trendColor(trend)">{{ trend || 'New' }}</span>
          </div>
        </div>
      </div>

      <!-- Radar (bar chart) + Strengths/Weaknesses -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Skill breakdown (bars) -->
        <div class="glass-panel rounded-xl p-6 lg:col-span-2">
          <h2 class="text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-primary text-lg">radar</span>
            Skill Breakdown
          </h2>
          <div v-if="!radar.length" class="text-center py-8 text-on-surface-variant text-sm">
            No skill data yet.
          </div>
          <div v-else class="space-y-3">
            <div v-for="r in radar" :key="r.category" class="flex items-center gap-3">
              <div class="w-32 text-xs font-bold text-on-surface-variant truncate text-right">{{ r.category }}</div>
              <div class="flex-1 h-6 bg-surface-container-highest rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500" :class="barColor(r.score)" :style="{ width: barWidth(r.score) }"></div>
              </div>
              <div class="w-10 text-xs font-bold text-on-surface text-right">{{ r.score }}</div>
            </div>
          </div>
        </div>

        <!-- Strengths & Weaknesses -->
        <div class="space-y-4">
          <div class="glass-panel rounded-xl p-5">
            <h3 class="text-xs font-bold uppercase tracking-widest text-outline mb-3 flex items-center gap-1">
              <span class="material-symbols-outlined text-primary text-sm">thumb_up</span> Strengths
            </h3>
            <div v-if="!strengths.length" class="text-sm text-on-surface-variant">None yet</div>
            <div v-else class="space-y-2">
              <div v-for="s in strengths" :key="s"
                class="px-3 py-2 bg-primary/10 border border-primary/20 rounded-lg text-sm font-bold text-primary">
                {{ s }}
              </div>
            </div>
          </div>
          <div class="glass-panel rounded-xl p-5">
            <h3 class="text-xs font-bold uppercase tracking-widest text-outline mb-3 flex items-center gap-1">
              <span class="material-symbols-outlined text-error text-sm">warning</span> Needs Work
            </h3>
            <div v-if="!weaknesses.length" class="text-sm text-on-surface-variant">None yet</div>
            <div v-else class="space-y-2">
              <div v-for="w in weaknesses" :key="w"
                class="px-3 py-2 bg-error/10 border border-error/20 rounded-lg text-sm font-bold text-error">
                {{ w }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Evaluation history -->
      <div class="glass-panel rounded-xl p-6">
        <h2 class="text-sm font-bold text-on-surface mb-4 flex items-center gap-2">
          <span class="material-symbols-outlined text-primary text-lg">history</span>
          Evaluation History
        </h2>
        <div v-if="!evalHistory.length" class="text-center py-8 text-on-surface-variant text-sm">
          No evaluations yet.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-widest text-outline border-b border-outline-variant/10">
                <th class="pb-3 pr-4">Date</th>
                <th class="pb-3 pr-4">Commit</th>
                <th class="pb-3 pr-4">Project</th>
                <th class="pb-3 pr-4">Score</th>
                <th class="pb-3">Findings</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ev in evalHistory" :key="ev.id"
                class="border-b border-outline-variant/5">
                <td class="py-3 pr-4 text-on-surface-variant">{{ ev.date }}</td>
                <td class="py-3 pr-4">
                  <code class="text-xs bg-surface-container-highest px-2 py-1 rounded text-on-surface">{{ ev.sha }}</code>
                </td>
                <td class="py-3 pr-4 text-on-surface">{{ ev.project || '-' }}</td>
                <td class="py-3 pr-4 font-bold text-on-surface">{{ ev.score ?? '-' }}</td>
                <td class="py-3">
                  <span class="px-2 py-1 rounded-full text-xs font-bold"
                    :class="ev.finding_count > 5 ? 'bg-error/10 text-error' : ev.finding_count > 0 ? 'bg-tertiary/10 text-tertiary' : 'bg-primary/10 text-primary'">
                    {{ ev.finding_count }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
  </AppShell>
</template>
