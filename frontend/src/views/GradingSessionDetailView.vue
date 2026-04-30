<template>
  <AppShell>
    <div class="p-6 flex-1">
      <div class="max-w-[1400px] mx-auto flex flex-col gap-5 xl:mr-[400px]">
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
            v-if="store.activeSession && (store.activeSession as any).total_iterations > 1"
            class="px-2.5 py-1 rounded-md text-[11px] uppercase tracking-widest font-semibold bg-tertiary/15 text-tertiary"
            data-testid="iteration-pill"
          >
            Iteratie {{ (store.activeSession as any).iteration_number }} van
            {{ (store.activeSession as any).total_iterations }}
          </span>
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
          <!-- PR closed/merged cascade-discard banner -->
          <div
            v-if="prClosedDiscardKind === 'pr_closed_by_student'"
            class="rounded-xl border border-outline-variant/20 bg-surface-container-low text-on-surface-variant px-4 py-3 text-sm flex items-start gap-3"
            data-testid="pr-closed-discard-banner"
          >
            <span class="material-symbols-rounded text-on-surface-variant mt-0.5" aria-hidden="true">warning</span>
            <div class="flex flex-col gap-1">
              <strong class="text-on-surface">Iteratie afgebroken</strong>
              <span>
                De PR is gesloten door de student voordat je deze iteratie kon afronden.
                Het concept blijft bewaard ter referentie maar kan niet meer verzonden worden.
              </span>
            </div>
          </div>
          <div
            v-else-if="prClosedDiscardKind === 'pr_merged'"
            class="rounded-xl border border-outline-variant/20 bg-surface-container-low text-on-surface-variant px-4 py-3 text-sm flex items-start gap-3"
            data-testid="pr-merged-discard-banner"
          >
            <span class="material-symbols-rounded text-on-surface-variant mt-0.5" aria-hidden="true">check_circle</span>
            <div class="flex flex-col gap-1">
              <strong class="text-on-surface">PR is gemerged</strong>
              <span>
                De student heeft deze PR gemerged voordat deze iteratie afgerond was.
                Het concept blijft bewaard ter referentie maar kan niet meer verzonden worden.
              </span>
            </div>
          </div>

          <!-- Truncated banner -->
          <div
            v-if="store.activeSession.ai_draft_truncated"
            class="bg-tertiary/10 border border-tertiary/30 text-tertiary px-4 py-3 rounded-lg text-sm"
            data-testid="truncated-banner"
          >
            De diff is afgekapt voor de AI-beoordeling. Controleer zorgvuldig.
          </div>

          <!-- Student-side gate: students must not see the docent's draft
               during drafted / reviewing / sending states. They get a clear
               "wachten op feedback" placeholder until the docent hits Send
               and the session lands in `posted`. The list view also blocks
               navigation to non-posted sessions, but a student could still
               URL-hop here, so we gate at the detail level too. -->
          <div
            v-if="
              readOnlyStudent
                && !['posted', 'partial', 'discarded', 'failed', 'pending', 'drafting'].includes(store.activeSession.state)
            "
            class="glass-panel p-10 rounded-xl flex flex-col items-center justify-center gap-4 text-center"
            data-testid="student-waiting-for-feedback"
          >
            <span
              class="material-symbols-rounded text-5xl text-primary"
              aria-hidden="true"
            >hourglass_empty</span>
            <div class="flex flex-col gap-2 max-w-md">
              <p class="text-on-surface font-semibold text-lg">
                Wacht op feedback van docent
              </p>
              <p class="text-sm text-on-surface-variant">
                Je PR is binnengekomen en LEERA heeft een concept-feedback opgesteld voor je docent. Zodra je docent de feedback heeft nagekeken en verstuurd, zie je hem hier.
              </p>
              <p class="text-xs text-outline mt-2">
                Status: {{ store.activeSession.state === 'drafted' ? 'klaar voor docent-review' : 'docent kijkt na' }}
              </p>
            </div>
          </div>

          <!-- Auto-draft loading state (PENDING auto-fires, DRAFTING is in-progress).
               Skeleton-shimmer aesthetic: a faux list of "findings being
               written" — two rows with a square icon block + title/subtitle
               lines, each pulsing with a diagonal shimmer sweep. Sits in
               the middle of the page, no card, no background. Reads as
               "Leera is drafting your feedback right now". -->
          <div
            v-else-if="
              store.activeSession.state === 'pending'
                || store.activeSession.state === 'drafting'
            "
            class="flex flex-col items-center justify-center gap-8 py-24"
            data-testid="draft-loading"
          >
            <div class="leera-skel" aria-hidden="true">
              <div class="leera-skel__row">
                <div class="leera-skel__icon"></div>
                <div class="leera-skel__lines">
                  <div class="leera-skel__line leera-skel__line--lg"></div>
                  <div class="leera-skel__line leera-skel__line--md"></div>
                </div>
              </div>
              <div class="leera-skel__row">
                <div class="leera-skel__icon"></div>
                <div class="leera-skel__lines">
                  <div class="leera-skel__line leera-skel__line--md"></div>
                  <div class="leera-skel__line leera-skel__line--lg"></div>
                </div>
              </div>
              <div class="leera-skel__row">
                <div class="leera-skel__icon"></div>
                <div class="leera-skel__lines">
                  <div class="leera-skel__line leera-skel__line--lg"></div>
                  <div class="leera-skel__line leera-skel__line--sm"></div>
                </div>
              </div>
            </div>

            <div class="flex flex-col gap-1.5 max-w-md text-center">
              <p class="text-on-surface font-semibold">
                Leera analyseert deze PR… dit duurt ongeveer 30 seconden.
              </p>
              <p class="text-xs text-on-surface-variant">
                Je kunt dit scherm openhouden of later terugkomen.
              </p>
            </div>
          </div>

          <!-- Failed state: manual retry -->
          <div
            v-else-if="store.activeSession.state === 'failed'"
            class="rounded-xl border border-error/20 bg-error/10 p-6 flex flex-col gap-3 items-start"
            data-testid="draft-failed"
          >
            <div class="flex items-center gap-2 text-error">
              <span class="material-symbols-rounded" aria-hidden="true">error</span>
              <p class="font-semibold">
                Er ging iets mis bij het analyseren. Klik om opnieuw te proberen.
              </p>
            </div>
            <button
              @click="onGenerateDraft"
              :disabled="draftInFlight"
              class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ draftInFlight ? 'Opnieuw proberen…' : 'Opnieuw proberen' }}
            </button>
          </div>

          <!-- No draft yet (rare: state is past pending but draft never generated) -->
          <div
            v-else-if="!store.activeSession.ai_draft_generated_at"
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

            <StudentHeaderChip
              :name="store.activeSession.student_name || store.activeSession.student_email"
              :email="store.activeSession.student_email"
              :branch="headBranch"
              :student-id="studentId"
              :cohort-name="cohortName"
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
                  :repo-full-name="store.activeSession.repo_full_name"
                  @update-comment="onCommentUpdate"
                  @remove-comment="removeComment"
                />
              </template>
            </section>

            <!-- Rubric fallback for below-xl viewports (sidebar is hidden there) -->
            <div class="xl:hidden">
              <RubricPanel
                :criteria="store.activeSession.rubric_snapshot.criteria"
                :scores="editedScores"
                :editable="canEdit"
                :course-name="store.activeSession.course_name"
                :cohort-name="cohortName"
                @update-score="setScore"
              />
            </div>

            <!-- Summary notes + bottom action row (teacher composer only) -->
            <section
              v-if="!readOnlyStudent"
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
                    v-if="store.activeSession.state === 'partial' && !prClosedDiscardKind"
                    @click="onResume"
                    :disabled="sendInFlight"
                    class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    data-testid="resume-btn"
                  >
                    {{ sendInFlight ? 'Hervatten…' : 'Hervat verzenden' }}
                  </button>
                  <button
                    v-else-if="!prClosedDiscardKind"
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

            <!-- Student read-only footer: feedback summary + GitHub link -->
            <section
              v-else
              class="rounded-xl border border-outline-variant/10 bg-surface-container-low p-5 flex flex-col gap-3"
              data-testid="student-readonly-footer"
            >
              <div class="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 class="text-base font-bold text-on-surface m-0">
                  Feedback van je docent
                </h2>
                <span
                  v-if="store.activeSession.state === 'posted' && store.activeSession.posted_at"
                  class="text-xs text-on-surface-variant"
                >
                  Geplaatst op {{ formatPostedDate(store.activeSession.posted_at) }}
                </span>
              </div>
              <p
                v-if="store.activeSession.final_summary"
                class="text-sm text-on-surface leading-relaxed m-0 whitespace-pre-line"
                data-testid="student-summary"
              >{{ store.activeSession.final_summary }}</p>
              <p
                v-else
                class="text-sm text-on-surface-variant italic m-0"
              >
                Geen samenvatting van de docent — alle feedback staat als comments
                bij de regels hierboven en op GitHub.
              </p>
              <div class="flex gap-3 flex-wrap pt-1">
                <a
                  v-if="store.activeSession.pr_url"
                  :href="store.activeSession.pr_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="primary-gradient text-on-primary px-5 py-2.5 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-95"
                  data-testid="view-on-github-btn"
                >
                  <span class="material-symbols-outlined text-sm">open_in_new</span>
                  Bekijk op GitHub
                </a>
                <button
                  @click="goBack"
                  class="bg-surface-container hover:bg-surface-container-high text-on-surface px-5 py-2.5 rounded-lg text-sm font-medium border border-outline-variant/20 transition-colors"
                >Terug</button>
              </div>
            </section>

            <!-- Vorige iteraties van deze PR -->
            <section
              v-if="previousIterations.length > 0"
              class="rounded-xl border border-outline-variant/10 bg-surface-container-low p-4 flex flex-col gap-3"
              data-testid="previous-iterations"
            >
              <h2
                class="text-[11px] font-bold uppercase tracking-widest text-on-surface-variant"
              >Vorige iteraties van deze PR</h2>
              <ul class="flex flex-col gap-2">
                <li
                  v-for="prev in previousIterations"
                  :key="prev.id"
                  class="flex items-center gap-3 bg-surface-container-lowest border border-outline-variant/10 rounded-lg px-3 py-2 text-sm"
                  :data-testid="`prev-iter-${prev.id}`"
                >
                  <span class="font-semibold text-on-surface">
                    Iteratie {{ prev.iteration_number }}
                  </span>
                  <span
                    class="px-2 py-0.5 rounded-md text-[10px] uppercase tracking-widest font-semibold"
                    :class="stateBadgeClass(prev.state)"
                  >{{ stateLabel(prev.state) }}</span>
                  <span
                    v-if="prev.eindbeoordeling !== null && prev.eindbeoordeling !== undefined"
                    class="text-xs text-on-surface-variant"
                  >
                    Eindbeoordeling {{ prev.eindbeoordeling }}
                  </span>
                  <span v-if="prev.posted_at" class="text-xs text-on-surface-variant">
                    · {{ formatDutchDate(prev.posted_at) }}
                  </span>
                  <button
                    @click="router.push({ name: 'grading-session-detail', params: { id: prev.id } })"
                    class="ml-auto text-xs text-primary hover:underline"
                  >Bekijk →</button>
                </li>
              </ul>
            </section>

            <!-- Start nieuwe iteratie — manual teacher override -->
            <div
              v-if="showNewIterationStrip"
              class="rounded-xl border border-outline-variant/10 bg-surface-container-low px-4 py-3 flex flex-wrap items-center gap-3"
              data-testid="new-iteration-strip"
            >
              <div class="text-xs text-on-surface-variant flex-1 min-w-0">
                <span v-if="canStartNewIteration">
                  Student is terug aan het werk. Start een nieuwe iteratie om opnieuw te beoordelen.
                </span>
                <span v-else-if="activeSession?.submission?.status === 'graded'">
                  PR is al gemerged — geen nieuwe iteratie mogelijk.
                </span>
                <span v-else-if="activeSession?.superseded_by">
                  Deze iteratie is al vervangen. Open de nieuwste iteratie.
                </span>
                <span v-else>
                  Nieuwe iteratie starten is nog niet beschikbaar voor deze sessie.
                </span>
              </div>
              <button
                @click="onStartNewIteration"
                :disabled="!canStartNewIteration || newIterationInFlight"
                :title="newIterationTooltip"
                class="bg-surface-container hover:bg-surface-container-high text-on-surface px-4 py-2 rounded-lg text-sm font-semibold border border-outline-variant/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="new-iteration-btn"
              >
                {{ newIterationInFlight ? 'Nieuwe iteratie starten…' : 'Start nieuwe iteratie' }}
              </button>
            </div>

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
      <RightSidebar
        v-if="
          store.activeSession
            && store.activeSession.ai_draft_generated_at
            && fileList.length > 0
        "
        :files="fileList"
        :criteria="store.activeSession.rubric_snapshot.criteria"
        :scores="editedScores"
        :editable="canEdit"
        :course-name="store.activeSession.course_name"
        :cohort-name="cohortName"
        @update-score="setScore"
      />
    </div>

  </AppShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import { useGradingStore, type GradingComment, type SessionState } from '@/stores/grading';
