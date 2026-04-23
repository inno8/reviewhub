<template>
  <AppShell>
    <div class="p-6 flex-1">
      <div class="max-w-[1400px] mx-auto flex flex-col gap-5">
        <!-- Header -->
        <header
          class="flex flex-wrap items-center gap-4 pb-4 border-b border-outline-variant/10"
        >
          <button
            @click="goBack"
            class="p-2 hover:bg-surface-container rounded-lg transition-colors"
            data-testid="back-btn"
            aria-label="Terug naar inbox"
          >
            <span
              class="material-symbols-rounded text-on-surface-variant"
              aria-hidden="true"
            >arrow_back</span>
          </button>
          <div class="flex-1 min-w-0" v-if="store.activeSession">
            <h1 class="text-lg font-bold text-on-surface truncate">
              {{ store.activeSession.student_name || store.activeSession.student_email }}
            </h1>
            <p class="text-xs text-on-surface-variant truncate">
              {{ store.activeSession.course_name }} ·
              <a
                :href="store.activeSession.pr_url"
                target="_blank"
                class="text-primary hover:underline"
              >{{ store.activeSession.pr_title }}</a>
            </p>
          </div>
          <span
            v-if="store.activeSession"
            class="px-2.5 py-1 rounded-md text-[11px] uppercase tracking-widest font-semibold"
            :class="stateBadgeClass(store.activeSession.state)"
          >{{ stateLabel(store.activeSession.state) }}</span>
        </header>

        <!-- Loading -->
        <div
          v-if="store.activeSessionLoading && !store.activeSession"
          class="flex flex-col gap-2"
        >
          <div
            v-for="n in 8"
            :key="n"
            class="h-12 bg-surface-container-low rounded-lg animate-pulse"
          ></div>
        </div>

        <!-- Error -->
        <div
          v-else-if="store.activeSessionError"
          class="bg-error/10 border border-error/20 text-error rounded-lg px-4 py-3 text-sm"
        >{{ store.activeSessionError }}</div>

        <template v-else-if="store.activeSession">
          <!-- Truncated banner -->
          <div
            v-if="store.activeSession.ai_draft_truncated"
            class="bg-tertiary/10 border border-tertiary/30 text-tertiary px-4 py-3 rounded-lg text-sm"
            data-testid="truncated-banner"
          >
            De diff is afgekapt voor de AI-beoordeling. Controleer zorgvuldig.
          </div>

          <!-- Generate-draft prompt -->
          <div
            v-if="
              store.activeSession.state === 'pending'
                || !store.activeSession.ai_draft_generated_at
            "
            class="glass-panel p-6 text-center rounded-xl"
          >
            <p class="text-on-surface-variant mb-3">No AI draft yet.</p>
            <button
              @click="onGenerateDraft"
              :disabled="draftInFlight"
              class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ draftInFlight ? 'Concept opstellen…' : 'Concept opstellen' }}
            </button>
          </div>

          <template v-else>
            <!-- Contributors + student snapshot (side helpers) -->
            <ContributorsList
              v-if="
                store.activeSession.contributors
                  && store.activeSession.contributors.length > 1
              "
              :contributors="store.activeSession.contributors"
            />

            <StudentSnapshotPanel
              v-if="studentId"
              :student-id="studentId"
              :profile-link="true"
            />

            <!-- Rubric panel (horizontal strip — docent-first) -->
            <RubricPanel
              :criteria="store.activeSession.rubric_snapshot.criteria"
              :scores="editedScores"
              :editable="canEdit"
              @update-score="setScore"
            />

            <!-- File + diff viewer: one viewer per file, comments inlined at target line -->
            <section class="flex flex-col gap-4">
              <div class="flex items-center gap-3">
                <h2 class="text-sm font-bold uppercase tracking-widest text-on-surface-variant">
                  Code &amp; commentaar
                </h2>
                <span class="text-xs text-outline" data-testid="comment-count">
                  {{ editedComments.length }} comment{{ editedComments.length === 1 ? '' : 's' }}
                </span>
                <span v-if="dirty" class="text-[11px] text-tertiary ml-auto">niet opgeslagen</span>
                <span v-else-if="savingEdits" class="text-[11px] text-tertiary ml-auto">opslaan…</span>
              </div>

              <div
                v-if="editedComments.length === 0"
                class="p-4 bg-surface-container-low border border-dashed border-outline-variant/30 rounded-xl text-on-surface-variant text-sm"
                data-testid="no-comments"
              >
                De AI heeft geen inline comments geplaatst. Vul hieronder een
                samenvatting in of klik Verzenden met alleen de rubric-scores.
              </div>

              <template v-else>
                <!-- Hidden comment handles so existing tests can still target by index. -->
                <div class="sr-only" aria-hidden="true">
                  <div
                    v-for="(c, idx) in editedComments"
                    :key="`anchor-${idx}`"
                    :data-testid="`comment-${idx}`"
                  >{{ c.file }}:{{ c.line }}</div>
                </div>

                <DiffInlineViewer
                  v-for="group in fileGroups"
                  :key="group.file"
                  :session-id="id"
                  :file-path="group.file"
                  :comments="group.comments"
                  :editable="canEdit"
                  @update-comment="onCommentUpdate"
                  @remove-comment="removeComment"
                />
              </template>
            </section>

            <!-- Summary notes + bottom action row -->
            <section
              class="rounded-xl border border-outline-variant/10 bg-surface-container-low p-4 flex flex-col gap-4"
            >
              <div class="flex flex-col gap-2">
                <label
                  for="grading-summary"
                  class="text-[11px] uppercase tracking-widest text-on-surface-variant font-semibold"
                >Samenvatting (optioneel)</label>
                <textarea
                  id="grading-summary"
                  v-model="editedSummary"
                  @input="markDirty"
                  :disabled="!canEdit"
                  rows="4"
                  placeholder="Overall feedback die bovenaan de PR als comment verschijnt…"
                  class="w-full rounded-md border border-outline-variant/20 bg-surface-container-lowest px-3 py-2 text-sm text-on-surface leading-relaxed focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-60 placeholder:text-outline/50 resize-y"
                  data-testid="summary-textarea"
                ></textarea>
              </div>

              <footer class="flex items-center justify-between gap-4 flex-wrap">
                <div class="text-on-surface-variant text-xs">
                  <span v-if="store.activeSession.docent_review_time_seconds">
                    {{ Math.round(store.activeSession.docent_review_time_seconds / 60) }} min beoordeeld
                  </span>
                  <span
                    v-if="store.activeSession.state === 'partial'"
                    class="text-tertiary"
                  >
                    {{ store.activeSession.posted_comments.length }} comments al geplaatst
                  </span>
                </div>
                <div class="flex gap-3 flex-wrap">
                  <button
                    @click="goBack"
                    class="bg-transparent hover:bg-surface-container text-on-surface-variant px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
                    data-testid="cancel-btn"
                  >Annuleer</button>
                  <button
                    @click="onSave"
                    :disabled="!dirty || savingEdits || !canEdit"
                    class="bg-surface-container hover:bg-surface-container-high text-on-surface px-5 py-2.5 rounded-lg text-sm font-medium border border-outline-variant/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid="save-btn"
                  >Opslaan</button>
                  <button
                    v-if="store.activeSession.state === 'partial'"
                    @click="onResume"
                    :disabled="sendInFlight"
                    class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid="resume-btn"
                  >
                    {{ sendInFlight ? 'Hervatten…' : 'Hervat verzenden' }}
                  </button>
                  <button
                    v-else
                    @click="onSend"
                    :disabled="!canSend || sendInFlight"
                    class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid="send-btn"
                  >
                    {{ sendInFlight ? 'Verzenden…' : 'Verzenden naar student' }}
                  </button>
                </div>
              </footer>
            </section>

            <!-- Send-result banner -->
            <div
              v-if="sendResult"
              class="px-4 py-3 rounded-lg text-sm"
              :class="sendResultClass"
            >
              <template v-if="sendResult.ok">
                <strong>Verzonden.</strong>
                {{ sendResult.summary?.posted_count || 0 }} comments geplaatst
                ({{ sendResult.summary?.skipped_duplicate_count || 0 }} duplicaten overgeslagen).
              </template>
              <template v-else-if="sendResult.kind === 'partial'">
                <strong>Partial post.</strong>
                {{ sendResult.posted_so_far }} comments geplaatst. Klik Hervat om door te gaan.
              </template>
              <template v-else-if="sendResult.kind === 'pr_closed'">
                <strong>PR is gesloten.</strong> Vraag de student de PR weer te openen.
              </template>
              <template v-else-if="sendResult.kind === 'github_auth'">
                <strong>GitHub-authenticatie verlopen.</strong>
                Werk je PAT bij in Instellingen en probeer opnieuw.
              </template>
              <template v-else>
                <strong>Verzenden mislukt.</strong>
                {{ sendResult.message || 'Onbekende fout' }}
              </template>
            </div>
          </template>
        </template>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import { useGradingStore, type GradingComment, type SessionState } from '@/stores/grading';
