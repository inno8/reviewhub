<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import { useFindingsStore, type Finding } from '@/stores/findings';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-go';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-java';
import 'prismjs/components/prism-kotlin';
import 'prismjs/components/prism-rust';
import 'prismjs/components/prism-ruby';
import 'prismjs/components/prism-csharp';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-php';
import 'prismjs/components/prism-swift';

import { buildSideBySideDiff, type InlineSeg, type SideBySideRow } from '@/utils/fileDiff';

const route = useRoute();
const router = useRouter();
const findingsStore = useFindingsStore();
const auth = useAuthStore();

const findings = ref<Finding[]>([]);
const fileContent = ref<string>('');
const loading = ref(true);
const selectedFindingId = ref<number | null>(null);
const actionLoading = ref(false);
const toastMessage = ref('');

// Track line ranges for each finding
const findingLineRanges = ref<Map<number, { start: number; end: number }>>(new Map());

const filePath = computed(() => route.query.file as string);
const findingIds = computed(() => (route.query.ids as string)?.split(',').map(Number) || []);
const evaluationId = computed(() => route.query.evaluationId ? Number(route.query.evaluationId) : null);

/** File path that `fileContent` was last loaded for (avoids refetch when switching issues in same file). */
const contentSourcePath = ref<string | null>(null);
const viewInitializing = ref(true);

function fallbackFileContentFromSnippets(): string {
  return findings.value.map((f) => f.originalCode || '').join('\n\n// --- Next Issue ---\n\n');
}

/** Load full file via API (GitHub); falls back to stitched original_code snippets if empty or error. */
async function loadFileContentForFinding(findingId: number) {
  const f = findings.value.find((x) => x.id === findingId);
  let content = '';
  try {
    const { data } = await api.findings.getFileContent(findingId);
    content = typeof data?.content === 'string' ? data.content : '';
  } catch {
    content = '';
  }
  const merged = fallbackFileContentFromSnippets();
  if (!content.trim()) {
    content = merged;
  }
  fileContent.value = content;
  contentSourcePath.value = f?.filePath ?? null;
  calculateLineRanges();
}

onMounted(async () => {
  viewInitializing.value = true;
  loading.value = true;
  try {
    const fetchedFindings: Finding[] = [];

    if (evaluationId.value) {
      // Coming from Commit Timeline — fetch evaluation findings
      try {
        const { data } = await api.evaluations.get(evaluationId.value);
        const evalFindings = data.findings || [];
        for (const f of evalFindings) {
          fetchedFindings.push({
            id: f.id,
            title: f.title,
            description: f.description,
            severity: f.severity,
            filePath: f.file_path,
            lineStart: f.line_start,
            lineEnd: f.line_end,
            originalCode: f.original_code,
            suggestedCode: f.suggested_code,
            explanation: f.explanation,
            isFixed: f.is_fixed,
            skills: (f.skills || []).map((s: any) => ({ id: s.id, name: s.name, slug: s.slug })),
          } as Finding);
        }
      } catch (e) {
        console.error('Failed to load evaluation findings:', e);
      }
    } else {
      // Coming from Dashboard — use finding IDs from query
      for (const id of findingIds.value) {
        await findingsStore.fetchFinding(id);
        if (findingsStore.selectedFinding) {
          fetchedFindings.push({ ...findingsStore.selectedFinding });
        }
      }
    }

    findings.value = fetchedFindings;

    if (findings.value.length > 0) {
      selectedFindingId.value = findings.value[0].id;
      await loadFileContentForFinding(findings.value[0].id);
    }
  } finally {
    loading.value = false;
    viewInitializing.value = false;
  }
});

watch(selectedFindingId, async (id) => {
  if (viewInitializing.value || id == null) return;
  const f = findings.value.find((x) => x.id === id);
  if (!f) return;
  const path = f.filePath || '';
  if (path && path === contentSourcePath.value && (fileContent.value || '').trim()) {
    calculateLineRanges();
    return;
  }
  loading.value = true;
  try {
    await loadFileContentForFinding(id);
  } finally {
    loading.value = false;
  }
});

function normalizeLineForMatch(raw: string): string {
  return (raw ?? '').replace(/\s+/g, ' ').trim();
}

/** Locate original_code in the file; uses normalized lines for resilient matching. */
function findSnippetRangeInFile(
  fileLines: string[],
  originalCode: string,
): { start: number; end: number } | null {
  const snippetLines = (originalCode || '')
    .split(/\r?\n/)
    .map(normalizeLineForMatch)
    .filter((l) => l.length > 0);
  if (snippetLines.length === 0) return null;

  const n = fileLines.length;
  const m = snippetLines.length;

  for (let i = 0; i <= n - m; i++) {
    let ok = true;
    for (let j = 0; j < m; j++) {
      if (normalizeLineForMatch(fileLines[i + j] ?? '') !== snippetLines[j]) {
        ok = false;
        break;
      }
    }
    if (ok) return { start: i, end: i + m - 1 };
  }

  // Fallback: first line only (narrow); caller may union with API range
  if (m >= 1) {
    const first = snippetLines[0];
    for (let i = 0; i < n; i++) {
      if (normalizeLineForMatch(fileLines[i] ?? '') === first) {
        return { start: i, end: i };
      }
    }
  }
  return null;
}

