<template>
  <AppShell>
    <div class="p-8 flex-1">
      <div class="max-w-5xl mx-auto">
        <header class="flex items-center gap-4 pb-4 border-b border-outline-variant/10 mb-6">
          <button
            @click="goBack"
            class="bg-transparent border-none text-on-surface-variant hover:text-on-surface cursor-pointer px-3 py-2 text-sm transition-colors"
            data-testid="back-btn"
          >
            ← Inbox
          </button>
          <div class="flex-1 min-w-0" v-if="store.activeSession">
            <h1 class="text-xl font-semibold text-on-surface">
              {{ store.activeSession.student_name || store.activeSession.student_email }}
            </h1>
            <p class="text-sm text-on-surface-variant">
              {{ store.activeSession.course_name }} ·
              <a
                :href="store.activeSession.pr_url"
                target="_blank"
                class="text-primary hover:underline"
              >
                {{ store.activeSession.pr_title }}
              </a>
            </p>
          </div>
          <div v-if="store.activeSession">
            <span
              class="px-2.5 py-1 rounded-md text-xs uppercase tracking-widest font-semibold"
              :class="stateBadgeClass(store.activeSession.state)"
            >
              {{ stateLabel(store.activeSession.state) }}
            </span>
          </div>
        </header>

        <div v-if="store.activeSessionLoading && !store.activeSession" class="flex flex-col gap-2">
          <div
            v-for="n in 8"
            :key="n"
            class="h-12 bg-surface-container-low rounded-lg animate-pulse"
          ></div>
        </div>

        <div
          v-else-if="store.activeSessionError"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >
          {{ store.activeSessionError }}
        </div>

        <div v-else-if="store.activeSession" class="flex flex-col gap-6">
          <!-- AI draft warnings + controls -->
          <div
            v-if="store.activeSession.ai_draft_truncated"
            class="bg-tertiary/10 border border-tertiary/30 text-tertiary px-4 py-3 rounded-lg text-sm"
            data-testid="truncated-banner"
          >
            The diff was truncated before AI grading. Review carefully.
          </div>

          <div
            v-if="store.activeSession.state === 'pending' || !store.activeSession.ai_draft_generated_at"
            class="glass-panel p-6 text-center rounded-xl"
          >
            <p class="text-on-surface-variant mb-3">No AI draft yet.</p>
            <button
              @click="onGenerateDraft"
              :disabled="draftInFlight"
              class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ draftInFlight ? 'Drafting…' : 'Generate draft' }}
            </button>
          </div>

          <!-- Contributors (Workstream G2) — shown when PR has >1 contributor -->
          <ContributorsList
            v-if="store.activeSession.contributors && store.activeSession.contributors.length > 1"
            :contributors="store.activeSession.contributors"
          />

          <!--
            Student snapshot (Workstream E2)
            v1.1 followup: if session has multiple contributors, show a small
            "view snapshot for [name]" switcher here. v1 just shows the primary
            author's snapshot (via studentId loaded from the Submission).
          -->
          <StudentSnapshotPanel
            v-if="studentId"
            :student-id="studentId"
            :profile-link="true"
          />

          <!-- Rubric scores editor -->
          <section>
            <h2 class="text-base font-semibold text-on-surface mb-3">Rubric scores</h2>
            <div class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
              <div
                v-for="criterion in store.activeSession.rubric_snapshot.criteria"
                :key="criterion.id"
                class="bg-surface-container-low border border-outline-variant/10 rounded-xl px-4 py-3"
              >
                <div class="flex items-center justify-between gap-2 mb-2">
                  <span class="font-medium text-on-surface">{{ criterion.name }}</span>
                  <select
                    :value="scoreFor(criterion.id)"
                    @change="(e) => setScore(criterion.id, parseInt((e.target as HTMLSelectElement).value))"
                    class="bg-surface-container border border-outline-variant/20 text-on-surface rounded-md py-1 px-2 text-sm max-w-[140px] focus:ring-1 focus:ring-primary/50 focus:outline-none"
                    :data-testid="`score-${criterion.id}`"
                  >
                    <option
                      v-for="lvl in criterion.levels"
                      :key="lvl.score"
                      :value="lvl.score"
                    >
                      {{ lvl.score }}{{ lvl.description ? ' — ' + lvl.description : '' }}
                    </option>
                  </select>
                </div>
                <p v-if="evidenceFor(criterion.id)" class="text-xs text-on-surface-variant italic mt-2 leading-relaxed">
                  <span class="font-semibold not-italic">Evidence:</span>
                  {{ evidenceFor(criterion.id) }}
                </p>
              </div>
            </div>
          </section>

          <!-- Inline comments editor -->
          <section>
            <div class="flex items-center gap-4 mb-3">
              <h2 class="text-base font-semibold text-on-surface">Inline comments ({{ editedComments.length }})</h2>
              <span v-if="dirty" class="text-xs text-tertiary">Unsaved changes</span>
              <span v-if="savingEdits" class="text-xs text-tertiary">Saving…</span>
            </div>

            <div
              v-if="editedComments.length === 0"
              class="p-4 bg-surface-container-low border border-dashed border-outline-variant/30 rounded-xl text-on-surface-variant text-sm"
              data-testid="no-comments"
            >
              The AI returned no inline comments. Add a summary note below or click Send with rubric scores only.
            </div>

            <ul v-else class="list-none p-0 m-0 flex flex-col gap-3">
              <li
                v-for="(c, idx) in editedComments"
                :key="idx"
                class="bg-surface-container-low border border-outline-variant/10 rounded-xl p-3"
                :data-testid="`comment-${idx}`"
              >
                <div class="flex items-center justify-between mb-2">
                  <code class="font-mono text-xs text-primary bg-surface-container px-2 py-0.5 rounded">
                    {{ c.file }}:{{ c.line }}
                  </code>
                  <div class="flex items-center gap-3">
                    <button
                      class="inline-flex items-center gap-1 bg-transparent border-none text-on-surface-variant hover:text-primary cursor-pointer text-xs transition-colors"
                      @click="openCodeModal(idx)"
                      :data-testid="`view-in-code-${idx}`"
                      title="Bekijk in code"
                    >
                      <span class="material-symbols-rounded text-base" aria-hidden="true">code</span>
                      Bekijk in code
                    </button>
                    <button
                      class="bg-transparent border-none text-error hover:text-error/80 cursor-pointer text-xs transition-colors"
                      @click="removeComment(idx)"
                      :data-testid="`remove-comment-${idx}`"
                    >
                      Remove
                    </button>
                  </div>
                </div>
                <textarea
                  v-model="c.body"
                  @input="markDirty"
                  class="w-full bg-surface-container-lowest border border-outline-variant/20 text-on-surface rounded-md py-2 px-2 text-sm font-inherit resize-y focus:ring-1 focus:ring-primary/50 focus:outline-none leading-relaxed"
                  rows="3"
                  :data-testid="`comment-body-${idx}`"
                ></textarea>
              </li>
            </ul>
          </section>

          <!-- Summary note -->
          <section>
            <h2 class="text-base font-semibold text-on-surface mb-3">Summary note (optional)</h2>
            <textarea
              v-model="editedSummary"
              @input="markDirty"
              rows="4"
              placeholder="Overall feedback that will appear as a top-level PR comment…"
              class="w-full bg-surface-container-lowest border border-outline-variant/20 text-on-surface rounded-md py-3 px-3 text-sm font-inherit resize-y focus:ring-1 focus:ring-primary/50 focus:outline-none leading-relaxed placeholder:text-outline/50"
              data-testid="summary-textarea"
            ></textarea>
          </section>

          <!-- Send / Resume controls -->
          <footer class="flex items-center justify-between pt-6 border-t border-outline-variant/10">
            <div class="text-on-surface-variant text-sm">
              <span v-if="store.activeSession.docent_review_time_seconds">
                {{ Math.round(store.activeSession.docent_review_time_seconds / 60) }} min reviewed
              </span>
              <span v-if="store.activeSession.state === 'partial'" class="text-tertiary">
                {{ store.activeSession.posted_comments.length }} comments already posted
              </span>
            </div>
            <div class="flex gap-3">
              <button
                @click="onSave"
                :disabled="!dirty || savingEdits"
                class="bg-surface-container hover:bg-surface-container-high text-on-surface px-5 py-2.5 rounded-lg text-sm font-medium border border-outline-variant/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="save-btn"
              >
                Save
              </button>
              <button
                v-if="store.activeSession.state === 'partial'"
                @click="onResume"
                :disabled="sendInFlight"
                class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="resume-btn"
              >
                {{ sendInFlight ? 'Resuming…' : 'Resume send' }}
              </button>
              <button
                v-else
                @click="onSend"
                :disabled="!canSend || sendInFlight"
                class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="send-btn"
              >
                {{ sendInFlight ? 'Sending…' : 'Send to student' }}
              </button>
            </div>
          </footer>

          <!-- Send-result banners -->
          <div
            v-if="sendResult"
            class="px-4 py-3 rounded-lg text-sm"
            :class="sendResultClass"
          >
            <template v-if="sendResult.ok">
              <strong>Sent.</strong>
              Posted {{ sendResult.summary?.posted_count || 0 }} comments
              ({{ sendResult.summary?.skipped_duplicate_count || 0 }} duplicates skipped).
            </template>
            <template v-else-if="sendResult.kind === 'partial'">
              <strong>Partial post.</strong>
              {{ sendResult.posted_so_far }} comments posted. Click Resume to continue.
            </template>
            <template v-else-if="sendResult.kind === 'pr_closed'">
              <strong>PR is closed.</strong> Ask the student to reopen, then try again.
            </template>
            <template v-else-if="sendResult.kind === 'github_auth'">
              <strong>GitHub authentication expired.</strong>
              Update your PAT in Settings, then retry.
            </template>
            <template v-else>
              <strong>Send failed.</strong>
              {{ sendResult.message || 'Unknown error' }}
            </template>
          </div>
        </div>
      </div>
    </div>

    <GradingCommentCodeModal
      v-if="codeModalOpen && selectedComment"
      :session-id="id"
      :comment="selectedComment"
      :session-state="store.activeSession?.state"
      @save="onCodeModalSave"
      @close="closeCodeModal"
    />
  </AppShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import { useGradingStore, type GradingComment, type SessionState } from '@/stores/grading';
