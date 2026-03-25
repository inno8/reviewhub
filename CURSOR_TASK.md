# ReviewHub: GitHub File Viewer with Issue Highlighting

## Goal
When clicking a finding, show the full file content from GitHub with the problematic lines highlighted.

## Task 1: Backend - File Content Endpoint

**File:** `backend/src/routes/files.ts` (new)

```typescript
import { Router, Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { Octokit } from '@octokit/rest';
import { authMiddleware } from '../middleware/auth';

const router = Router();
const prisma = new PrismaClient();
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

router.use(authMiddleware);

// GET /api/files/:projectId/:branch/*path
// Fetches file content from GitHub
router.get('/:projectId/:branch/*', async (req: Request, res: Response): Promise<void> => {
  const projectId = parseInt(req.params.projectId);
  const branch = req.params.branch;
  const filePath = req.params[0]; // Everything after branch/

  if (!projectId || !branch || !filePath) {
    res.status(400).json({ error: 'projectId, branch, and file path required' });
    return;
  }

  const project = await prisma.project.findUnique({ where: { id: projectId } });
  if (!project) {
    res.status(404).json({ error: 'Project not found' });
    return;
  }

  try {
    const { data } = await octokit.repos.getContent({
      owner: project.githubOwner,
      repo: project.githubRepo,
      path: filePath,
      ref: branch,
    });

    if (Array.isArray(data) || data.type !== 'file') {
      res.status(400).json({ error: 'Path is not a file' });
      return;
    }

    // Decode base64 content
    const content = Buffer.from(data.content, 'base64').toString('utf-8');

    res.json({
      content,
      path: filePath,
      sha: data.sha,
      size: data.size,
      encoding: 'utf-8',
    });
  } catch (error: any) {
    if (error.status === 404) {
      res.status(404).json({ error: 'File not found in repository' });
    } else {
      console.error('[GitHub] Failed to fetch file:', error);
      res.status(500).json({ error: 'Failed to fetch file from GitHub' });
    }
  }
});

export default router;
```

**Register in `backend/src/app.ts`:**
```typescript
import filesRouter from './routes/files';
app.use('/api/files', filesRouter);
```

## Task 2: Frontend - API Client Update

**File:** `frontend/src/composables/useApi.ts`

Add:
```typescript
files: {
  getContent: (projectId: number, branch: string, filePath: string) =>
    client.get(`/files/${projectId}/${encodeURIComponent(branch)}/${filePath}`),
},
```

## Task 3: Frontend - FileViewer Component

**File:** `frontend/src/components/code/FileViewer.vue`

Create a modal component that:
1. Fetches file content from the API
2. Displays with syntax highlighting (use Prism.js or highlight.js)
3. Highlights issue lines (lineStart to lineEnd) in yellow/red
4. Auto-scrolls to the first highlighted line
5. Shows line numbers

