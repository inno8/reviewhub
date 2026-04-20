<template>
  <div class="grading-detail">
    <header class="detail-header">
      <button @click="goBack" class="btn-ghost" data-testid="back-btn">
        ← Inbox
      </button>
      <div class="header-meta" v-if="store.activeSession">
        <h1 class="text-xl font-semibold text-slate-100">
          {{ store.activeSession.student_name || store.activeSession.student_email }}
        </h1>
        <p class="text-sm text-slate-400">
          {{ store.activeSession.course_name }} ·
          <a :href="store.activeSession.pr_url" target="_blank" class="link">
            {{ store.activeSession.pr_title }}
          </a>
        </p>
      </div>
      <div class="header-state" v-if="store.activeSession">
        <span class="state-badge" :class="`state-${store.activeSession.state}`">
          {{ stateLabel(store.activeSession.state) }}
        </span>
      </div>
    </header>

    <div v-if="store.activeSessionLoading && !store.activeSession" class="skeleton-detail">
      <div class="skeleton-row" v-for="n in 8" :key="n"></div>
    </div>

    <div v-else-if="store.activeSessionError" class="error-banner">
      {{ store.activeSessionError }}
    </div>

    <div v-else-if="store.activeSession" class="detail-body">
      <!-- AI draft warnings + controls -->
      <div
        v-if="store.activeSession.ai_draft_truncated"
        class="info-banner warning"
        data-testid="truncated-banner"
      >
        The diff was truncated before AI grading. Review carefully.
      </div>

      <div
        v-if="store.activeSession.state === 'pending' || !store.activeSession.ai_draft_generated_at"
        class="draft-prompt"
      >
        <p>No AI draft yet.</p>
        <button @click="onGenerateDraft" :disabled="draftInFlight" class="btn-primary">
          {{ draftInFlight ? 'Drafting…' : 'Generate draft' }}
        </button>
      </div>

      <!-- Rubric scores editor -->
      <section class="rubric-section">
        <h2>Rubric scores</h2>
        <div class="rubric-grid">
          <div
            v-for="criterion in store.activeSession.rubric_snapshot.criteria"
            :key="criterion.id"
            class="criterion-card"
          >
            <div class="criterion-header">
              <span class="criterion-name">{{ criterion.name }}</span>
              <select
                :value="scoreFor(criterion.id)"
                @change="(e) => setScore(criterion.id, parseInt((e.target as HTMLSelectElement).value))"
                class="score-select"
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
            <p v-if="evidenceFor(criterion.id)" class="criterion-evidence">
              <span class="evidence-label">Evidence:</span>
              {{ evidenceFor(criterion.id) }}
            </p>
          </div>
        </div>
      </section>

      <!-- Inline comments editor -->
      <section class="comments-section">
        <div class="comments-header">
          <h2>Inline comments ({{ editedComments.length }})</h2>
          <span v-if="dirty" class="dirty-indicator">Unsaved changes</span>
          <span v-if="savingEdits" class="dirty-indicator">Saving…</span>
        </div>

        <div
          v-if="editedComments.length === 0"
          class="empty-comments"
          data-testid="no-comments"
        >
          The AI returned no inline comments. Add a summary note below or click Send with rubric scores only.
        </div>

        <ul v-else class="comment-list">
          <li
            v-for="(c, idx) in editedComments"
            :key="idx"
            class="comment-card"
            :data-testid="`comment-${idx}`"
          >
            <div class="comment-meta">
              <code class="comment-location">{{ c.file }}:{{ c.line }}</code>
              <button
                class="btn-ghost-red"
                @click="removeComment(idx)"
                :data-testid="`remove-comment-${idx}`"
              >
                Remove
              </button>
            </div>
            <textarea
              v-model="c.body"
              @input="markDirty"
              class="comment-body"
              rows="3"
              :data-testid="`comment-body-${idx}`"
            ></textarea>
          </li>
        </ul>
      </section>

      <!-- Summary note -->
      <section class="summary-section">
        <h2>Summary note (optional)</h2>
        <textarea
          v-model="editedSummary"
          @input="markDirty"
          rows="4"
          placeholder="Overall feedback that will appear as a top-level PR comment…"
          class="summary-textarea"
          data-testid="summary-textarea"
        ></textarea>
      </section>

      <!-- Send / Resume controls -->
      <footer class="detail-footer">
        <div class="footer-meta">
          <span v-if="store.activeSession.docent_review_time_seconds">
            {{ Math.round(store.activeSession.docent_review_time_seconds / 60) }} min reviewed
          </span>
          <span v-if="store.activeSession.state === 'partial'" class="text-orange-400">
            {{ store.activeSession.posted_comments.length }} comments already posted
          </span>
        </div>
        <div class="footer-actions">
          <button
            @click="onSave"
            :disabled="!dirty || savingEdits"
            class="btn-secondary"
            data-testid="save-btn"
          >
            Save
          </button>
          <button
            v-if="store.activeSession.state === 'partial'"
            @click="onResume"
            :disabled="sendInFlight"
            class="btn-primary"
            data-testid="resume-btn"
          >
            {{ sendInFlight ? 'Resuming…' : 'Resume send' }}
          </button>
          <button
            v-else
            @click="onSend"
            :disabled="!canSend || sendInFlight"
            class="btn-primary"
            data-testid="send-btn"
          >
            {{ sendInFlight ? 'Sending…' : 'Send to student' }}
          </button>
        </div>
      </footer>

      <!-- Send-result banners -->
      <div v-if="sendResult" class="send-result" :class="`result-${sendResult.kind || 'success'}`">
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import { useGradingStore, type GradingComment, type SessionState } from '@/stores/grading';

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