import { api } from '@/composables/useApi';
import StudentSnapshotPanel from '@/components/grading/StudentSnapshotPanel.vue';
import ContributorsList from '@/components/grading/ContributorsList.vue';
import GradingCommentCodeModal from '@/components/grading/GradingCommentCodeModal.vue';
import AppShell from '@/components/layout/AppShell.vue';

const route = useRoute();
const router = useRouter();
const store = useGradingStore();

// Local editable state (mirrored from activeSession; synced via watch)
const editedComments = ref<GradingComment[]>([]);
const editedScores = ref<Record<string, { score: number; evidence?: string }>>({});
const editedSummary = ref('');
const dirty = ref(false);
const savingEdits = ref(false);
const draftInFlight = ref(false);
const sendInFlight = ref(false);
const sendResult = ref<any>(null);
const autosaveTimer = ref<number | null>(null);

const id = computed(() => Number(route.params.id));
const studentId = ref<number | null>(null);

// View-in-code modal state
const codeModalOpen = ref(false);
const selectedCommentIdx = ref<number | null>(null);
const selectedComment = computed<GradingComment | null>(() => {
  const i = selectedCommentIdx.value;
  if (i === null) return null;
  return editedComments.value[i] || null;
});

function openCodeModal(idx: number) {
  selectedCommentIdx.value = idx;
  codeModalOpen.value = true;
}