/**
 * Grow [start,end] so every non-empty line in original_code matches consecutive file lines.
 * Fixes LLM storing line_start=line_end=1 while original_code lists the whole block.
 */
function extendRangeToCoverOriginalCodeLines(
  fileLines: string[],
  start: number,
  end: number,
  originalCode: string,
): { start: number; end: number } {
  const parts = (originalCode || '')
    .split(/\r?\n/)
    .map(normalizeLineForMatch)
    .filter((l) => l.length > 0);
  if (parts.length === 0 || start < 0) return { start, end };

  let e = end;
  for (let k = 0; k < parts.length; k++) {
    const fi = start + k;
    if (fi >= fileLines.length) break;
    if (normalizeLineForMatch(fileLines[fi] ?? '') !== parts[k]) break;
    e = fi;
  }
  return { start, end: Math.max(end, e) };
}

/**
 * LLM sometimes stores only the first line in original_code while the suggestion replaces a whole block.
 * When suggestion is multi-line, expand a single-line range downward (capped) so red/green line up.
 */
function expandRangeForMultilineSuggestion(
  fileLines: string[],
  start: number,
  end: number,
  originalCode: string,
  suggestedCode: string,
): { start: number; end: number } {
  const origLines = (originalCode || '')
    .split(/\r?\n/)
    .map(normalizeLineForMatch)
    .filter((l) => l.length > 0);
  const suggLines = (suggestedCode || '').split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (origLines.length !== 1 || start !== end || suggLines.length < 2) {
    return { start, end };
  }
  const len = fileLines.length;
  const greedyEnd = Math.min(
    len - 1,
    start + Math.max(suggLines.length + 6, 12) - 1,
  );
  return { start, end: Math.max(end, greedyEnd) };
}

function calculateLineRanges() {
  const fileLines = fileContent.value.split('\n');
  const len = fileLines.length;
  const ranges = new Map<number, { start: number; end: number }>();

  findings.value.forEach((finding) => {
    const ls = finding.lineStart;
    const le = finding.lineEnd;
    let apiStart = -1;
    let apiEnd = -1;
    if (ls != null && le != null && ls >= 1 && le >= ls) {
      apiStart = Math.min(Math.max(0, len - 1), Math.floor(ls) - 1);
      apiEnd = Math.min(Math.max(apiStart, len - 1), Math.floor(le) - 1);
    }

    const snippetRange = findSnippetRangeInFile(fileLines, finding.originalCode);

    let start = -1;
    let end = -1;
    if (apiStart >= 0 && snippetRange) {
      start = Math.min(apiStart, snippetRange.start);
      end = Math.max(apiEnd, snippetRange.end);
    } else if (snippetRange) {
      start = snippetRange.start;
      end = snippetRange.end;
    } else if (apiStart >= 0) {
      start = apiStart;
      end = apiEnd;
    }

    if (start < 0) return;

    let grown = extendRangeToCoverOriginalCodeLines(fileLines, start, end, finding.originalCode);
    start = grown.start;
    end = Math.min(len - 1, grown.end);

    grown = expandRangeForMultilineSuggestion(
      fileLines,
      start,
      end,
      finding.originalCode,
      finding.optimizedCode,
    );
    start = grown.start;
    end = Math.min(len - 1, grown.end);

    if (start <= end) {
      ranges.set(finding.id, { start, end });
    }
  });

  findingLineRanges.value = ranges;
}

const selectedFinding = computed(() => 
  findings.value.find(f => f.id === selectedFindingId.value) || null
);

const branch = computed(() => selectedFinding.value?.review?.branch || 'main');

/** Path used to detect language (Prism) for syntax highlighting. */
const diffSourcePath = computed(
  () =>
    contentSourcePath.value ||
    (route.query.file as string) ||
    selectedFinding.value?.filePath ||
    '',
);

const diffPrismLanguage = computed(() => {
  const path = diffSourcePath.value;
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  const langMap: Record<string, string> = {
    html: 'markup',
    htm: 'markup',
    vue: 'markup',
    xml: 'markup',
    svg: 'markup',
    js: 'javascript',
    mjs: 'javascript',
    cjs: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    css: 'css',
    scss: 'css',
    less: 'css',
    sass: 'css',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    sh: 'bash',
    bash: 'bash',
    zsh: 'bash',
    go: 'go',
    rs: 'rust',
    java: 'java',
    kt: 'kotlin',
    kts: 'kotlin',
    cs: 'csharp',
    rb: 'ruby',
    php: 'php',
    swift: 'swift',
    sql: 'sql',
    md: 'markdown',
    mdx: 'markdown',
  };
  return langMap[ext] || 'markup';
});

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Prism highlighting by file extension. Lines without inline diff chars get full-line highlight;
 * mixed diff lines keep add/del spans and highlight neutral fragments only.
 */
