<script setup lang="ts">
import { ref, onMounted } from 'vue';
import axios from 'axios';

const props = defineProps<{
  projectId?: string;
}>();

const recommendations = ref<any[]>([]);
const loading = ref(false);

async function fetchRecommendations() {
  try {
    loading.value = true;
    const token = localStorage.getItem('reviewhub_token');
    const params = props.projectId ? { project: props.projectId } : {};
    const response = await axios.get(
      `${import.meta.env.VITE_API_URL}/skills/recommendations/`,
      { 
        params,
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      }
    );
    recommendations.value = response.data || [];
  } catch (error) {
    console.error('Failed to fetch recommendations:', error);
    recommendations.value = [];
  } finally {
    loading.value = false;
  }
}

function getPriorityColor(priority: string) {
  const colors: Record<string, string> = {
    high: 'text-error',
    medium: 'text-warning',
    low: 'text-info',
    mastered: 'text-success',
    growth: 'text-primary',
  };
  return colors[priority] || 'text-on-surface-variant';
}

function getPriorityBg(priority: string) {
  const colors: Record<string, string> = {
    high: 'bg-error/10',
    medium: 'bg-warning/10',
    low: 'bg-info/10',
    mastered: 'bg-success/10',
    growth: 'bg-primary/10',
  };
  return colors[priority] || 'bg-surface-container';
}

function getPriorityLabel(priority: string) {
  // v1.1 (May 2 2026): Dutch labels for the priority pill. Backend
  // returns the english enum keys; this layer is the only place they
  // need to be translated.
  const labels: Record<string, string> = {
    high: 'hoge prioriteit',
    medium: 'gemiddelde prioriteit',
    low: 'lage prioriteit',
    mastered: 'beheerst',
    growth: 'volgend niveau',
  };
  return labels[priority] || priority;
}

// v1.1 (May 2 2026): Dutch labels for the severity_breakdown chips on
// the rec card (critical/warning/info/suggestion).
function getSeverityLabel(severity: string) {
  const labels: Record<string, string> = {
    critical: 'kritiek',
    warning: 'waarschuwing',
    info: 'info',
    suggestion: 'suggestie',
  };
  return labels[severity] || severity;
}

function getPriorityIcon(priority: string) {
  const icons: Record<string, string> = {
    high: 'error',
    medium: 'warning',
    low: 'info',
    mastered: 'emoji_events',
    growth: 'rocket_launch',
  };
  return icons[priority] || 'lightbulb';
}

function openResource(url: string) {
  window.open(url, '_blank');
}

onMounted(() => {
  fetchRecommendations();
});
</script>