import { api } from '@/composables/useApi';
import StudentSnapshotPanel from '@/components/grading/StudentSnapshotPanel.vue';
import ContributorsList from '@/components/grading/ContributorsList.vue';
import RubricPanel from '@/components/grading/RubricPanel.vue';
import DiffInlineViewer from '@/components/grading/DiffInlineViewer.vue';
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

const EDITABLE_STATES = new Set<SessionState>(['drafted', 'reviewing', 'partial']);
const canEdit = computed(() => {
  const st = store.activeSession?.state;
  return st ? EDITABLE_STATES.has(st) : false;
});

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

/**
 * Group comments by file, preserving each comment's stable index (the index
 * into editedComments) so the per-comment update/remove handlers can mutate
 * the authoritative array.
 */
interface AnchoredComment extends GradingComment {
  _index: number;
  original_snippet?: string;
  suggested_snippet?: string;
  teacher_explanation?: string;
}

const fileGroups = computed<{ file: string; comments: AnchoredComment[] }[]>(() => {
  const byFile = new Map<string, AnchoredComment[]>();
  editedComments.value.forEach((c, i) => {
    const key = c.file || '(unknown)';
    const anchored: AnchoredComment = { ...(c as AnchoredComment), _index: i };
    if (!byFile.has(key)) byFile.set(key, []);
    byFile.get(key)!.push(anchored);
  });
  return Array.from(byFile.entries()).map(([file, comments]) => ({
    file,
    comments: comments.sort((a, b) => (a.line || 0) - (b.line || 0)),
  }));
});

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