const canSend = computed(() => {
  const st = store.activeSession?.state;
  if (!st) return false;
  return ['drafted', 'reviewing'].includes(st);
});

onMounted(async () => {
  await store.fetchSession(id.value);
  hydrateEdits();
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
</script>

<style scoped>
.grading-detail {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgb(30 41 59);
  margin-bottom: 1.5rem;
}

.header-meta {
  flex: 1;
  min-width: 0;
}

.link {
  color: rgb(147 197 253);
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.state-badge {
  padding: 0.25rem 0.6rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}

.state-badge.state-drafted { background: rgb(59 130 246 / 0.2); color: rgb(147 197 253); }
.state-badge.state-reviewing { background: rgb(234 179 8 / 0.2); color: rgb(253 224 71); }
.state-badge.state-posted { background: rgb(34 197 94 / 0.2); color: rgb(134 239 172); }
.state-badge.state-partial { background: rgb(249 115 22 / 0.2); color: rgb(253 186 116); }
.state-badge.state-failed { background: rgb(239 68 68 / 0.2); color: rgb(252 165 165); }

.btn-ghost {
  background: transparent;
  border: none;
  color: rgb(148 163 184);
  cursor: pointer;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
}

.btn-ghost:hover {
  color: rgb(226 232 240);
}

.btn-ghost-red {
  background: transparent;
  border: none;
  color: rgb(248 113 113);
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-primary {
  background: rgb(99 102 241);
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  border-radius: 0.375rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary:disabled {
  background: rgb(71 85 105);
  cursor: not-allowed;
}

.btn-secondary {
  background: rgb(30 41 59);
  border: 1px solid rgb(71 85 105);
  color: rgb(226 232 240);
  padding: 0.6rem 1.2rem;
  border-radius: 0.375rem;
  cursor: pointer;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.info-banner {
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.info-banner.warning {
  background: rgb(120 53 15 / 0.3);
  border: 1px solid rgb(180 83 9);
  color: rgb(253 186 116);
}

.error-banner {
  background: rgb(127 29 29);
  border: 1px solid rgb(185 28 28);
  color: rgb(254 226 226);
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
}

.draft-prompt {
  padding: 1.5rem;
  background: rgb(30 41 59);
  border-radius: 0.5rem;
  text-align: center;
  margin-bottom: 1.5rem;
}

.draft-prompt p {
  color: rgb(148 163 184);
  margin-bottom: 0.75rem;
}

.rubric-section,
.comments-section,
.summary-section {
  margin-bottom: 2rem;
}

h2 {
  font-size: 1rem;
  font-weight: 600;
  color: rgb(226 232 240);
  margin-bottom: 0.75rem;
}

.rubric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.criterion-card {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
}

.criterion-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.criterion-name {
  font-weight: 500;
  color: rgb(226 232 240);
}

.score-select {
  background: rgb(30 41 59);
  border: 1px solid rgb(51 65 85);
  color: rgb(226 232 240);
  padding: 0.3rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.85rem;
  max-width: 140px;
}

.criterion-evidence {
  font-size: 0.8rem;
  color: rgb(148 163 184);
  font-style: italic;
  margin-top: 0.5rem;
}

.evidence-label {
  font-weight: 600;
  font-style: normal;
}

.comments-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.dirty-indicator {
  font-size: 0.75rem;
  color: rgb(253 186 116);
}

.empty-comments {
  padding: 1rem;
  background: rgb(15 23 42);
  border: 1px dashed rgb(51 65 85);
  border-radius: 0.5rem;
  color: rgb(148 163 184);
  font-size: 0.9rem;
}

.comment-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.comment-card {
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
  padding: 0.75rem;
}

.comment-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.comment-location {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 0.8rem;
  color: rgb(147 197 253);
  background: rgb(30 41 59);
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
}

.comment-body {
  width: 100%;
  background: rgb(2 6 23);
  border: 1px solid rgb(51 65 85);
  color: rgb(226 232 240);
  padding: 0.5rem;
  border-radius: 0.375rem;
  font-family: inherit;
  font-size: 0.9rem;
  resize: vertical;
}

.summary-textarea {
  width: 100%;
  background: rgb(2 6 23);
  border: 1px solid rgb(51 65 85);
  color: rgb(226 232 240);
  padding: 0.75rem;
  border-radius: 0.375rem;
  font-family: inherit;
  font-size: 0.9rem;
  resize: vertical;
}

.detail-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 1.5rem;
  border-top: 1px solid rgb(30 41 59);
  margin-top: 1.5rem;
}

.footer-meta {
  color: rgb(148 163 184);
  font-size: 0.875rem;
}

.footer-actions {
  display: flex;
  gap: 0.75rem;
}

.send-result {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.9rem;
}

.send-result.result-success,
.send-result:not([class*="result-"]) {
  background: rgb(22 101 52 / 0.3);
  border: 1px solid rgb(34 197 94);
  color: rgb(187 247 208);
}

.send-result.result-partial {
  background: rgb(154 52 18 / 0.3);
  border: 1px solid rgb(234 88 12);
  color: rgb(254 215 170);
}

.send-result.result-pr_closed,
.send-result.result-github_auth,
.send-result.result-github_failed,
.send-result.result-network {
  background: rgb(127 29 29 / 0.3);
  border: 1px solid rgb(185 28 28);
  color: rgb(254 202 202);
}

.skeleton-detail {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.skeleton-row {
  height: 3rem;
  background: rgb(30 41 59);
  border-radius: 0.5rem;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