function highlightDiffSide(segments: InlineSeg[]): string {
  const raw = segments.map((s) => s.text).join('');
  const hasInlineChange = segments.some((s) => s.kind !== 'neutral');

  if (!hasInlineChange) {
    try {
      const langKey = diffPrismLanguage.value;
      const grammar = Prism.languages[langKey];
      if (grammar) {
        return Prism.highlight(raw || ' ', grammar, langKey);
      }
    } catch {
      /* plain fallback */
    }
    return escapeHtml(raw);
  }

  return segments
    .map((s) => {
      if (s.kind === 'del') {
        return `<span class="diff-seg-del">${escapeHtml(s.text)}</span>`;
      }
      if (s.kind === 'add') {
        return `<span class="diff-seg-add">${escapeHtml(s.text)}</span>`;
      }
      try {
        const langKey = diffPrismLanguage.value;
        const grammar = Prism.languages[langKey];
        if (grammar && s.text) {
          return Prism.highlight(s.text, grammar, langKey);
        }
      } catch {
        /* fall through */
      }
      return escapeHtml(s.text);
    })
    .join('');
}

/** Full file text with the selected finding’s suggested code patched in (for diff rh side). */
const mergedOptimizedText = computed(() => {
  const sel = selectedFinding.value;
  const base = fileContent.value || '';
  if (!sel) return base;

  const baseLines = base.split('\n');
  const range = findingLineRanges.value.get(sel.id);
  const suggestedRaw = sel.optimizedCode || '';
  const suggestedLines = suggestedRaw.length ? suggestedRaw.split(/\r?\n/) : [];

  if (range == null) return base;
  if (suggestedLines.length === 0) return base;

  const before = baseLines.slice(0, range.start);
  const after = baseLines.slice(range.end + 1);
  return [...before, ...suggestedLines, ...after].join('\n');
});

const originalLineCount = computed(() =>
  fileContent.value ? fileContent.value.split(/\n/).length : 0,
);
const optimizedLineCount = computed(() =>
  mergedOptimizedText.value ? mergedOptimizedText.value.split(/\n/).length : 0,
);

/** Aligned side-by-side diff: full original vs merged optimized, inline char highlights. */
const diffView = computed(() => {
  const oldStr = fileContent.value || '';
  const newStr = mergedOptimizedText.value || '';
  const selectedId = selectedFindingId.value;
  const { rows, removalRows, additionRows } = buildSideBySideDiff(oldStr, newStr);

  const annotated = rows.map((row: SideBySideRow) => {
    if (row.leftTint !== 'none') return row;
    const ln = row.leftNum;
    if (ln == null) return row;
    const idx = ln - 1;
    for (const [findingId, range] of findingLineRanges.value.entries()) {
      if (findingId === selectedId) continue;
      if (idx >= range.start && idx <= range.end) {
        return { ...row, leftTint: 'other-issue' as const };
      }
    }
    return row;
  });

  return { rows: annotated, removalRows, additionRows };
});

/** Row-level tint is in scoped CSS (`.diff-tr-*`); cells only get a left accent bar. */
function leftLineCellClass(row: SideBySideRow) {
  if (row.leftTint === 'removed') return 'border-l-4 border-l-red-400';
  if (row.leftTint === 'other-issue') return 'border-l-2 border-l-red-400/70';
  return '';
}

function rightLineCellClass(row: SideBySideRow) {
  if (row.rightTint === 'added') return 'border-l-4 border-l-emerald-400';
  return '';
}

function leftTrClass(row: SideBySideRow) {
  if (row.leftTint === 'removed') return 'diff-tr-removed';
  if (row.leftTint === 'other-issue') return 'diff-tr-issue';
  if (!row.leftNum && row.rightNum) return 'diff-tr-pad-left';
  return '';
}

function rightTrClass(row: SideBySideRow) {
  if (row.rightTint === 'added') return 'diff-tr-added';
  if (row.leftNum && !row.rightNum) return 'diff-tr-pad-right';
  return '';
}

function leftGutterClass(row: SideBySideRow) {
  const sticky = 'diff-gutter sticky left-0 z-10 border-r border-outline-variant/20';
  if (row.leftTint === 'removed' || row.leftTint === 'other-issue' || (!row.leftNum && row.rightNum)) return sticky;
  return `${sticky} bg-surface-container-lowest text-outline/45`;
}

function rightGutterClass(row: SideBySideRow) {
  const sticky = 'diff-gutter-opt sticky left-0 z-10 border-r border-outline-variant/20';
  if (row.rightTint === 'added' || (row.leftNum && !row.rightNum)) return sticky;
  return `${sticky} bg-surface-container text-outline/45`;
}

async function copyOriginalFile() {
  try {
    await navigator.clipboard.writeText(fileContent.value || '');
    toastMessage.value = 'Original file copied.';
  } catch {
    toastMessage.value = 'Could not copy.';
  }
}

async function copyOptimizedFile() {
  try {
    await navigator.clipboard.writeText(mergedOptimizedText.value || '');
    toastMessage.value = 'Optimized file copied.';
  } catch {
    toastMessage.value = 'Could not copy.';
  }
}

// Get line range for display
function getLineRange(findingId: number): string {
  const range = findingLineRanges.value.get(findingId);
  if (range) {
    return `Lines ${range.start + 1}-${range.end + 1}`;
  }
  return '';
}

/** Human-readable span for the selected finding (both panels use the same replace window). */
const selectedIssueSpanLabel = computed(() => {
  const id = selectedFindingId.value;
  if (id == null) return '';
  const r = findingLineRanges.value.get(id);
  if (!r) return '';
  const a = r.start + 1;
  const b = r.end + 1;
  return a === b ? `Line ${a} in original file is replaced` : `Lines ${a}-${b} in original file are replaced`;
});