onMounted(async () => {
  await store.fetchSession(id.value);
  hydrateEdits();
  loadStudentIdFromSubmission();
  if (store.activeSession?.state === 'drafted') {
    try { await store.startReview(id.value); } catch { /* non-fatal */ }
  }
});

onBeforeUnmount(() => {
  if (autosaveTimer.value) window.clearTimeout(autosaveTimer.value);
});

onBeforeRouteLeave(async (_to, _from, next) => {
  if (dirty.value && !savingEdits.value) {
    try { await onSave(); } catch { /* continue */ }
  }
  next();
});

watch(() => store.activeSession?.id, () => hydrateEdits());

function hydrateEdits() {
  if (!store.activeSession) return;
  const src = store.activeSession;
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

function setScore(criterionId: string, score: number) {
  const prev = editedScores.value[criterionId] || { score: 0 };
  editedScores.value[criterionId] = { ...prev, score };
  markDirty();
}

function onCommentUpdate(idx: number, patch: Partial<AnchoredComment>) {
  const cur = editedComments.value[idx];
  if (!cur) return;
  // Apply patch only if something actually changed to avoid needless dirty flips.
  let changed = false;
  for (const k of Object.keys(patch) as (keyof AnchoredComment)[]) {
    if ((cur as any)[k] !== (patch as any)[k]) {
      (cur as any)[k] = (patch as any)[k];
      changed = true;
    }
  }
  if (changed) markDirty();
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
    pending: 'in afwachting',
    drafting: 'concept wordt opgesteld…',
    drafted: 'concept klaar',
    reviewing: 'in review',
    sending: 'verzenden…',
    posted: 'verzonden',
    partial: 'gedeeltelijk — hervat',
    failed: 'mislukt',
    discarded: 'weggegooid',
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