import { api } from '@/composables/useApi';
import StudentHeaderChip from '@/components/grading/StudentHeaderChip.vue';
import ContributorsList from '@/components/grading/ContributorsList.vue';
import RubricPanel from '@/components/grading/RubricPanel.vue';
import DiffInlineViewer from '@/components/grading/DiffInlineViewer.vue';
import RightSidebar from '@/components/grading/RightSidebar.vue';
import AppShell from '@/components/layout/AppShell.vue';
import { useAuthStore } from '@/stores/auth';
import { storeToRefs } from 'pinia';

const route = useRoute();
const router = useRouter();
const store = useGradingStore();

// Role gating: this view is shared between teachers (compose / edit / send)
// and students (read-only feedback view of their own posted PR). Backend
// returns the same JSON shape; the difference is purely UI affordances.
const auth = useAuthStore();
const { isTeacher, isSchoolAdmin, isSuperuser, isStudent } = storeToRefs(auth);
const isStaff = computed(() => isTeacher.value || isSchoolAdmin.value || isSuperuser.value);
// Students get a read-only render with no Save/Send/Discard, no autosave,
// no draft kickoff on mount, and no edit affordance on comments or rubric.
const readOnlyStudent = computed(() => isStudent.value && !isStaff.value);

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
const draftPollTimer = ref<number | null>(null);