function closeCodeModal() {
  codeModalOpen.value = false;
  selectedCommentIdx.value = null;
}

function onCodeModalSave(updated: GradingComment) {
  const i = selectedCommentIdx.value;
  if (i !== null && editedComments.value[i]) {
    editedComments.value[i] = { ...editedComments.value[i], ...updated };
    markDirty();
    // Persist eagerly — don't wait for autosave.
    onSave();
  }
  closeCodeModal();
}

async function loadStudentIdFromSubmission() {
  const subId = store.activeSession?.submission;
  if (!subId) { studentId.value = null; return; }
  try {
    const { data } = await api.grading.submissions.get(subId);
    studentId.value = data?.student ?? null;
  } catch {
    studentId.value = null;
  }
}

const canSend = computed(() => {
  const st = store.activeSession?.state;
  if (!st) return false;
  return ['drafted', 'reviewing'].includes(st);
});

const sendResultClass = computed(() => {
  const r = sendResult.value;
  if (!r) return '';
  if (r.ok || !r.kind) {
    return 'bg-primary-container/15 border border-primary-container/30 text-primary-container';
  }
  if (r.kind === 'partial') {
    return 'bg-tertiary/10 border border-tertiary/30 text-tertiary';
  }
  return 'bg-error/10 border border-error/20 text-error';
});

