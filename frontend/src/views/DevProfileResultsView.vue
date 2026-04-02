<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import SkillRadarChart from '@/components/charts/SkillRadarChart.vue';
import { api } from '@/composables/useApi';

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const error = ref('');
const data = ref<any>(null);

const jobId = computed(() => {
  const j = route.query.job;
  if (j == null || j === '') return undefined;
  const n = Number(j);
  return Number.isFinite(n) ? n : undefined;
});

const runningStatuses = ['pending', 'cloning', 'analyzing', 'building_profile'];

const batchJob = computed(() => data.value?.batch_job ?? null);
const isJobRunning = computed(() => {
  const st = batchJob.value?.status as string | undefined;
  return st ? runningStatuses.includes(st) : false;
});

function formatKey(k: string): string {
  return k.replace(/_/g, ' ');
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function loadAll() {
  try {
    const { data: payload } = await api.devProfile.calibration(jobId.value);
    data.value = payload;
    error.value = '';
    const st = payload?.batch_job?.status as string | undefined;
    if (!st || !runningStatuses.includes(st)) {
      stopPolling();
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || 'Could not load calibration summary.';
    stopPolling();
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  await loadAll();
  if (isJobRunning.value) {
    pollTimer = setInterval(() => {
      if (!isJobRunning.value) {
        stopPolling();
        return;
      }
      void loadAll();
    }, 4000);
  }
});

onUnmounted(() => {
  stopPolling();
});

function goDashboard() {
  router.push({ name: 'dashboard' });
}

function goSkills() {
  router.push({ name: 'skills' });
}
</script>

<template>
  <AppShell>
    <div class="p-8 flex-1 max-w-4xl mx-auto w-full">
      <header class="mb-10">
        <span class="text-primary font-bold uppercase tracking-[0.2em] text-xs">Calibration complete</span>
        <h1 class="text-4xl font-black tracking-tight text-on-surface mt-2">
          Your developer profile
        </h1>
        <p class="text-outline text-sm mt-2 max-w-2xl">
          Here is what we know from your questionnaire and from the commits we analysed with the LLM.
          You can revisit Skills and Insights anytime as new reviews land.
        </p>
      </header>

      <div v-if="loading && !data" class="flex items-center gap-3 py-16 text-outline">
        <span class="material-symbols-outlined animate-spin text-3xl">progress_activity</span>
        Loading your profile…
      </div>

      <div
        v-else-if="error"
        class="p-6 rounded-2xl border border-error/30 bg-error/5 text-error text-sm mb-8"
      >
        {{ error }}
        <button
          type="button"
          class="ml-4 underline"
          @click="loadAll"
        >
          Retry
        </button>
      </div>

      <template v-else-if="data">
        <!-- Batch job in progress -->
        <section
          v-if="batchJob && isJobRunning"
          class="mb-10 p-6 rounded-2xl border border-primary/25 bg-primary/5"
        >
          <div class="flex items-center gap-3 mb-3">
            <span class="material-symbols-outlined text-primary animate-pulse">hub</span>
            <h2 class="text-lg font-bold text-on-surface">Analysing your repository</h2>
          </div>
          <p class="text-sm text-outline mb-4">
            {{ batchJob.repo_url }} — this can take a few minutes. This page refreshes automatically.
          </p>
          <div class="h-2 bg-surface-container rounded-full overflow-hidden">
            <div
              class="h-full bg-primary transition-all duration-500 rounded-full"
              :style="{ width: (batchJob.progress_percent ?? 0) + '%' }"
            />
          </div>
          <p class="text-xs text-outline mt-2 capitalize">
            Status: {{ batchJob.status?.replace(/_/g, ' ') }}
            <span v-if="batchJob.total_commits">
              · {{ batchJob.processed_commits ?? 0 }} / {{ batchJob.total_commits }} commits
            </span>
          </p>
        </section>

        <!-- Batch failed -->
        <section
          v-else-if="batchJob && batchJob.status === 'failed'"
          class="mb-10 p-6 rounded-2xl border border-error/20 bg-error/5"
        >
          <h2 class="text-lg font-bold text-error mb-2">Repository analysis failed</h2>
          <p class="text-sm text-outline">{{ batchJob.error_message || 'Unknown error.' }}</p>
          <p class="text-xs text-outline mt-2">
            Your questionnaire is still saved — you can run batch analysis again from Batch Analysis.
          </p>
        </section>

        <!-- Questionnaire summary -->
        <section v-if="data.questionnaire" class="mb-10">
          <h2 class="text-xl font-black tracking-tight mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-secondary">person</span>
            What you told us
          </h2>
          <div class="grid gap-4 sm:grid-cols-2">
            <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10">
              <p class="text-xs text-outline uppercase tracking-wider mb-1">Role &amp; experience</p>
              <p class="text-sm font-semibold capitalize">
                {{ formatKey(data.questionnaire.job_role || '—') }} ·
                {{ data.questionnaire.experience_years ?? '—' }} yrs
              </p>
              <p class="text-sm text-on-surface-variant mt-1">
                {{ data.questionnaire.primary_language }}
                <span v-if="data.questionnaire.other_languages?.length">
                  · also {{ data.questionnaire.other_languages.join(', ') }}
                </span>
              </p>
            </div>
            <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10">
              <p class="text-xs text-outline uppercase tracking-wider mb-1">Goals &amp; learning</p>
              <p class="text-sm">
                <span class="font-medium capitalize">{{ formatKey(data.questionnaire.current_goal || '—') }}</span>
                ·
                <span class="capitalize">{{ formatKey(data.questionnaire.learning_style || '—') }}</span>
              </p>
              <p class="text-sm text-on-surface-variant mt-1 capitalize">
                Focus: {{ formatKey(data.questionnaire.want_to_improve || '—') }}
              </p>
            </div>
          </div>
        </section>

        <!-- Code-derived insights (LLM evaluations) -->
        <section class="mb-10">
          <h2 class="text-xl font-black tracking-tight mb-4 flex items-center gap-2">
            <span class="material-symbols-outlined text-tertiary">analytics</span>
            What we see in your code
            <span
              v-if="batchJob && !isJobRunning && batchJob.status === 'completed'"
              class="text-xs font-normal text-emerald-500 ml-2 px-2 py-0.5 rounded-full bg-emerald-500/10"
            >
              Batch complete
            </span>
          </h2>

          <div
            v-if="!data.evaluation_insights?.evaluation_count && (!batchJob || isJobRunning)"
            class="p-6 rounded-2xl border border-outline-variant/15 bg-surface-container-low text-outline text-sm"
          >
            <span v-if="isJobRunning">
              Findings from the LLM will appear here as commits are processed.
            </span>
            <span v-else>
              No analysed commits yet. Link a repository during onboarding or run Batch Analysis to calibrate from real code.
            </span>
          </div>

          <div
            v-else
            class="space-y-4"
          >
            <div class="grid gap-4 sm:grid-cols-3">
              <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10 text-center">
                <p class="text-3xl font-black text-primary">
                  {{ data.evaluation_insights.evaluation_count }}
                </p>
                <p class="text-xs text-outline uppercase tracking-wider">Commits reviewed</p>
              </div>
              <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10 text-center">
                <p class="text-3xl font-black text-secondary">
                  {{ data.evaluation_insights.avg_score ?? '—' }}
                </p>
                <p class="text-xs text-outline uppercase tracking-wider">Avg quality score</p>
              </div>
              <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10 text-center">
                <p class="text-3xl font-black text-tertiary">
                  {{ data.evaluation_insights.total_findings }}
                </p>
                <p class="text-xs text-outline uppercase tracking-wider">Findings flagged</p>
              </div>
            </div>

            <div
              v-if="Object.keys(data.evaluation_insights.severity_breakdown || {}).length"
              class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10"
            >
              <p class="text-xs text-outline uppercase tracking-wider mb-2">Findings by severity</p>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="(n, sev) in data.evaluation_insights.severity_breakdown"
                  :key="sev"
                  class="px-3 p-1 rounded-lg text-xs font-semibold capitalize bg-surface-container"
                >
                  {{ sev }}: {{ n }}
                </span>
              </div>
            </div>

            <div
              v-if="data.evaluation_insights.top_skill_issues?.length"
              class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10"
            >
              <p class="text-xs text-outline uppercase tracking-wider mb-3">Where the LLM saw the most issues</p>
              <ul class="space-y-2">
                <li
                  v-for="row in data.evaluation_insights.top_skill_issues"
                  :key="row.slug"
                  class="flex justify-between text-sm"
                >
                  <span>{{ row.name }}</span>
                  <span class="font-mono text-outline">{{ row.issue_count }}</span>
                </li>
              </ul>
            </div>

            <!-- Visual Charts -->
            <div
              v-if="data.evaluation_insights.top_skill_issues?.length"
              class="grid grid-cols-1 lg:grid-cols-2 gap-4"
            >
              <!-- Skill Radar Chart -->
              <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10">
                <p class="text-xs text-outline uppercase tracking-wider mb-3">Skill Overview</p>
                <SkillRadarChart
                  :data="data.evaluation_insights.top_skill_issues.slice(0, 8).map((s: any) => ({
                    category: s.name,
                    score: Math.max(0, 100 - (s.issue_count * 10)),
                  }))"
                />
              </div>

              <!-- Severity Visual Bars -->
              <div class="p-4 rounded-xl bg-surface-container-low border border-outline-variant/10">
                <p class="text-xs text-outline uppercase tracking-wider mb-3">Issue Severity Distribution</p>
                <div class="space-y-3 mt-4">
                  <div
                    v-for="(count, sev) in (data.evaluation_insights.severity_breakdown || {})"
                    :key="sev"
                    class="flex items-center gap-3"
                  >
                    <span
                      class="text-xs font-bold uppercase w-20"
                      :class="{
                        'text-red-400': sev === 'critical',
                        'text-orange-400': sev === 'warning',
                        'text-blue-400': sev === 'info',
                        'text-green-400': sev === 'suggestion',
                      }"
                    >{{ sev }}</span>
                    <div class="flex-1 bg-surface-container-lowest rounded-full h-5 overflow-hidden">
                      <div
                        class="h-full rounded-full transition-all"
                        :class="{
                          'bg-red-500': sev === 'critical',
                          'bg-orange-500': sev === 'warning',
                          'bg-blue-500': sev === 'info',
                          'bg-green-500': sev === 'suggestion',
                        }"
                        :style="{ width: data.evaluation_insights.total_findings ? (count / data.evaluation_insights.total_findings * 100) + '%' : '0%' }"
                      ></div>
                    </div>
                    <span class="text-sm font-bold w-8 text-right">{{ count }}</span>
                  </div>
                </div>

                <!-- Score Summary -->
                <div class="mt-6 pt-4 border-t border-outline-variant/10 text-center">
                  <p class="text-xs text-outline uppercase mb-1">Average Quality</p>
                  <p class="text-4xl font-black"
                    :class="{
                      'text-red-400': (data.evaluation_insights.avg_score || 0) < 40,
                      'text-orange-400': (data.evaluation_insights.avg_score || 0) >= 40 && (data.evaluation_insights.avg_score || 0) < 60,
                      'text-yellow-400': (data.evaluation_insights.avg_score || 0) >= 60 && (data.evaluation_insights.avg_score || 0) < 75,
                      'text-green-400': (data.evaluation_insights.avg_score || 0) >= 75,
                    }">
                    {{ data.evaluation_insights.avg_score ?? '—' }}%
                  </p>
                </div>
              </div>
            </div>

            <!-- Stored DeveloperProfile row (if backend populated it) -->
            <div
              v-if="data.developer_profile"
              class="p-4 rounded-xl border border-primary/20 bg-primary/5"
            >
              <p class="text-xs text-primary font-bold uppercase tracking-wider mb-2">Profile snapshot (historical batch)</p>
              <p class="text-sm capitalize">
                Level: <strong>{{ data.developer_profile.level }}</strong>
                · Score: <strong>{{ data.developer_profile.overall_score }}</strong>
                · Trend: <strong>{{ data.developer_profile.trend }}</strong>
              </p>
              <p
                v-if="data.developer_profile.commits_analyzed"
                class="text-xs text-outline mt-2"
              >
                {{ data.developer_profile.commits_analyzed }} commits in profile model ·
                {{ data.developer_profile.total_findings }} findings
              </p>
            </div>
          </div>
        </section>

        <footer class="flex flex-wrap gap-3 pt-4 border-t border-outline-variant/10">
          <button
            type="button"
            class="px-6 py-3 rounded-xl bg-primary text-on-primary font-bold text-sm"
            @click="goDashboard"
          >
            Go to dashboard
          </button>
          <button
            type="button"
            class="px-6 py-3 rounded-xl border border-outline-variant/30 text-sm font-semibold hover:bg-surface-container transition-colors"
            @click="goSkills"
          >
            Open Skills
          </button>
        </footer>
      </template>
    </div>
  </AppShell>
</template>