function getCategoryClass(category: string) {
  const cat = category?.toLowerCase().replace('_', '');
  return {
    security: 'bg-error/10 text-error border-error/20',
    performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    codestyle: 'bg-primary/10 text-primary border-primary/20',
    testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
    architecture: 'bg-secondary/10 text-secondary border-secondary/20',
  }[cat] || 'bg-outline/10 text-outline border-outline/20';
}

const originalDiffScrollEl = ref<HTMLElement | null>(null);
const optimizedDiffScrollEl = ref<HTMLElement | null>(null);
let diffScrollSync = false;

function syncDiffScroll(from: 'original' | 'optimized', e: Event) {
  if (diffScrollSync) return;
  const src = e.target as HTMLElement;
  const other =
    from === 'original' ? optimizedDiffScrollEl.value : originalDiffScrollEl.value;
  if (!other) return;
  diffScrollSync = true;
  other.scrollTop = src.scrollTop;
  requestAnimationFrame(() => {
    diffScrollSync = false;
  });
}

async function scrollToIssue(findingId: number) {
  selectedFindingId.value = findingId;

  await nextTick();

  const range = findingLineRanges.value.get(findingId);
  if (!range) return;
  const targetLine = range.start + 1;
  const rows = diffView.value.rows;
  let idx = rows.findIndex((r) => r.leftNum === targetLine);
  if (idx < 0) {
    idx = rows.findIndex((r) => r.leftNum != null && r.leftNum >= targetLine);
  }
  if (idx < 0) idx = 0;
  document.getElementById(`diff-o-${idx}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById(`diff-p-${idx}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function markUnderstood() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.markUnderstood(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) finding.markedUnderstood = data.markedUnderstood;
    toastMessage.value = 'Understanding state saved.';
  } finally {
    actionLoading.value = false;
  }
}

async function requestExplanation() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    await api.findings.requestExplanation(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) finding.explanationRequested = true;
    toastMessage.value = 'Explanation requested via Telegram.';
  } finally {
    actionLoading.value = false;
  }
}

async function applyFix() {
  if (!selectedFindingId.value) return;
  actionLoading.value = true;
  try {
    const { data } = await api.findings.applyFix(selectedFindingId.value);
    const finding = findings.value.find(f => f.id === selectedFindingId.value);
    if (finding) {
      finding.prCreated = true;
      finding.prUrl = data.prUrl;
    }
    toastMessage.value = 'Pull request created!';
  } catch (e: any) {
    toastMessage.value = e?.response?.data?.error || 'Failed to create PR';
  } finally {
    actionLoading.value = false;
  }
}

// ── Fix & Learn ──────────────────────────────────────────────────────────
const showFixLearnDialog = ref(false);
const fixLearnLoading = ref(false);
const fixLearnStep = ref<'explain' | 'results'>('explain');

// Group findings by category (skill or severity)
interface CategoryGroup {
  key: string;
  label: string;
  findings: Finding[];
  explanation: string;
  result: { level: string; feedback: string; deeper_explanation: string } | null;
}
const fixLearnGroups = ref<CategoryGroup[]>([]);

function openFixLearn() {
  showFixLearnDialog.value = true;
  fixLearnStep.value = 'explain';

  // Group findings by their first skill name, or severity as fallback
  const groupMap: Record<string, Finding[]> = {};
  for (const f of findings.value) {
    const key = (f.skills?.[0]?.name) || (f as any).category || f.severity || 'Other';
    if (!groupMap[key]) groupMap[key] = [];
    groupMap[key].push(f);
  }

  fixLearnGroups.value = Object.entries(groupMap).map(([key, fList]) => ({
    key,
    label: key.replace(/_/g, ' '),
    findings: fList,
    explanation: '',
    result: null,
  }));
}

async function submitUnderstanding() {
  fixLearnLoading.value = true;
  try {
    const filledGroups = fixLearnGroups.value.filter(g => g.explanation.trim());
    if (!filledGroups.length) {
      toastMessage.value = 'Please write an explanation for at least one category.';
      fixLearnLoading.value = false;
      return;
    }

    // Send one check per group, using the first finding's ID to store the result
    const entries = filledGroups.flatMap(g =>
      g.findings.map(f => ({ id: f.id, explanation: g.explanation }))
    );

    const { data } = await api.findings.checkUnderstanding(entries);

    // Map results back to groups
    for (const g of fixLearnGroups.value) {
      const firstResult = (data.results || []).find(
        (r: any) => g.findings.some(f => f.id === r.finding_id)
      );
      if (firstResult) {
        g.result = {
          level: firstResult.level,
          feedback: firstResult.feedback,
          deeper_explanation: firstResult.deeper_explanation || '',
        };
      }
    }
    fixLearnStep.value = 'results';
  } catch (e: any) {
    toastMessage.value = 'Failed to check understanding.';
  } finally {
    fixLearnLoading.value = false;
  }
}

async function copyFixToClipboard(finding: Finding) {
  const code = finding.suggestedCode || finding.originalCode || '';
  try {
    await navigator.clipboard.writeText(code);
    toastMessage.value = `Copied fix for "${finding.title}" to clipboard!`;
    setTimeout(() => { toastMessage.value = ''; }, 3000);
  } catch {
    toastMessage.value = 'Failed to copy to clipboard.';
  }
}