onMounted(async () => {
  await store.fetchSession(id.value);
  hydrateEdits();
  loadStudentIdFromSubmission();
  // Auto-transition to reviewing + start stopwatch
  if (store.activeSession?.state === 'drafted') {
    try { await store.startReview(id.value); } catch { /* non-fatal */ }
  }
});

onBeforeUnmount(() => {
  if (autosaveTimer.value) window.clearTimeout(autosaveTimer.value);
});

onBeforeRouteLeave(async (to, from, next) => {
  if (dirty.value && !savingEdits.value) {
    try { await onSave(); } catch { /* continue */ }
  }
  next();
});

watch(() => store.activeSession?.id, () => hydrateEdits());

function hydrateEdits() {
  if (!store.activeSession) return;
  const src = store.activeSession;
  // Prefer final_* if the docent has already edited; else seed from ai_draft_*.
  editedComments.value = JSON.parse(
    JSON.stringify(
      (src.final_comments && src.final_comments.length > 0)
        ? src.final_comments
        : (src.ai_draft_comments || []),
    ),
  );
  editedScores.value = JSON.parse(
    JSON.stringify(
      Object.keys(src.final_scores || {}).length > 0
        ? src.final_scores
        : (src.ai_draft_scores || {}),
    ),
  );
  editedSummary.value = src.final_summary || '';
  dirty.value = false;
}

function markDirty() {
  dirty.value = true;
  scheduleAutosave();
}

function scheduleAutosave() {
  if (autosaveTimer.value) window.clearTimeout(autosaveTimer.value);
  autosaveTimer.value = window.setTimeout(() => {
    if (dirty.value && !savingEdits.value) onSave();
  }, 3000);
}

function scoreFor(criterionId: string): number | undefined {
  return editedScores.value[criterionId]?.score;
}

function evidenceFor(criterionId: string): string | undefined {
  return editedScores.value[criterionId]?.evidence;
}

function setScore(criterionId: string, score: number) {
  const prev = editedScores.value[criterionId] || {};
  editedScores.value[criterionId] = { ...prev, score };
  markDirty();
}

function removeComment(idx: number) {
  editedComments.value.splice(idx, 1);
  markDirty();
}

async function onSave() {
  if (!dirty.value || !store.activeSession) return;
  savingEdits.value = true;
  try {
    await store.saveEdits(id.value, {
      final_scores: editedScores.value,
      final_comments: editedComments.value,
      final_summary: editedSummary.value,
    });
    dirty.value = false;
  } catch (err) {
    // Keep dirty flag so the user can retry.
    console.error('save failed', err);
  } finally {
    savingEdits.value = false;
  }
}

async function onGenerateDraft() {
  draftInFlight.value = true;
  try {
    await store.generateDraft(id.value);
    hydrateEdits();
  } finally {
    draftInFlight.value = false;
  }
}

async function onSend() {
  // Autosave first
  if (dirty.value) await onSave();
  sendInFlight.value = true;
  sendResult.value = null;
  try {
    sendResult.value = await store.send(id.value);
  } finally {
    sendInFlight.value = false;
  }
}

async function onResume() {
  sendInFlight.value = true;
  sendResult.value = null;
  try {
    sendResult.value = await store.resume(id.value);
  } finally {
    sendInFlight.value = false;
  }
}

function goBack() {
  router.push({ name: 'grading-inbox' });
}

function stateLabel(state: SessionState): string {
  const labels: Record<SessionState, string> = {
    pending: 'Pending',
    drafting: 'Drafting…',
    drafted: 'Draft ready',
    reviewing: 'In review',
    sending: 'Sending…',
    posted: 'Posted',
    partial: 'Partial — resume',
    failed: 'Failed',
    discarded: 'Discarded',
  };
  return labels[state] || state;
}

function stateBadgeClass(state: SessionState): string {
  switch (state) {
    case 'drafted':
      return 'bg-primary/15 text-primary';
    case 'reviewing':
      return 'bg-tertiary/20 text-tertiary';
    case 'posted':
      return 'bg-primary-container/15 text-primary-container';
    case 'partial':
      return 'bg-tertiary/20 text-tertiary';
    case 'failed':
      return 'bg-error/15 text-error';
    default:
      return 'bg-surface-container text-on-surface-variant';
  }
}
</script>