const id = computed(() => Number(route.params.id));
const studentId = ref<number | null>(null);
const headBranch = ref<string | null>(null);
const cohortName = ref<string | null>(null);

const prClosedDiscardKind = computed<'pr_closed_by_student' | 'pr_merged' | null>(() => {
  const s: any = store.activeSession;
  if (!s || s.state !== 'discarded') return null;
  const reason = s.partial_post_error?.reason;
  if (reason === 'pr_closed_by_student' || reason === 'pr_merged') return reason;
  return null;
});

const EDITABLE_STATES = new Set<SessionState>(['drafted', 'reviewing', 'partial']);
const canEdit = computed(() => {
  // Students never edit. Mirrors backend gate on PATCH /sessions/<id>/.
  if (readOnlyStudent.value) return false;
  if (prClosedDiscardKind.value) return false;
  const st = store.activeSession?.state;
  return st ? EDITABLE_STATES.has(st) : false;
});

const canSend = computed(() => {
  if (readOnlyStudent.value) return false;
  if (prClosedDiscardKind.value) return false;
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

const fileList = computed<{ path: string; isAdded: boolean }[]>(() => {
  const seen = new Set<string>();
  const out: { path: string; isAdded: boolean }[] = [];
  for (const c of editedComments.value) {
    const f = c.file || '(unknown)';
    if (seen.has(f)) continue;
    seen.add(f);
    // Heuristic: we don't have PR diff metadata here, so mark as "modified"
    // (the pencil icon). If future backend work adds an `added` hint we can
    // surface it via a plus icon — for now keep it calm and uniform.
    out.push({ path: f, isAdded: false });
  }
  return out;
});

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
  if (!subId) { studentId.value = null; headBranch.value = null; return; }
  try {
    const { data } = await api.grading.submissions.get(subId);
    studentId.value = data?.student ?? null;
    headBranch.value = data?.head_branch ?? null;
    // Try to pull cohort name for the rubric section header (J2 detection).
    const courseId = data?.course;
    if (courseId) {
      try {
        const { data: course } = await api.grading.courses.get(courseId);
        cohortName.value = course?.cohort_name ?? null;
      } catch { /* non-fatal */ }
    }
  } catch {
    studentId.value = null;
    headBranch.value = null;
  }
}

onMounted(async () => {
  await store.fetchSession(id.value);
  hydrateEdits();
  loadStudentIdFromSubmission();
  // Auto-fire draft if session is still PENDING — teacher shouldn't have to
  // click a button; they opened this PR because they want feedback. None of
  // these state transitions are valid for a student viewer; backend would
  // 403 anyway, but skipping the call keeps the network log clean and
  // avoids spurious error toasts.
  if (readOnlyStudent.value) {
    return;
  }
  if (store.activeSession?.state === 'pending') {
    autoStartDraft();
  } else if (store.activeSession?.state === 'drafting') {
    // Mid-flight from a previous session / other tab — just poll.
    startDraftPolling();
  } else if (store.activeSession?.state === 'drafted') {
    try { await store.startReview(id.value); } catch { /* non-fatal */ }
  }
});

onBeforeUnmount(() => {
  if (autosaveTimer.value) window.clearTimeout(autosaveTimer.value);
  stopDraftPolling();
});

function stopDraftPolling() {
  if (draftPollTimer.value) {
    window.clearInterval(draftPollTimer.value);
    draftPollTimer.value = null;
  }
}

function startDraftPolling() {
  stopDraftPolling();
  draftPollTimer.value = window.setInterval(async () => {
    try {
      await store.fetchSession(id.value);
      const st = store.activeSession?.state;
      if (st === 'drafted' || st === 'reviewing' || st === 'partial' || st === 'posted') {
        stopDraftPolling();
        hydrateEdits();
        if (st === 'drafted') {
          try { await store.startReview(id.value); } catch { /* non-fatal */ }
        }
      } else if (st === 'failed') {
        stopDraftPolling();
      }
    } catch {
      /* keep polling on transient error */
    }
  }, 4000);
}

async function autoStartDraft() {
  if (draftInFlight.value) return;
  draftInFlight.value = true;
  startDraftPolling();
  try {
    await store.generateDraft(id.value);
    // generateDraft usually returns with DRAFTED already; hydrate and stop.
    stopDraftPolling();
    hydrateEdits();
    if (store.activeSession?.state === 'drafted') {
      try { await store.startReview(id.value); } catch { /* non-fatal */ }
    }
  } catch {
    // Let the poller pick up DRAFTED/FAILED; if the call itself threw and
    // state is still pending, also stop polling so the failed card renders.
    if (store.activeSession?.state !== 'drafting') stopDraftPolling();
  } finally {
    draftInFlight.value = false;
  }
}

onBeforeRouteLeave(async (_to, _from, next) => {
  // Students have nothing to save; their edits aren't even allowed by the
  // backend. Skip the save attempt to avoid a guaranteed 403 on navigation.
  if (readOnlyStudent.value) {
    next();
    return;
  }
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

const newIterationInFlight = ref(false);

const TERMINAL_STATES = new Set<SessionState>(['posted', 'partial', 'failed', 'discarded']);

const prIsMerged = computed(() => {
  // Backend marks Submission.status = 'graded' when PR is merged.
  // The detail serializer doesn't include submission.status directly; we
  // infer via activity_since_posted being absent + a refresh will fetch
  // fresh data. Conservative: if backend says we can't start, we can't.
  const s: any = store.activeSession;
  return !!(s && s._submission_graded);
});

const showNewIterationStrip = computed(() => {
  // Students never trigger iterations; this is a teacher-only manual
  // override (the start_new_iteration endpoint is gated on IsTeacher).
  if (readOnlyStudent.value) return false;
  const s: any = store.activeSession;
  if (!s) return false;
  if (!TERMINAL_STATES.has(s.state as SessionState)) return false;
  if (s.superseded_by) return false;
  // PR is closed/merged — there is nothing to iterate on. The cascade-discard
  // banner already explains this; don't double up with the strip.
  if (prClosedDiscardKind.value) return false;
  return true;
});

const canStartNewIteration = computed(() => {
  const s: any = store.activeSession;
  return !!(s && s.can_start_new_iteration);
});

const newIterationTooltip = computed(() => {
  if (canStartNewIteration.value) return '';
  const s: any = activeSession.value;
  if (s?.submission?.status === 'graded') return 'PR is al gemerged — geen nieuwe iteratie mogelijk.';
  if (s?.superseded_by) return 'Deze iteratie is al vervangen — open de nieuwste.';
  return 'Nieuwe iteratie nog niet beschikbaar voor deze sessie.';
});

async function onStartNewIteration() {
  if (!canStartNewIteration.value || newIterationInFlight.value) return;
  newIterationInFlight.value = true;
  try {
    const result: any = await (store as any).startNewIteration(id.value);
    if (result?.session_id) {
      router.push({ name: 'grading-session-detail', params: { id: result.session_id } });
    }
  } catch (err) {
    console.error('start_new_iteration failed', err);
  } finally {
    newIterationInFlight.value = false;
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
  // Teachers go back to the inbox; students don't have access to it (the
  // viewset is teacher-only). Send them home — the dashboard or their
  // own PR list, whichever the router knows about.
  if (readOnlyStudent.value) {
    router.push({ name: 'dashboard' }).catch(() => {
      router.push('/');
    });
    return;
  }
  router.push({ name: 'grading-inbox' });
}

function formatPostedDate(iso: string): string {
  // Match the Dutch teacher-facing date format used elsewhere
  // ("25 apr 2026"). Fallback to the raw string on parse error so we
  // never crash the read-only view because of a bad date.
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('nl-NL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

interface PreviousIteration {
  id: number;
  iteration_number: number;
  state: SessionState;
  eindbeoordeling: number | null;
  posted_at: string | null;
  created_at: string | null;
}

const previousIterations = computed<PreviousIteration[]>(() => {
  const s: any = store.activeSession;
  if (!s) return [];
  return (s.previous_iterations || []) as PreviousIteration[];
});

function formatDutchDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('nl-NL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
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

<style scoped>
/* Skeleton-shimmer loader. Three rows, each: square icon + 2 lines of
   varying widths. A diagonal shimmer sweep moves left→right across the
   whole block, giving the "content is being drafted" feel. No card, no
   background — sits transparent on the page. */

.leera-skel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: min(360px, 80vw);
  overflow: hidden;
  user-select: none;
  padding: 4px 0;
}

.leera-skel__row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.leera-skel__icon {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
}

.leera-skel__lines {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.leera-skel__line {
  height: 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
}

.leera-skel__line--lg { width: 80%; }
.leera-skel__line--md { width: 55%; }
.leera-skel__line--sm { width: 35%; }

/* Shimmer sweep — a diagonal gradient slab moves L→R over the whole
   skeleton. We layer it as an absolute pseudo-element on the container
   so it brightens every block proportionally as it passes. */
.leera-skel::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 0%,
    transparent 35%,
    rgba(255, 255, 255, 0.08) 50%,
    transparent 65%,
    transparent 100%
  );
  background-size: 200% 100%;
  background-position: -100% 0;
  animation: leera-shimmer 1.6s ease-in-out infinite;
  pointer-events: none;
}

@keyframes leera-shimmer {
  0%   { background-position: -100% 0; }
  100% { background-position: 100% 0; }
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
  .leera-skel::before {
    animation-duration: 4s;
  }
}
</style>