async function markFixedAfterCopy(finding: Finding) {
  try {
    await api.findings.markFixed(finding.id, '');
    const f = findings.value.find(x => x.id === finding.id);
    if (f) (f as any).isFixed = true;
    toastMessage.value = `"${finding.title}" marked as fixed. Push your changes to see the score improve!`;
  } catch {
    toastMessage.value = 'Failed to mark as fixed.';
  }
}

function goBack() {
  const projectId = route.query.project;
  if (projectId) {
    router.push({ path: '/', query: { project: String(projectId) } });
  } else {
    router.back();
  }
}
</script>

<template>
  <AppShell>
    <div class="p-4 flex-1 flex flex-col h-[calc(100vh-64px)]">
      <div class="w-full flex flex-col h-full">
        <!-- Header -->
        <div class="flex items-center justify-between mb-4 flex-shrink-0">
          <div class="flex items-center gap-4">
            <button
              @click="goBack"
              class="p-2 hover:bg-surface-container rounded-lg transition-colors"
            >
              <span class="material-symbols-outlined text-outline">arrow_back</span>
            </button>
            <div>
              <div class="flex items-center gap-2 text-on-surface font-mono text-sm">
                <span class="material-symbols-outlined text-sm text-outline">description</span>
                {{ filePath }}
              </div>
              <div class="flex items-center gap-2 mt-1">
                <span class="material-symbols-outlined text-xs text-outline">account_tree</span>
                <span class="text-xs text-primary-fixed-dim">{{ branch }}</span>
                <span class="text-xs text-outline mx-2">•</span>
                <span class="text-xs text-outline">{{ findings.length }} issues found</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Main Content Area -->
        <div class="flex gap-4 flex-1 min-h-0">
          <!-- Issue Navigator Sidebar -->
          <div
            class="w-64 flex-shrink-0 bg-surface-container-low rounded-xl border border-outline-variant/10 flex flex-col h-[70vh] max-h-[70vh] min-h-0"
          >
            <div class="p-3 border-b border-outline-variant/10 flex-shrink-0">
              <h3 class="text-sm font-bold text-on-surface">Issues in this file</h3>
            </div>
            <div class="flex-1 min-h-0 overflow-y-auto overscroll-contain p-2">
              <button
                v-for="(finding, idx) in findings"
                :key="finding.id"
                :class="[
                  'w-full text-left p-3 rounded-lg mb-2 transition-all',
                  selectedFindingId === finding.id
                    ? 'bg-primary/10 border border-primary/30'
                    : 'bg-surface-container border border-transparent hover:border-outline-variant/30'
                ]"
                @click="scrollToIssue(finding.id)"
              >
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs font-bold text-outline">#{{ idx + 1 }}</span>
                  <span :class="['px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border', getCategoryClass(finding.category || finding.severity || '')]">
                    {{ (finding.category || finding.severity || 'unknown').replace('_', ' ') }}
                  </span>
                </div>
                <p class="text-xs text-on-surface-variant line-clamp-2">
                  {{ (finding.explanation || '').slice(0, 80) }}{{ (finding.explanation || '').length > 80 ? '…' : '' }}
                </p>
                <div class="flex items-center gap-2 mt-2 text-[10px] text-outline">
                  <span>{{ getLineRange(finding.id) }}</span>
                  <span v-if="finding.markedUnderstood" class="text-primary ml-auto">✓ Understood</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Code Panels + Explanation -->
          <div class="flex-1 flex flex-col min-w-0 gap-4">
            <!-- Diff: two separate panels (original | optimized), scroll-synced; block height 60vh -->
            <div class="flex h-[60vh] max-h-[60vh] min-h-0 w-full flex-col gap-2">
              <div
                class="px-3 py-1.5 rounded-lg border border-outline-variant/10 bg-surface-container/40 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-outline"
              >
                <span class="tabular-nums"
                  >{{ originalLineCount }} → {{ optimizedLineCount }} lines</span
                >
                <span v-if="diffSourcePath" class="font-mono text-outline/70 truncate max-w-[14rem]" :title="diffSourcePath">{{
                  diffPrismLanguage
                }}</span>
              </div>
              <p
                v-if="selectedIssueSpanLabel"
                class="text-[11px] text-on-surface-variant px-1"
              >
                <span class="font-semibold text-red-400">Original:</span>
                red row / token = removed or old.
                <span class="font-semibold text-emerald-400 ml-2">Optimized:</span>
                green = added or new. Panels scroll together.
                {{ selectedIssueSpanLabel }}.
              </p>
              <div class="flex min-h-0 flex-1 gap-3">
                <!-- Original -->
                <div
                  class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-variant/15 bg-surface-container-lowest ring-1 ring-outline-variant/5"
                >
                  <div
                    class="flex flex-shrink-0 flex-wrap items-center justify-between gap-2 border-b border-outline-variant/10 bg-surface-container/80 px-3 py-2"
                  >
                    <div class="flex items-center gap-2">
                      <span class="text-xs font-bold uppercase tracking-widest text-outline">Original</span>
                      <span class="text-[11px] font-semibold text-red-400 tabular-nums">
                        {{ diffView.removalRows }} removal{{ diffView.removalRows === 1 ? '' : 's' }}
                      </span>
                    </div>
                    <button
                      type="button"
                      class="text-[11px] rounded-md border border-outline-variant/30 px-2 py-1 hover:bg-surface-container transition-colors"
                      @click="copyOriginalFile"
                    >
                      Copy
                    </button>
                  </div>
                  <div
                    ref="originalDiffScrollEl"
                    class="min-h-0 flex-1 overflow-auto overscroll-contain"
                    @scroll="syncDiffScroll('original', $event)"
                  >
                    <table class="diff-table w-full table-fixed border-collapse font-mono text-[13px] leading-snug">
                      <colgroup>
                        <col class="w-11" />
                        <col />
                      </colgroup>
                      <tbody>
                        <tr
                          v-for="(row, ridx) in diffView.rows"
                          :key="`diff-o-${ridx}-${selectedFindingId}`"
                          :id="`diff-o-${ridx}`"
                          :class="['align-top', leftTrClass(row)]"
                        >
                          <td :class="['py-0.5 pr-2 text-right tabular-nums select-none', leftGutterClass(row)]">
                            {{ row.leftNum ?? '' }}
                          </td>
                          <td :class="['py-0.5 pl-2 pr-2 align-top', leftLineCellClass(row)]">
                            <code
                              class="diff-code-line block whitespace-pre text-on-surface-variant"
                              v-html="highlightDiffSide(row.leftSegments)"
                            ></code>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
                <!-- Optimized -->
                <div
                  class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-emerald-500/20 bg-surface-container-lowest ring-1 ring-emerald-500/10"
                >
                  <div
                    class="flex flex-shrink-0 flex-wrap items-center justify-between gap-2 border-b border-emerald-500/20 bg-emerald-500/10 px-3 py-2"
                  >
                    <div class="flex items-center gap-2">
                      <span
                        class="text-xs font-bold uppercase tracking-widest text-emerald-800 dark:text-emerald-200"
                        >Optimized</span
                      >
                      <span class="text-[11px] font-semibold text-emerald-500 tabular-nums">
                        {{ diffView.additionRows }} addition{{ diffView.additionRows === 1 ? '' : 's' }}
                      </span>
                    </div>
                    <button
                      type="button"
                      class="text-[11px] rounded-md border border-emerald-500/35 px-2 py-1 text-emerald-800 hover:bg-emerald-500/15 dark:text-emerald-200 transition-colors"
                      @click="copyOptimizedFile"
                    >
                      Copy
                    </button>
                  </div>
                  <div
                    ref="optimizedDiffScrollEl"
                    class="min-h-0 flex-1 overflow-auto overscroll-contain"
                    @scroll="syncDiffScroll('optimized', $event)"
                  >
                    <table class="diff-table w-full table-fixed border-collapse font-mono text-[13px] leading-snug">
                      <colgroup>
                        <col class="w-11" />
                        <col />
                      </colgroup>
                      <tbody>
                        <tr
                          v-for="(row, ridx) in diffView.rows"
                          :key="`diff-p-${ridx}-${selectedFindingId}`"
                          :id="`diff-p-${ridx}`"
                          :class="['align-top', rightTrClass(row)]"
                        >
                          <td :class="['py-0.5 pr-2 text-right tabular-nums select-none', rightGutterClass(row)]">
                            {{ row.rightNum ?? '' }}
                          </td>
                          <td :class="['py-0.5 pl-2 pr-2 align-top', rightLineCellClass(row)]">
                            <code
                              class="diff-code-line block whitespace-pre text-on-surface-variant"
                              v-html="highlightDiffSide(row.rightSegments)"
                            ></code>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

            <!-- Explanation Box (Bottom) -->
            <div v-if="selectedFinding" class="flex-shrink-0 bg-surface-container-low rounded-xl border border-outline-variant/10 p-4">
              <div class="flex items-start justify-between gap-6">
                <!-- Explanation Content -->
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-3">
                    <span :class="['px-2 py-1 rounded-full text-[10px] font-bold uppercase border', getCategoryClass(selectedFinding.category || selectedFinding.severity || '')]">
                      {{ (selectedFinding.category || selectedFinding.severity || 'unknown').replace('_', ' ') }}
                    </span>
                    <span class="text-xs text-outline">by {{ selectedFinding.commitAuthor || 'unknown' }}</span>
                    <span class="text-xs text-outline">{{ getLineRange(selectedFinding.id) }}</span>
                  </div>
                  
                  <h3 class="text-lg font-bold text-on-surface mb-2">Why This Is Better</h3>
                  <p class="text-sm text-on-surface-variant leading-relaxed mb-3">
                    {{ selectedFinding.explanation }}
                  </p>
                  
                  <!-- References -->
                  <div v-if="selectedFinding.references?.length" class="flex items-center gap-4">
                    <span class="text-xs font-bold uppercase tracking-wider text-outline">References:</span>
                    <div class="flex flex-wrap gap-3">
                      <a
                        v-for="(ref, idx) in selectedFinding.references"
                        :key="idx"
                        :href="ref.url"
                        target="_blank"
                        class="text-xs text-primary hover:underline flex items-center gap-1"
                      >
                        <span class="material-symbols-outlined text-sm">link</span>
                        {{ ref.title }}
                      </a>
                    </div>
                  </div>

                  <!-- PR Link -->
                  <div v-if="selectedFinding.prUrl" class="mt-3 p-2 bg-primary/10 rounded-lg border border-primary/20 inline-block">
                    <p class="text-xs text-primary">
                      <span class="font-bold">PR Created:</span>
                      <a :href="selectedFinding.prUrl" target="_blank" class="ml-1 underline">View on GitHub</a>
                    </p>
                  </div>
                </div>

                <!-- Actions -->
                <div class="flex flex-col gap-3 items-end">
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      :checked="!!selectedFinding.markedUnderstood"
                      :disabled="actionLoading"
                      class="h-4 w-4 rounded border-outline-variant bg-surface-container text-primary"
                      @change="markUnderstood"
                    />
                    <span class="text-sm text-on-surface-variant">Mark as understood</span>
                  </label>
                  
                  <div class="flex gap-2">
                    <button
                      class="px-4 py-2 bg-primary/10 text-primary text-sm font-bold rounded-lg hover:bg-primary/20 transition-all flex items-center gap-2"
                      @click="openFixLearn"
                    >
                      <span class="material-symbols-outlined text-sm">school</span>
                      Fix & Learn
                    </button>
                    <button
                      :disabled="actionLoading || selectedFinding.explanationRequested"
                      class="px-4 py-2 border border-outline-variant/30 rounded-lg text-sm font-medium text-on-surface-variant hover:bg-surface-container transition-all disabled:opacity-50"
                      @click="requestExplanation"
                    >
                      {{ selectedFinding.explanationRequested ? '✓ Requested' : 'Request Help' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg cursor-pointer z-50"
      @click="toastMessage = ''"
    >
      {{ toastMessage }}
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="fixed inset-0 bg-background/80 flex items-center justify-center z-50">
      <span class="material-symbols-outlined text-4xl text-outline animate-spin">progress_activity</span>
    </div>
  </AppShell>

  <!-- Fix & Learn Dialog -->
  <Teleport to="body">
    <div v-if="showFixLearnDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click.self="showFixLearnDialog = false">
      <div class="bg-surface-container rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-outline-variant/10 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-primary">school</span>
            <h3 class="text-lg font-bold">Fix & Learn</h3>
          </div>
          <button @click="showFixLearnDialog = false" class="p-1 rounded-lg hover:bg-surface-container-highest">
            <span class="material-symbols-outlined text-outline">close</span>
          </button>
        </div>

        <!-- Content -->
        <div class="flex-1 overflow-y-auto p-6 space-y-6">

          <!-- Step 1: Explain (grouped by category) -->
          <template v-if="fixLearnStep === 'explain'">
            <p class="text-sm text-on-surface-variant">
              Before copying the fix, explain <strong>in your own words</strong> why the original code is problematic.
              Issues are grouped by category — one explanation per group.
            </p>

            <div v-for="group in fixLearnGroups" :key="group.key" class="p-4 rounded-xl border border-outline-variant/10 bg-surface-container-lowest space-y-3">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-tertiary/10 text-tertiary">
                  {{ group.label }}
                </span>
                <span class="text-sm font-bold">{{ group.findings.length }} issue{{ group.findings.length > 1 ? 's' : '' }}</span>
              </div>
              <ul class="text-xs text-outline space-y-1 pl-4 list-disc">
                <li v-for="f in group.findings" :key="f.id">{{ f.title }}</li>
              </ul>
              <textarea
                v-model="group.explanation"
                rows="3"
                class="w-full bg-surface-container border border-outline-variant/30 rounded-lg text-sm text-on-surface p-3 focus:ring-1 focus:ring-primary/50 placeholder:text-outline/40"
                :placeholder="`Why is ${group.label} problematic here? What could go wrong?`"
              ></textarea>
            </div>
          </template>

          <!-- Step 2: Results (grouped by category) -->
          <template v-if="fixLearnStep === 'results'">
            <div v-for="group in fixLearnGroups" :key="group.key" class="p-4 rounded-xl border space-y-3"
              :class="{
                'border-green-500/30 bg-green-500/5': group.result?.level === 'got_it',
                'border-yellow-500/30 bg-yellow-500/5': group.result?.level === 'partial',
                'border-red-500/30 bg-red-500/5': group.result?.level === 'not_yet',
                'border-outline-variant/10': !group.result,
              }">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-bold capitalize">{{ group.label }}</span>
                  <span class="text-xs text-outline">({{ group.findings.length }} issue{{ group.findings.length > 1 ? 's' : '' }})</span>
                </div>
                <span v-if="group.result" class="px-2 py-0.5 rounded-full text-xs font-bold"
                  :class="{
                    'bg-green-500/20 text-green-400': group.result.level === 'got_it',
                    'bg-yellow-500/20 text-yellow-400': group.result.level === 'partial',
                    'bg-red-500/20 text-red-400': group.result.level === 'not_yet',
                  }">
                  {{ group.result.level === 'got_it' ? 'Understood!' : group.result.level === 'partial' ? 'Almost' : 'Keep Learning' }}
                </span>
              </div>

              <!-- Feedback -->
              <p v-if="group.result?.feedback" class="text-sm text-on-surface-variant">
                {{ group.result.feedback }}
              </p>

              <!-- Deeper explanation (not_yet only) -->
              <div v-if="group.result?.level === 'not_yet' && group.result?.deeper_explanation" class="p-3 bg-surface-container rounded-lg">
                <p class="text-xs font-bold text-red-400 mb-1">Here's a clearer explanation:</p>
                <p class="text-sm text-on-surface">{{ group.result.deeper_explanation }}</p>
              </div>

              <!-- Per-finding actions (copy fix for each) -->
              <div v-if="group.result?.level === 'got_it' || group.result?.level === 'partial'" class="space-y-2 pt-2 border-t border-outline-variant/10">
                <div v-for="f in group.findings" :key="f.id" class="flex items-center justify-between gap-2">
                  <span class="text-xs text-on-surface truncate flex-1">{{ f.title }}</span>
                  <div class="flex gap-1.5 shrink-0">
                    <button @click="copyFixToClipboard(f)"
                      class="flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary text-xs font-bold rounded hover:bg-primary/20 transition-all">
                      <span class="material-symbols-outlined text-xs">content_copy</span> Copy Fix
                    </button>
                    <button @click="markFixedAfterCopy(f)"
                      class="flex items-center gap-1 px-2 py-1 border border-green-500/30 text-green-400 text-xs rounded hover:bg-green-500/10 transition-all">
                      <span class="material-symbols-outlined text-xs">check</span> Fixed
                    </button>
                  </div>
                </div>
              </div>

              <!-- "I understand now" (not_yet) -->
              <div v-if="group.result?.level === 'not_yet'" class="space-y-2 pt-2 border-t border-outline-variant/10">
                <div v-for="f in group.findings" :key="f.id" class="flex items-center justify-between gap-2">
                  <span class="text-xs text-on-surface truncate flex-1">{{ f.title }}</span>
                  <button @click="copyFixToClipboard(f)"
                    class="flex items-center gap-1 px-2 py-1 border border-outline-variant/30 text-on-surface-variant text-xs rounded hover:bg-surface-container transition-all">
                    <span class="material-symbols-outlined text-xs">content_copy</span> I Get It — Copy
                  </button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-outline-variant/10 flex justify-between">
          <button @click="showFixLearnDialog = false" class="px-4 py-2 text-sm text-outline hover:text-on-surface">
            Close
          </button>
          <button v-if="fixLearnStep === 'explain'" @click="submitUnderstanding" :disabled="fixLearnLoading"
            class="px-6 py-2 primary-gradient text-on-primary text-sm font-bold rounded-lg disabled:opacity-50 flex items-center gap-2">
            <span v-if="fixLearnLoading" class="material-symbols-outlined text-sm animate-spin">progress_activity</span>
            {{ fixLearnLoading ? 'Checking...' : 'Check My Understanding' }}
          </button>
          <button v-if="fixLearnStep === 'results'" @click="fixLearnStep = 'explain'" class="px-4 py-2 text-sm text-primary font-bold">
            ← Try Again
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* Full-row diff tint (GitHub-style); sticky gutters stay opaque for horizontal scroll */
.diff-tr-removed {
  background-color: rgba(220, 38, 38, 0.2);
}
.diff-tr-removed .diff-gutter {
  background-color: rgba(69, 10, 10, 0.92);
  color: rgb(254 202 202);
}

