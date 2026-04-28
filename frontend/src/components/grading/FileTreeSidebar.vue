<template>
  <aside
    :class="[
      'rounded-xl border border-outline-variant/10 bg-surface-container-low p-3',
      inline
        ? 'block'
        : 'hidden xl:block fixed top-24 right-6 w-60 max-h-[calc(100vh-7rem)] overflow-y-auto',
    ]"
    data-testid="file-tree-sidebar"
  >
    <h3 class="text-[11px] font-bold uppercase tracking-widest text-on-surface-variant mb-2 px-1">
      Bestanden ({{ files.length }})
    </h3>
    <ul class="list-none p-0 m-0 flex flex-col gap-0.5">
      <template v-for="node in flatTree" :key="node.key">
        <li v-if="node.type === 'folder'" class="text-[11px]">
          <div
            class="flex items-center gap-1.5 px-1.5 py-1 text-outline"
            :style="{ paddingLeft: (4 + node.depth * 12) + 'px' }"
          >
            <span class="material-symbols-rounded text-[14px]" aria-hidden="true">folder</span>
            <span class="truncate font-medium">{{ node.name }}</span>
          </div>
        </li>
        <li v-else class="text-xs">
          <button
            type="button"
            @click="onFileClick(node.fullPath)"
            :class="[
              'w-full flex items-center gap-1.5 px-1.5 py-1 rounded-md text-left transition-colors',
              node.fullPath === activePath
                ? 'bg-primary/15 text-primary'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container',
            ]"
            :style="{ paddingLeft: (4 + node.depth * 12) + 'px' }"
            :data-testid="`file-tree-node-${node.fullPath}`"
            :title="node.fullPath"
          >
            <span
              class="material-symbols-rounded text-[14px] shrink-0"
              :class="node.isAdded ? 'text-emerald-400' : 'text-outline'"
              aria-hidden="true"
            >{{ node.isAdded ? 'add_circle' : 'edit' }}</span>
            <span class="truncate">{{ node.name }}</span>
          </button>
        </li>
      </template>
    </ul>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';

interface FileEntry {
  path: string;
  isAdded?: boolean;
}

const props = withDefaults(
  defineProps<{
    files: FileEntry[];
    /** When true, render inline (no fixed positioning, no xl-only gate) — for composition inside a wrapper sidebar. */
    inline?: boolean;
  }>(),
  { inline: false },
);

interface TreeNode {
  key: string;
  name: string;
  type: 'file' | 'folder';
  depth: number;
  fullPath: string;
  isAdded?: boolean;
}

/** Flat pre-order list for stable v-for rendering with depth-based indent. */
const flatTree = computed<TreeNode[]>(() => {
  interface FolderBucket {
    children: Map<string, FolderBucket>;
    files: FileEntry[];
  }
  const root: FolderBucket = { children: new Map(), files: [] };
  for (const f of props.files) {
    const parts = f.path.split('/').filter(Boolean);
    if (parts.length === 1) {
      root.files.push(f);
      continue;
    }
    let cur = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const seg = parts[i];
      if (!cur.children.has(seg)) cur.children.set(seg, { children: new Map(), files: [] });
      cur = cur.children.get(seg)!;
    }
    cur.files.push(f);
  }

  const out: TreeNode[] = [];
  function walk(bucket: FolderBucket, pathPrefix: string, depth: number) {
    const folderNames = Array.from(bucket.children.keys()).sort();
    for (const folder of folderNames) {
      const folderPath = pathPrefix ? `${pathPrefix}/${folder}` : folder;
      out.push({
        key: `folder:${folderPath}`,
        name: folder,
        type: 'folder',
        depth,
        fullPath: folderPath,
      });
      walk(bucket.children.get(folder)!, folderPath, depth + 1);
    }
    const sorted = [...bucket.files].sort((a, b) => a.path.localeCompare(b.path));
    for (const f of sorted) {
      const parts = f.path.split('/');
      out.push({
        key: `file:${f.path}`,
        name: parts[parts.length - 1],
        type: 'file',
        depth,
        fullPath: f.path,
        isAdded: f.isAdded,
      });
    }
  }
  walk(root, '', 0);
  return out;
});

const activePath = ref<string | null>(null);

function onFileClick(path: string) {
  const el = document.getElementById(`file-${encodeURIComponent(path)}`);
  if (el) {
    activePath.value = path;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// Track which file section is in view — highlight it in the sidebar.
let observer: IntersectionObserver | null = null;

function setupObserver() {
  if (typeof window === 'undefined' || !('IntersectionObserver' in window)) return;
  observer?.disconnect();
  const nodes = document.querySelectorAll('[data-file-path]');
  if (!nodes.length) {
    // Retry shortly — files may mount after sidebar.
    window.setTimeout(setupObserver, 300);
    return;
  }
  observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter(e => e.isIntersecting)
      .sort((a, b) => (b.intersectionRatio - a.intersectionRatio));
    if (visible.length > 0) {
      const path = (visible[0].target as HTMLElement).dataset.filePath;
      if (path) activePath.value = path;
    }
  }, { rootMargin: '-80px 0px -50% 0px', threshold: [0, 0.25, 0.5] });
  nodes.forEach(n => observer!.observe(n));
}

onMounted(() => {
  // Wait a tick so DiffInlineViewer components have mounted.
  window.setTimeout(setupObserver, 200);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});
</script>
