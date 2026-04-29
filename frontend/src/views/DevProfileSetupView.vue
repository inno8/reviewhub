<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/composables/useApi';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();

// ── Wizard state ──────────────────────────────────────────────────────────
const currentStep = ref(1);
const totalSteps = 7;
const saving = ref(false);
const loading = ref(true);  // starts true so the form doesn't flash empty
                            // before existing values are loaded in
const toastMsg = ref('');
const isEditing = ref(false);  // true when an existing profile was loaded

// ── Form data ─────────────────────────────────────────────────────────────

// Step 1 – Basic Profile
const jobRole = ref('');
const experienceYears = ref<number | null>(null);
const primaryLanguage = ref('');
const otherLanguages = ref<string[]>([]);
const otherLangInput = ref('');

// Step 2 – Skill Self-Assessment (1–5)
const selfScores = ref<Record<string, number>>({
  clean_code: 3,
  algorithm_efficiency: 3,
  error_handling: 3,
  unit_testing: 3,
  input_validation: 3,
  api_design: 3,
  database_queries: 3,
});

const skillLabels: Record<string, string> = {
  clean_code: 'Writing clean and readable code',
  algorithm_efficiency: 'Debugging issues',
  error_handling: 'Error handling',
  unit_testing: 'Writing tests',
  input_validation: 'Working with APIs',
  api_design: 'Scalable architecture',
  database_queries: 'Performance optimisation',
};

// Step 3 – Coding Behavior
const focusFirst = ref('');
const writesTests = ref('');
const edgeCaseHandling = ref('');
const debuggingApproach = ref('');

// Step 4 – Technical Depth
const canDesignSystem = ref('');
const comfortableWith = ref<string[]>([]);
const workedOn = ref<string[]>([]);

// Step 5 – Preferences
const enjoyMost = ref('');
const wantToImprove = ref('');

// Step 6 – Learning Goals
const currentGoal = ref('');
const learningStyle = ref('');

// Step 7 – Optional
const proudCode = ref('');
const struggledCode = ref('');

// GitHub App connection state. Loaded on mount alongside the existing
// dev profile load. Three observable values:
//   - installUrl: the URL to redirect to when "Install LEERA" is
//     clicked. null until /api/github/install-url returns.
//   - installUrlError: human message if the App isn't configured
//     server-side (env vars missing). Surfaced under the button.
//   - connectedRepos: existing StudentRepo rows for this user.
//     Populated from /api/github/installations/. Drives the
//     already-connected UI state.
const installUrl = ref<string | null>(null);
const installUrlError = ref<string | null>(null);
const connectingGithub = ref(false);
const connectedRepos = ref<{ full_name: string; default_branch: string }[]>([]);
const connectedInstallationId = ref<number | null>(null);

// ── Helpers ───────────────────────────────────────────────────────────────

const progressPct = computed(() => Math.round(((currentStep.value - 1) / totalSteps) * 100));

function addLanguage() {
  const lang = otherLangInput.value.trim();
  if (lang && !otherLanguages.value.includes(lang)) {
    otherLanguages.value.push(lang);
  }
  otherLangInput.value = '';
}

function removeLanguage(lang: string) {
  otherLanguages.value = otherLanguages.value.filter((l) => l !== lang);
}

function toggleComfort(item: string) {
  const idx = comfortableWith.value.indexOf(item);
  if (idx === -1) comfortableWith.value.push(item);
  else comfortableWith.value.splice(idx, 1);
}

function toggleWorkedOn(item: string) {
  const idx = workedOn.value.indexOf(item);
  if (idx === -1) workedOn.value.push(item);
  else workedOn.value.splice(idx, 1);
}

function nextStep() {
  if (currentStep.value < totalSteps) currentStep.value++;
}

function prevStep() {
  if (currentStep.value > 1) currentStep.value--;
}

function scoreLabel(val: number): string {
  return ['', 'Weak', 'Below avg', 'Average', 'Good', 'Strong'][val] ?? '';
}

// ── Load existing profile (edit mode) ─────────────────────────────────────
// On mount, fetch the user's existing profile if one exists. The backend
// returns 404 for first-time users — that's not an error, just means we
// keep the form defaults. For users editing, every field gets pre-filled
// so they can tweak rather than re-enter.