.diff-tr-issue {
  background-color: rgba(220, 38, 38, 0.12);
}
.diff-tr-issue .diff-gutter {
  background-color: rgba(69, 10, 10, 0.78);
  color: rgb(252 165 165);
}

.diff-tr-pad-left {
  background-color: rgba(255, 255, 255, 0.05);
}
.diff-tr-pad-left .diff-gutter {
  background-color: rgba(0, 0, 0, 0.28);
  color: rgba(255, 255, 255, 0.38);
}

.diff-tr-added {
  background-color: rgba(16, 185, 129, 0.28);
}
.diff-tr-added .diff-gutter-opt {
  background-color: rgba(6, 78, 59, 0.92);
  color: rgb(167 243 208);
}

.diff-tr-pad-right {
  background-color: rgba(255, 255, 255, 0.05);
}
.diff-tr-pad-right .diff-gutter-opt {
  background-color: rgba(0, 0, 0, 0.28);
  color: rgba(255, 255, 255, 0.38);
}

.diff-code-line {
  overflow-wrap: anywhere;
  word-break: break-word;
}

/* Prism tokens: improve contrast on dark surface (prism.css is light-theme oriented) */
.diff-table :deep(.token.keyword) {
  color: #d73a49;
}
.diff-table :deep(.token.string) {
  color: #032f62;
}
.diff-table :deep(.token.function) {
  color: #6f42c1;
}
.diff-table :deep(.token.number) {
  color: #005cc5;
}
.diff-table :deep(.token.comment),
.diff-table :deep(.token.prolog),
.diff-table :deep(.token.doctype),
.diff-table :deep(.token.cdata) {
  color: #6a737d;
}
.diff-table :deep(.token.operator),
.diff-table :deep(.token.punctuation) {
  color: #24292e;
}
.diff-table :deep(.token.class-name) {
  color: #6f42c1;
}

.diff-seg-del {
  background: rgba(248, 113, 113, 0.5);
  color: rgb(254 242 242);
  border-radius: 0.125rem;
  padding: 0 0.125rem;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
.diff-seg-add {
  background: rgba(52, 211, 153, 0.55);
  color: rgb(236 253 245);
  border-radius: 0.125rem;
  padding: 0 0.125rem;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
</style>