```vue
<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-white rounded-lg shadow-xl w-[90vw] max-w-5xl max-h-[85vh] flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b">
        <div>
          <h3 class="font-semibold text-lg">{{ filePath }}</h3>
          <p class="text-sm text-gray-500">{{ branch }}</p>
        </div>
        <button @click="$emit('close')" class="p-2 hover:bg-gray-100 rounded">
          <XIcon class="w-5 h-5" />
        </button>
      </div>

      <!-- Code Content -->
      <div class="flex-1 overflow-auto" ref="codeContainer">
        <div v-if="loading" class="p-8 text-center text-gray-500">Loading file...</div>
        <div v-else-if="error" class="p-8 text-center text-red-500">{{ error }}</div>
        <div v-else class="code-viewer font-mono text-sm">
          <div
            v-for="(line, index) in lines"
            :key="index"
            :ref="el => { if (isHighlighted(index + 1)) highlightedRefs.push(el) }"
            :class="[
              'flex hover:bg-gray-50',
              isHighlighted(index + 1) ? 'bg-yellow-100 border-l-4 border-yellow-500' : ''
            ]"
          >
            <span class="w-12 px-2 py-0.5 text-right text-gray-400 select-none border-r bg-gray-50">
              {{ index + 1 }}
            </span>
            <pre class="flex-1 px-4 py-0.5 overflow-x-auto"><code v-html="highlightLine(line)"></code></pre>
          </div>
        </div>
      </div>

      <!-- Footer with issue info -->
      <div v-if="finding" class="p-4 border-t bg-gray-50">
        <p class="font-medium text-sm">{{ finding.category }}</p>
        <p class="text-sm text-gray-600 mt-1">{{ finding.explanation }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue';
import { XIcon } from 'lucide-vue-next';
import { api } from '@/composables/useApi';
import Prism from 'prismjs';
import 'prismjs/themes/prism.css';
// Import language support as needed
import 'prismjs/components/prism-markup';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-python';

const props = defineProps<{
  projectId: number;
  branch: string;
  filePath: string;
  lineStart: number;
  lineEnd: number;
  finding?: any;
}>();

const emit = defineEmits(['close']);

const loading = ref(true);
const error = ref('');
const content = ref('');
const codeContainer = ref<HTMLElement>();
const highlightedRefs = ref<HTMLElement[]>([]);

const lines = computed(() => content.value.split('\n'));

const language = computed(() => {
  const ext = props.filePath.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    html: 'markup',
    htm: 'markup',
    vue: 'markup',
    xml: 'markup',
    js: 'javascript',
    ts: 'javascript',
    jsx: 'javascript',
    tsx: 'javascript',
    py: 'python',
    css: 'css',
    scss: 'css',
  };
  return langMap[ext || ''] || 'markup';
});

function isHighlighted(lineNum: number): boolean {
  return lineNum >= props.lineStart && lineNum <= props.lineEnd;
}

function highlightLine(line: string): string {
  try {
    return Prism.highlight(line || ' ', Prism.languages[language.value], language.value);
  } catch {
    return escapeHtml(line || ' ');
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

onMounted(async () => {
  try {
    const { data } = await api.files.getContent(props.projectId, props.branch, props.filePath);
    content.value = data.content;
  } catch (e: any) {
    error.value = e.response?.data?.error || 'Failed to load file';
  } finally {
    loading.value = false;
  }

  // Scroll to highlighted line after render
  await nextTick();
  if (highlightedRefs.value.length > 0) {
    highlightedRefs.value[0]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
});
</script>

<style scoped>
.code-viewer {
  min-width: max-content;
}
pre {
  margin: 0;
  white-space: pre;
}
code {
  background: none;
  padding: 0;
}
</style>
```

## Task 4: Install Prism.js

```bash
cd frontend
npm install prismjs @types/prismjs
```

## Task 5: Integrate into FindingCard

**File:** `frontend/src/components/findings/FindingCard.vue` (or wherever findings are displayed)

Add a "View File" button that opens the FileViewer:

```vue
<template>
  <!-- existing finding card content -->
  <button @click="showFileViewer = true" class="text-sm text-blue-600 hover:underline">
    View full file
  </button>
  
  <FileViewer
    v-if="showFileViewer"
    :projectId="projectId"
    :branch="finding.review.branch"
    :filePath="finding.filePath"
    :lineStart="finding.lineStart"
    :lineEnd="finding.lineEnd"
    :finding="finding"
    @close="showFileViewer = false"
  />
</template>
```

## Task 6: Handle Missing Line Numbers

Some imported findings have lineStart/lineEnd = 1. For better UX:
- If lineStart === lineEnd === 1 and we have `originalCode`, search for that code in the file content to find the actual line numbers
- Highlight all matching occurrences

## Testing

1. Click a finding with a valid filePath (e.g., `home.html`)
2. FileViewer modal should open
3. Full file content displayed with syntax highlighting
4. Issue lines (lineStart to lineEnd) highlighted in yellow
5. Auto-scroll to highlighted section
6. Close button works

## Files to Create/Modify

- **CREATE:** `backend/src/routes/files.ts`
- **MODIFY:** `backend/src/app.ts` (register route)
- **CREATE:** `frontend/src/components/code/FileViewer.vue`
- **MODIFY:** `frontend/src/composables/useApi.ts`
- **MODIFY:** Finding display component (add "View File" button)
- **INSTALL:** `prismjs` package

---

Ready for implementation!