async function loadExistingProfile() {
  try {
    const { data } = await api.devProfile.get();
    if (!data) return;
    isEditing.value = true;

    // Step 1
    if (data.job_role) jobRole.value = data.job_role;
    if (data.experience_years != null) experienceYears.value = data.experience_years;
    if (data.primary_language) primaryLanguage.value = data.primary_language;
    if (Array.isArray(data.other_languages)) otherLanguages.value = [...data.other_languages];

    // Step 2 — only override defaults for keys the backend actually sent;
    // any new skill key in skillLabels but missing from saved data keeps
    // its 3 default.
    if (data.self_scores && typeof data.self_scores === 'object') {
      selfScores.value = { ...selfScores.value, ...data.self_scores };
    }

    // Step 3
    if (data.focus_first) focusFirst.value = data.focus_first;
    if (data.writes_tests) writesTests.value = data.writes_tests;
    if (data.edge_case_handling) edgeCaseHandling.value = data.edge_case_handling;
    if (data.debugging_approach) debuggingApproach.value = data.debugging_approach;

    // Step 4
    if (data.can_design_system) canDesignSystem.value = data.can_design_system;
    if (Array.isArray(data.comfortable_with)) comfortableWith.value = [...data.comfortable_with];
    if (Array.isArray(data.worked_on)) workedOn.value = [...data.worked_on];

    // Step 5
    if (data.enjoy_most) enjoyMost.value = data.enjoy_most;
    if (data.want_to_improve) wantToImprove.value = data.want_to_improve;

    // Step 6
    if (data.current_goal) currentGoal.value = data.current_goal;
    if (data.learning_style) learningStyle.value = data.learning_style;

    // Step 7 — proud_code/struggled_code are free-text. The GitHub
    // App connection is loaded separately via loadGithubState() below;
    // it lives in a different table (GitHubInstallation) not in the
    // dev profile, so it persists independently of this form.
    if (data.proud_code) proudCode.value = data.proud_code;
    if (data.struggled_code) struggledCode.value = data.struggled_code;
  } catch (err: any) {
    // 404 = first-time user, no profile yet. Anything else = real error,
    // log but don't block — the user can still fill the form.
    if (err?.response?.status !== 404) {
      console.error('Failed to load existing dev profile:', err);
    }
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  // Run both loads in parallel — they don't depend on each other and
  // the user shouldn't wait for the GitHub call before seeing the form.
  await Promise.all([loadExistingProfile(), loadGithubState()]);
});

// ── GitHub App connection ─────────────────────────────────────────────────

async function loadGithubState() {
  // Fetch the install URL (so the button has somewhere to send) and
  // the existing installations + repos in parallel. Both calls fail
  // gracefully — if /install-url returns 503 the App isn't configured
  // server-side and we surface the message; if /installations is
  // empty the user hasn't connected yet (button shows the install CTA).
  try {
    const { data } = await api.github.installUrl();
    if (data?.configured && data?.install_url) {
      installUrl.value = data.install_url;
    } else {
      installUrlError.value =
        data?.detail ||
        'GitHub connection is currently unavailable. Contact support.';
    }
  } catch (e: any) {
    if (e?.response?.status === 503) {
      installUrlError.value =
        'GitHub App not configured on this server yet. ' +
        'You can finish onboarding without connecting GitHub.';
    } else {
      installUrlError.value =
        e?.response?.data?.detail || 'Could not reach GitHub connection service.';
    }
  }

  try {
    const { data } = await api.github.installations();
    const installs = Array.isArray(data) ? data : [];
    if (installs.length) {
      connectedInstallationId.value = installs[0].installation_id;
      connectedRepos.value = installs.flatMap((inst: any) =>
        (inst.repos || []).map((r: any) => ({
          full_name: r.full_name,
          default_branch: r.default_branch,
        })),
      );
    }
  } catch {
    // 404 / empty list = first-time user. Not an error.
  }
}

function connectGithub() {
  if (!installUrl.value) return;
  connectingGithub.value = true;
  // Open in the same tab so GitHub's redirect lands us back at
  // /dev-profile/connected without a popup-blocker dance.
  window.location.href = installUrl.value;
}

function manageOnGithub() {
  if (connectedInstallationId.value) {
    window.open(
      `https://github.com/settings/installations/${connectedInstallationId.value}`,
      '_blank',
      'noopener',
    );
  } else {
    window.open('https://github.com/settings/installations', '_blank', 'noopener');
  }
}

// ── Submit ────────────────────────────────────────────────────────────────