<template>
  <div class="bg-surface-container-low rounded-lg p-6 border border-outline-variant/20">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <span class="material-symbols-outlined text-primary">school</span>
        <h2 class="text-xl font-bold text-on-surface">Aanbevolen voor jou</h2>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-8">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="recommendations.length === 0" class="text-center py-8">
      <span class="material-symbols-outlined text-6xl text-success mb-2">
        workspace_premium
      </span>
      <p class="text-on-surface font-semibold mb-1">Alle skills zien er sterk uit!</p>
      <p class="text-on-surface-variant text-sm">
        Blijf code pushen — nieuwe aanbevelingen verschijnen wanneer je nieuwe uitdagingen aanpakt.
      </p>
    </div>

    <!-- Recommendations Grid -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="recommendation in recommendations"
        :key="recommendation.skill.id"
        class="bg-surface-container rounded-lg p-4 border border-outline-variant/20 hover:shadow-md transition-shadow flex flex-col"
      >
        <!-- Header -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <h3 class="text-base font-semibold text-on-surface">
                {{ recommendation.skill.name }}
              </h3>
              <span
                :class="[
                  'px-2 py-0.5 text-xs font-medium rounded flex items-center gap-1',
                  getPriorityBg(recommendation.priority),
                  getPriorityColor(recommendation.priority)
                ]"
              >
                <span class="material-symbols-outlined text-xs">{{ getPriorityIcon(recommendation.priority) }}</span>
                {{ getPriorityLabel(recommendation.priority) }}
              </span>
            </div>
            <p class="text-xs text-on-surface-variant">
              {{ recommendation.skill.category }}
            </p>
            <!-- v1.1 E3: Crebo werkproces pill (kerntaakcode + naam). Hidden
                 if backend returned werkproces_code=null (e.g. pattern recs
                 with no skill category). -->
            <p
              v-if="recommendation.werkproces_code"
              class="text-[10px] uppercase tracking-widest text-primary mt-1 font-semibold"
              :title="`Crebo 25604 · ${recommendation.werkproces_name}`"
            >
              <span class="font-mono">{{ recommendation.werkproces_code }}</span>
              <span class="text-on-surface-variant font-normal normal-case tracking-normal mx-1">·</span>
              <span class="font-normal normal-case tracking-normal">{{ recommendation.werkproces_name }}</span>
            </p>
          </div>

          <!-- Score Badge -->
          <div class="flex flex-col items-center">
            <div
              :class="[
                'h-12 w-12 rounded-full flex items-center justify-center text-lg font-bold',
                recommendation.current_score < 50
                  ? 'bg-error/10 text-error'
                  : recommendation.current_score < 70
                  ? 'bg-warning/10 text-warning'
                  : 'bg-success/10 text-success'
              ]"
            >
              {{ recommendation.current_score }}
            </div>
            <span class="text-xs text-on-surface-variant mt-1">score</span><!-- "score" is a Dutch loanword too — leave as-is -->

          </div>
        </div>

        <!-- Reason -->
        <div class="mb-3 p-3 rounded" :class="recommendation.priority === 'mastered' ? 'bg-success/5 border border-success/20' : recommendation.priority === 'growth' ? 'bg-primary/5 border border-primary/20' : 'bg-surface-container-highest'">
          <p class="text-sm" :class="recommendation.priority === 'mastered' ? 'text-success' : recommendation.priority === 'growth' ? 'text-primary' : 'text-on-surface-variant'">
            <span class="material-symbols-outlined text-base align-middle mr-1">
              {{ getPriorityIcon(recommendation.priority) }}
            </span>
            {{ recommendation.reason }}
          </p>
        </div>

        <!-- Improvement Tip -->
        <div v-if="recommendation.improvement_tip" class="mb-3 p-3 bg-primary/5 rounded border border-primary/20">
          <p class="text-sm text-on-surface">
            💡 <strong>Tip:</strong> {{ recommendation.improvement_tip }}
          </p>
        </div>

        <!-- Stats -->
        <div v-if="recommendation.issue_count" class="flex gap-4 mb-3 text-sm">
          <div class="flex items-center gap-1 text-on-surface-variant">
            <span class="material-symbols-outlined text-base">bug_report</span>
            <span>{{ recommendation.issue_count }} {{ recommendation.issue_count === 1 ? 'bevinding' : 'bevindingen' }}</span>
          </div>

          <div
            v-if="recommendation.severity_breakdown"
            class="flex items-center gap-2 text-xs"
          >
            <span
              v-if="recommendation.severity_breakdown.critical"
              class="px-2 py-0.5 bg-error/10 text-error rounded"
            >
              {{ recommendation.severity_breakdown.critical }} {{ getSeverityLabel('critical') }}
            </span>
            <span
              v-if="recommendation.severity_breakdown.warning"
              class="px-2 py-0.5 bg-warning/10 text-warning rounded"
            >
              {{ recommendation.severity_breakdown.warning }} {{ getSeverityLabel('warning') }}
            </span>
          </div>
        </div>

        <!-- Resources -->
        <div v-if="recommendation.suggested_resources?.length" class="space-y-2">
          <p class="text-xs font-semibold text-on-surface-variant">Aanbevolen bronnen:</p>
          <div class="space-y-1">
            <button
              v-for="(resource, idx) in recommendation.suggested_resources.slice(0, 2)"
              :key="idx"
              @click="openResource(resource.url)"
              class="w-full text-left p-2 bg-surface-container-highest rounded hover:bg-primary/5 transition-colors flex items-center gap-2 group"
            >
              <span class="material-symbols-outlined text-sm text-primary">
                {{ resource.type === 'book' ? 'book' : resource.type === 'course' ? 'school' : 'link' }}
              </span>
              <span class="text-sm text-on-surface group-hover:text-primary flex-1">
                {{ resource.title }}
              </span>
              <span class="material-symbols-outlined text-sm text-on-surface-variant group-hover:text-primary">
                open_in_new
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
