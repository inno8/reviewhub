# ReviewHub: Full File Display with Diff Highlighting

## Goal
Show the ENTIRE file content from GitHub with:
- **ORIGINAL section**: Full file with issue lines highlighted in RED
- **OPTIMIZED section**: Full file with the fix applied, highlighted in GREEN

## Task 1: Backend - Fetch Full File Content

The `/api/files/:projectId/:branch/:filePath` endpoint already exists. Use it.

## Task 2: Update Finding Detail View

**File:** `frontend/src/views/FindingDetailView.vue`

Replace the current code comparison with a full-file diff view:

```vue
<template>
  <div class="grid grid-cols-2 gap-4">
    <!-- ORIGINAL: Full file with issue highlighted in red -->
    <div class="code-panel">
      <h3 class="header bg-red-900 text-white">ORIGINAL</h3>
      <div class="code-content">
        <div v-for="(line, idx) in originalLines" :key="idx"
             :class="isIssueLine(idx + 1) ? 'bg-red-900/30 border-l-4 border-red-500' : ''">
          <span class="line-number">{{ idx + 1 }}</span>
          <code v-html="highlightSyntax(line)"></code>
        </div>
      </div>
    </div>
    
    <!-- OPTIMIZED: Full file with fix highlighted in green -->
    <div class="code-panel">
      <h3 class="header bg-green-900 text-white">OPTIMIZED</h3>
      <div class="code-content">
        <div v-for="(line, idx) in optimizedLines" :key="idx"
             :class="isFixLine(idx + 1) ? 'bg-green-900/30 border-l-4 border-green-500' : ''">
          <span class="line-number">{{ idx + 1 }}</span>
          <code v-html="highlightSyntax(line)"></code>
        </div>
      </div>
    </div>
  </div>
</template>
```

### Logic:
1. On mount, fetch full file from GitHub: `api.files.getContent(projectId, branch, filePath)`
2. `originalLines` = full file content split by newlines
3. `optimizedLines` = full file content with the fix applied (replace issue lines with optimized code)
4. Highlight issue lines (lineStart to lineEnd) in RED in original
5. Highlight fix lines in GREEN in optimized
6. Use Prism.js for syntax highlighting
7. Sync scroll between both panels

### Header Info (above code panels):
```vue
<div class="file-header">
  <div class="flex items-center gap-4">
    <span class="font-mono text-sm">{{ finding.filePath }}</span>
    <a :href="commitUrl" target="_blank" class="text-blue-400 hover:underline">
      {{ finding.commitSha }}
    </a>
  </div>
  <div class="text-sm text-gray-400">
    <span>Author: {{ finding.commitAuthor }}</span>
    <span class="mx-2">•</span>
    <span>Branch: {{ finding.review.branch }}</span>
  </div>
</div>
```

## Task 3: Generate Optimized File Content

When we have the original file and the fix suggestion, generate the optimized version:

```typescript
function generateOptimizedFile(originalContent: string, finding: Finding): string {
  const lines = originalContent.split('\n');
  
  // If we have specific optimizedCode, replace the lines
  if (finding.optimizedCode && finding.lineStart && finding.lineEnd) {
    const before = lines.slice(0, finding.lineStart - 1);
    const after = lines.slice(finding.lineEnd);
    const fixLines = finding.optimizedCode.split('\n');
    return [...before, ...fixLines, ...after].join('\n');
  }
  
  // Otherwise return original (no automatic fix available)
  return originalContent;
}
```

## Task 4: Sync Scroll Between Panels

Both panels should scroll together:

```typescript
const originalPanel = ref<HTMLElement>();
const optimizedPanel = ref<HTMLElement>();

function syncScroll(source: 'original' | 'optimized') {
  if (source === 'original' && originalPanel.value && optimizedPanel.value) {
    optimizedPanel.value.scrollTop = originalPanel.value.scrollTop;
  } else if (source === 'optimized' && originalPanel.value && optimizedPanel.value) {
    originalPanel.value.scrollTop = optimizedPanel.value.scrollTop;
  }
}
```

## Task 5: Build Commit URL

```typescript
const commitUrl = computed(() => {
  if (!finding.value?.review?.project) return '';
  const p = finding.value.review.project;
  return `https://github.com/${p.githubOwner}/${p.githubRepo}/commit/${finding.value.commitSha}`;
});
```

## Files to Modify

- `frontend/src/views/FindingDetailView.vue` - Complete rewrite of code display
- `frontend/src/components/code/DiffViewer.vue` - New component for side-by-side diff

## Expected Result

When viewing a finding:
1. Full file loads from GitHub
2. Left panel (ORIGINAL): Shows entire file, issue lines 20-21 highlighted RED
3. Right panel (OPTIMIZED): Shows entire file with fix applied, fix lines highlighted GREEN
4. Both panels scroll in sync
5. Header shows: file path, commit link, author, branch

---

Ready for implementation!