async function submit() {
  saving.value = true;
  try {
    await api.devProfile.save({
      job_role: jobRole.value,
      experience_years: experienceYears.value ?? 0,
      primary_language: primaryLanguage.value,
      other_languages: otherLanguages.value,
      self_scores: selfScores.value,
      focus_first: focusFirst.value,
      writes_tests: writesTests.value,
      edge_case_handling: edgeCaseHandling.value,
      debugging_approach: debuggingApproach.value,
      can_design_system: canDesignSystem.value,
      comfortable_with: comfortableWith.value,
      worked_on: workedOn.value,
      enjoy_most: enjoyMost.value,
      want_to_improve: wantToImprove.value,
      current_goal: currentGoal.value,
      learning_style: learningStyle.value,
      proud_code: proudCode.value,
      struggled_code: struggledCode.value,
    });

    auth.markDevProfileCompleted();
    // Repo analysis used to be triggered by a hand-pasted GitHub URL
    // here. Now repos are tied through the LEERA GitHub App install
    // (handled separately via the Connect button). No batch job kicked
    // off at submit — calibration data flows from webhook PRs once
    // the App is installed.
    router.push({ name: 'dev-profile-results' });
  } catch (err: any) {
    toastMsg.value = 'Could not save profile. Please try again.';
    console.error(err);
  } finally {
    saving.value = false;
  }
}

function skipToEnd() {
  currentStep.value = totalSteps;
}
</script>

<template>
  <div class="min-h-screen bg-background flex flex-col items-center justify-center p-6">
    <!-- Header -->
    <div class="w-full max-w-2xl mb-8 text-center">
      <h1 class="text-4xl font-black tracking-tight text-on-surface mb-2">
        {{ isEditing ? 'Update Your Developer Profile' : 'Set Up Your Developer Profile' }}
      </h1>
      <p class="text-outline text-sm">
        {{ isEditing
          ? 'Tweak your answers — your saved values are pre-filled.'
          : 'Help us personalise your code reviews and skill tracking (2–3 min)' }}
      </p>
    </div>

    <!-- Loading skeleton — prevents flash-of-empty-form before saved values load -->
    <div v-if="loading" class="w-full max-w-2xl bg-surface-container-low rounded-2xl border border-outline-variant/15 p-8 text-center">
      <span class="material-symbols-outlined animate-spin text-2xl text-primary">progress_activity</span>
      <p class="mt-2 text-sm text-on-surface-variant">Loading your profile...</p>
    </div>

    <template v-else>
    <!-- Progress bar -->
    <div class="w-full max-w-2xl mb-6">
      <div class="flex justify-between text-xs text-outline mb-2">
        <span>Step {{ currentStep }} of {{ totalSteps }}</span>
        <span>{{ progressPct }}% complete</span>
      </div>
      <div class="h-1.5 bg-surface-container rounded-full overflow-hidden">
        <div
          class="h-full bg-primary rounded-full transition-all duration-500"
          :style="{ width: progressPct + '%' }"
        />
      </div>
    </div>

    <!-- Card -->
    <div class="w-full max-w-2xl bg-surface-container-low rounded-2xl border border-outline-variant/15 p-8 shadow-lg">

      <!-- ── Step 1: Basic Profile ── -->
      <template v-if="currentStep === 1">
        <h2 class="text-xl font-bold mb-6">Basic Profile</h2>

        <label class="block mb-5">
          <span class="text-sm text-outline font-semibold mb-2 block">What is your primary role?</span>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <button
              v-for="opt in [
                { v: 'frontend', l: 'Frontend' },
                { v: 'backend', l: 'Backend' },
                { v: 'fullstack', l: 'Full Stack' },
                { v: 'mobile', l: 'Mobile' },
                { v: 'other', l: 'Other' },
              ]"
              :key="opt.v"
              type="button"
              :class="[
                'px-4 py-3 rounded-xl border text-sm font-medium transition-all',
                jobRole === opt.v
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant',
              ]"
              @click="jobRole = opt.v"
            >{{ opt.l }}</button>
          </div>
        </label>

        <label class="block mb-5">
          <span class="text-sm text-outline font-semibold mb-2 block">Years of coding experience</span>
          <input
            v-model.number="experienceYears"
            type="number"
            min="0"
            max="40"
            step="0.5"
            placeholder="e.g. 2.5"
            class="w-full bg-surface-container-lowest rounded-xl border border-outline-variant/20 px-4 py-3 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </label>

        <label class="block mb-5">
          <span class="text-sm text-outline font-semibold mb-2 block">Main programming language</span>
          <input
            v-model="primaryLanguage"
            type="text"
            placeholder="e.g. Python, JavaScript, Rust…"
            class="w-full bg-surface-container-lowest rounded-xl border border-outline-variant/20 px-4 py-3 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </label>

        <div class="block mb-2">
          <span class="text-sm text-outline font-semibold mb-2 block">Other languages you use</span>
          <div class="flex gap-2">
            <input
              v-model="otherLangInput"
              type="text"
              placeholder="Add a language…"
              class="flex-1 bg-surface-container-lowest rounded-xl border border-outline-variant/20 px-4 py-3 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50"
              @keydown.enter.prevent="addLanguage"
            />
            <button type="button" @click="addLanguage"
              class="px-4 py-2 rounded-xl border border-outline-variant/30 text-sm hover:bg-surface-container transition-colors">
              Add
            </button>
          </div>
          <div v-if="otherLanguages.length" class="flex flex-wrap gap-2 mt-2">
            <span
              v-for="lang in otherLanguages"
              :key="lang"
              class="px-3 py-1 bg-primary/10 border border-primary/20 rounded-full text-xs text-primary flex items-center gap-1"
            >
              {{ lang }}
              <button type="button" @click="removeLanguage(lang)" class="text-primary/70 hover:text-primary ml-1">×</button>
            </span>
          </div>
        </div>
      </template>

      <!-- ── Step 2: Skill Self-Assessment ── -->
      <template v-else-if="currentStep === 2">
        <h2 class="text-xl font-bold mb-2">Skill Self-Assessment</h2>
        <p class="text-sm text-outline mb-6">Rate your confidence (1 = weak → 5 = strong)</p>

        <div class="space-y-5">
          <div v-for="(label, slug) in skillLabels" :key="slug">
            <div class="flex justify-between text-sm mb-1">
              <span class="text-on-surface-variant">{{ label }}</span>
              <span class="text-primary font-bold">{{ selfScores[slug] }} — {{ scoreLabel(selfScores[slug]) }}</span>
            </div>
            <input
              type="range"
              min="1" max="5" step="1"
              v-model.number="selfScores[slug]"
              class="w-full accent-primary"
            />
            <div class="flex justify-between text-[10px] text-outline mt-0.5">
              <span>Weak</span><span>Strong</span>
            </div>
          </div>
        </div>
      </template>

      <!-- ── Step 3: Coding Behavior ── -->
      <template v-else-if="currentStep === 3">
        <h2 class="text-xl font-bold mb-6">Coding Behavior</h2>

        <div class="space-y-6">
          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">When writing code, what do you usually focus on first?</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'making_it_work', l: 'Making it work' },
                { v: 'code_quality', l: 'Code quality' },
                { v: 'performance', l: 'Performance' },
                { v: 'readability', l: 'Readability' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', focusFirst === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="focusFirst = opt.v">{{ opt.l }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">Do you usually write tests?</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'always', l: 'Always' }, { v: 'sometimes', l: 'Sometimes' },
                { v: 'rarely', l: 'Rarely' }, { v: 'never', l: 'Never' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', writesTests === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="writesTests = opt.v">{{ opt.l }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">How often do you handle edge cases explicitly?</span>
            <div class="grid grid-cols-3 gap-2">
              <button v-for="opt in [
                { v: 'always', l: 'Always' }, { v: 'sometimes', l: 'Sometimes' }, { v: 'rarely', l: 'Rarely' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', edgeCaseHandling === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="edgeCaseHandling = opt.v">{{ opt.l }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">When debugging, what is your usual approach?</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'trial_and_error', l: 'Trial and error' }, { v: 'logs_tracing', l: 'Logs and tracing' },
                { v: 'structured', l: 'Structured debugging' }, { v: 'struggle', l: 'I struggle' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', debuggingApproach === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="debuggingApproach = opt.v">{{ opt.l }}</button>
            </div>
          </label>
        </div>
      </template>

      <!-- ── Step 4: Technical Depth ── -->
      <template v-else-if="currentStep === 4">
        <h2 class="text-xl font-bold mb-6">Technical Depth</h2>

        <div class="space-y-6">
          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">Can you design a system from scratch?</span>
            <div class="grid grid-cols-3 gap-2">
              <button v-for="opt in [
                { v: 'yes', l: 'Yes confidently' }, { v: 'with_help', l: 'With help' }, { v: 'no', l: 'No' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', canDesignSystem === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="canDesignSystem = opt.v">{{ opt.l }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">I am comfortable with (select all that apply)</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="item in ['databases', 'apis', 'auth', 'deployment']" :key="item" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium capitalize transition-all', comfortableWith.includes(item) ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="toggleComfort(item)">{{ item === 'apis' ? 'APIs' : item === 'auth' ? 'Auth systems' : item === 'deployment' ? 'Deployment (Docker/cloud)' : 'Databases (SQL/NoSQL)' }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">I have worked on (select all that apply)</span>
            <div class="grid grid-cols-3 gap-2">
              <button v-for="item in ['production', 'personal', 'opensource']" :key="item" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', workedOn.includes(item) ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="toggleWorkedOn(item)">{{ item === 'opensource' ? 'Open source' : item === 'production' ? 'Production systems' : 'Personal projects' }}</button>
            </div>
          </label>
        </div>
      </template>

      <!-- ── Step 5: Preferences ── -->
      <template v-else-if="currentStep === 5">
        <h2 class="text-xl font-bold mb-6">Preferences</h2>

        <div class="space-y-6">
          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">What do you enjoy most?</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'frontend_ui', l: 'Frontend UI' }, { v: 'backend_logic', l: 'Backend logic' },
                { v: 'system_design', l: 'System design' }, { v: 'devops', l: 'DevOps' }, { v: 'data_ai', l: 'Data / AI' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', enjoyMost === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="enjoyMost = opt.v">{{ opt.l }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">What do you want to improve most?</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'clean_code', l: 'Clean code' }, { v: 'architecture', l: 'Architecture' },
                { v: 'testing', l: 'Testing' }, { v: 'debugging', l: 'Debugging' }, { v: 'performance', l: 'Performance' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', wantToImprove === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="wantToImprove = opt.v">{{ opt.l }}</button>
            </div>
          </label>
        </div>
      </template>

      <!-- ── Step 6: Learning Goals ── -->
      <template v-else-if="currentStep === 6">
        <h2 class="text-xl font-bold mb-6">Learning Goals</h2>

        <div class="space-y-6">
          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">What is your current goal?</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'get_job', l: 'Get a job' }, { v: 'improve_job', l: 'Improve at current job' },
                { v: 'become_senior', l: 'Become senior' }, { v: 'learn_new_tech', l: 'Learn new tech' },
                { v: 'build_startup', l: 'Build a startup' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', currentGoal === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="currentGoal = opt.v">{{ opt.l }}</button>
            </div>
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">Preferred learning style</span>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="opt in [
                { v: 'short_tips', l: 'Short tips' }, { v: 'detailed', l: 'Detailed explanations' },
                { v: 'examples', l: 'Examples / projects' }, { v: 'challenges', l: 'Challenges' },
              ]" :key="opt.v" type="button"
                :class="['px-4 py-3 rounded-xl border text-sm font-medium transition-all', learningStyle === opt.v ? 'border-primary bg-primary/10 text-primary' : 'border-outline-variant/30 hover:border-outline-variant/60 text-on-surface-variant']"
                @click="learningStyle = opt.v">{{ opt.l }}</button>
            </div>
          </label>
        </div>
      </template>

      <!-- ── Step 7: Optional ── -->
      <template v-else-if="currentStep === 7">
        <div class="flex items-start justify-between mb-2">
          <h2 class="text-xl font-bold">Optional — Extra Context</h2>
          <span class="px-2 py-0.5 text-[10px] font-bold uppercase rounded-full bg-outline/10 text-outline">Skip allowed</span>
        </div>
        <p class="text-sm text-outline mb-6">Help us calibrate your profile from the start. All optional.</p>

        <div class="space-y-5">
          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">Paste a piece of code you are proud of</span>
            <textarea
              v-model="proudCode"
              rows="5"
              placeholder="// Your best work..."
              class="w-full bg-surface-container-lowest rounded-xl border border-outline-variant/20 px-4 py-3 text-sm font-mono text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50 resize-y"
            />
          </label>

          <label class="block">
            <span class="text-sm text-outline font-semibold mb-2 block">Paste a piece of code you struggled with</span>
            <textarea
              v-model="struggledCode"
              rows="5"
              placeholder="// Something that gave you trouble..."
              class="w-full bg-surface-container-lowest rounded-xl border border-outline-variant/20 px-4 py-3 text-sm font-mono text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/50 resize-y"
            />
          </label>

          <!-- ── Connect GitHub via the LEERA App ── -->
          <div class="p-4 bg-primary/5 rounded-xl border border-primary/15">
            <div class="flex items-center gap-2 mb-3">
              <span class="material-symbols-outlined text-primary text-lg">code</span>
              <span class="text-sm font-bold text-on-surface">Connect your GitHub</span>
            </div>

            <!-- Already-connected state — shows the repos and lets you manage -->
            <div v-if="connectedRepos.length" class="space-y-3">
              <p class="text-xs text-on-surface-variant">
                LEERA can read pull requests and post review comments on
                <strong class="text-on-surface">{{ connectedRepos.length }}</strong>
                {{ connectedRepos.length === 1 ? 'repository' : 'repositories' }}.
              </p>
              <ul class="bg-surface-container rounded-lg border border-outline-variant/10 max-h-32 overflow-y-auto">
                <li
                  v-for="repo in connectedRepos"
                  :key="repo.full_name"
                  class="px-3 py-2 border-b border-outline-variant/5 last:border-b-0 flex items-center gap-2"
                >
                  <span class="material-symbols-outlined text-xs text-primary">folder_open</span>
                  <span class="font-mono text-xs text-on-surface">{{ repo.full_name }}</span>
                </li>
              </ul>
              <button
                type="button"
                @click="manageOnGithub"
                class="text-xs text-primary hover:underline inline-flex items-center gap-1"
              >
                Add or remove repos on GitHub
                <span class="material-symbols-outlined text-xs">open_in_new</span>
              </button>
            </div>

            <!-- Not yet connected — single CTA that opens GitHub install flow -->
            <div v-else>
              <p class="text-xs text-outline mb-3">
                Install the LEERA GitHub App on the repos you want reviewed.
                One install covers all your project repos — your teachers
                never need to be collaborators.
              </p>
              <button
                type="button"
                @click="connectGithub"
                :disabled="connectingGithub || !installUrl"
                class="w-full bg-on-surface text-background px-4 py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 hover:opacity-90 transition-opacity active:scale-95 disabled:opacity-50"
              >
                <svg v-if="!connectingGithub" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.385-1.335-1.755-1.335-1.755-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.4 3-.405 1.02.005 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
                </svg>
                <span v-else class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
                {{ connectingGithub ? 'Opening GitHub...' : 'Install LEERA on GitHub' }}
              </button>
              <p v-if="installUrlError" class="text-xs text-error mt-2">{{ installUrlError }}</p>
            </div>
          </div>
        </div>
      </template>

      <!-- ── Navigation ── -->
      <div class="flex items-center justify-between mt-8 pt-6 border-t border-outline-variant/10">
        <button
          v-if="currentStep > 1"
          type="button"
          class="flex items-center gap-2 px-4 py-2 rounded-xl border border-outline-variant/30 text-sm text-on-surface-variant hover:bg-surface-container transition-colors"
          @click="prevStep"
        >
          <span class="material-symbols-outlined text-sm">arrow_back</span>
          Back
        </button>
        <div v-else></div>

        <div class="flex items-center gap-3">
          <button
            v-if="currentStep < totalSteps"
            type="button"
            class="text-sm text-outline hover:text-on-surface-variant transition-colors"
            @click="skipToEnd"
          >
            Skip to end
          </button>

          <button
            v-if="currentStep < totalSteps"
            type="button"
            class="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-bold hover:bg-primary/90 transition-colors"
            @click="nextStep"
          >
            Next
            <span class="material-symbols-outlined text-sm">arrow_forward</span>
          </button>

          <button
            v-else
            type="button"
            :disabled="saving"
            class="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-60"
            @click="submit"
          >
            <span v-if="saving" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            <span v-else class="material-symbols-outlined text-sm">check_circle</span>
            {{ saving ? 'Saving…' : 'Complete Setup' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Step dots -->
    <div class="flex gap-2 mt-6">
      <button
        v-for="n in totalSteps"
        :key="n"
        type="button"
        :class="[
          'w-2 h-2 rounded-full transition-all',
          n === currentStep ? 'bg-primary w-5' : n < currentStep ? 'bg-primary/50' : 'bg-outline/30',
        ]"
        @click="currentStep = n"
      />
    </div>
    </template>

    <!-- Toast -->
    <div
      v-if="toastMsg"
      class="fixed bottom-6 right-6 bg-surface-container-high border border-outline-variant/20 rounded-xl px-5 py-3 text-sm text-on-surface shadow-lg cursor-pointer z-50"
      @click="toastMsg = ''"
    >
      {{ toastMsg }}
    </div>
  </div>
</template>
