import { ref, computed, onMounted, nextTick } from 'vue';
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
const props = defineProps();
const loading = ref(true);
const error = ref('');
const fileContent = ref('');
const originalPanel = ref();
const optimizedPanel = ref();
let scrolling = false;
const language = computed(() => {
    const ext = props.finding.filePath.split('.').pop()?.toLowerCase();
    const langMap = {
        html: 'markup', htm: 'markup', vue: 'markup', xml: 'markup', svg: 'markup',
        js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
        ts: 'typescript', tsx: 'typescript',
        py: 'python', css: 'css', scss: 'css', go: 'go',
        json: 'json', yaml: 'yaml', yml: 'yaml', sh: 'bash', bash: 'bash',
    };
    return langMap[ext || ''] || 'markup';
});
const originalLines = computed(() => fileContent.value.split('\n'));
const optimizedLines = computed(() => {
    if (!fileContent.value)
        return [];
    return generateOptimizedFile(fileContent.value, props.finding).split('\n');
});
const fixLineStart = computed(() => {
    if (!props.finding.lineStart)
        return -1;
    return props.finding.lineStart;
});
const fixLineEnd = computed(() => {
    if (!props.finding.lineStart)
        return -1;
    const optimizedCodeLines = props.finding.optimizedCode?.split('\n') || [];
    return fixLineStart.value + optimizedCodeLines.length - 1;
});
const commitUrl = computed(() => {
    const p = props.finding.review?.project;
    if (!p?.githubOwner || !p?.githubRepo || !props.finding.commitSha)
        return '';
    return `https://github.com/${p.githubOwner}/${p.githubRepo}/commit/${props.finding.commitSha}`;
});
function isIssueLine(lineNum) {
    const start = props.finding.lineStart;
    const end = props.finding.lineEnd;
    if (!start)
        return false;
    return lineNum >= start && lineNum <= (end || start);
}
function isFixLine(lineNum) {
    if (fixLineStart.value < 0)
        return false;
    return lineNum >= fixLineStart.value && lineNum <= fixLineEnd.value;
}
function generateOptimizedFile(originalContent, finding) {
    const lines = originalContent.split('\n');
    if (finding.optimizedCode && finding.lineStart && finding.lineEnd) {
        const before = lines.slice(0, finding.lineStart - 1);
        const after = lines.slice(finding.lineEnd);
        const fixLines = finding.optimizedCode.split('\n');
        return [...before, ...fixLines, ...after].join('\n');
    }
    return originalContent;
}
function highlightLine(line) {
    try {
        const lang = Prism.languages[language.value];
        if (lang) {
            return Prism.highlight(line || ' ', lang, language.value);
        }
        return escapeHtml(line || ' ');
    }
    catch {
        return escapeHtml(line || ' ');
    }
}
function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function syncScroll(source) {
    if (scrolling)
        return;
    scrolling = true;
    if (source === 'original' && originalPanel.value && optimizedPanel.value) {
        optimizedPanel.value.scrollTop = originalPanel.value.scrollTop;
        optimizedPanel.value.scrollLeft = originalPanel.value.scrollLeft;
    }
    else if (source === 'optimized' && originalPanel.value && optimizedPanel.value) {
        originalPanel.value.scrollTop = optimizedPanel.value.scrollTop;
        originalPanel.value.scrollLeft = optimizedPanel.value.scrollLeft;
    }
    requestAnimationFrame(() => { scrolling = false; });
}
onMounted(async () => {
    const projectId = props.finding.review?.project?.id;
    const branch = props.finding.review?.branch || 'main';
    if (!projectId) {
        // Fallback: use finding's own file-content endpoint
        try {
            const { data } = await api.findings.getFileContent(props.finding.id);
            fileContent.value = data.content;
        }
        catch (e) {
            error.value = e.response?.data?.error || 'Failed to load file content';
        }
        finally {
            loading.value = false;
        }
        return;
    }
    try {
        const { data } = await api.files.getContent(projectId, branch, props.finding.filePath);
        fileContent.value = data.content;
    }
    catch {
        // Fallback to finding-specific endpoint
        try {
            const { data } = await api.findings.getFileContent(props.finding.id);
            fileContent.value = data.content;
        }
        catch (e) {
            error.value = e.response?.data?.error || 'Failed to load file content';
        }
    }
    finally {
        loading.value = false;
    }
    // Scroll to issue lines after render
    await nextTick();
    if (props.finding.lineStart && originalPanel.value) {
        const lineEl = originalPanel.value.querySelector(`.code-lines > div:nth-child(${props.finding.lineStart})`);
        if (lineEl) {
            lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "diff-viewer space-y-4" },
});
/** @type {__VLS_StyleScopedClasses['diff-viewer']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-surface-container-low rounded-xl p-4 border border-outline-variant/10" },
});
/** @type {__VLS_StyleScopedClasses['bg-surface-container-low']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-4 flex-wrap" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "font-mono text-sm text-on-surface-variant bg-surface-container px-3 py-1 rounded-lg flex items-center gap-1.5" },
});
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-on-surface-variant']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "material-symbols-outlined text-sm" },
});
/** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
(__VLS_ctx.finding.filePath);
if (__VLS_ctx.commitUrl) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
        href: (__VLS_ctx.commitUrl),
        target: "_blank",
        ...{ class: "text-primary text-sm hover:underline flex items-center gap-1" },
    });
    /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    (__VLS_ctx.finding.commitSha || 'View commit');
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-3 mt-2 text-sm text-outline" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
if (__VLS_ctx.finding.commitAuthor) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "flex items-center gap-1" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    (__VLS_ctx.finding.commitAuthor);
}
if (__VLS_ctx.finding.review?.branch) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "flex items-center gap-1" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    (__VLS_ctx.finding.review.branch);
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-center h-64 bg-surface-container rounded-xl border border-outline-variant/10" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-64']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-center text-outline" },
    });
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-3xl animate-spin" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "mt-2 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-error/10 border border-error/20 rounded-xl p-6 text-center" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-error/10']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-error/20']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-3xl text-error" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-error']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "mt-2 text-error" },
    });
    /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-error']} */ ;
    (__VLS_ctx.error);
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "grid grid-cols-2 gap-4" },
    });
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "rounded-xl overflow-hidden border border-outline-variant/10" },
    });
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "px-4 py-2 bg-red-900/80 text-white text-sm font-bold flex items-center gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-900/80']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onScroll: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!!(__VLS_ctx.error))
                    return;
                __VLS_ctx.syncScroll('original');
                // @ts-ignore
                [finding, finding, finding, finding, finding, finding, commitUrl, commitUrl, loading, error, error, syncScroll,];
            } },
        ref: "originalPanel",
        ...{ class: "code-scroll-panel overflow-auto font-mono text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['code-scroll-panel']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-auto']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "code-lines" },
    });
    /** @type {__VLS_StyleScopedClasses['code-lines']} */ ;
    for (const [line, idx] of __VLS_vFor((__VLS_ctx.originalLines))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (idx),
            ...{ class: ([
                    'flex hover:bg-surface-container-highest/30',
                    __VLS_ctx.isIssueLine(idx + 1) ? 'bg-red-900/20 border-l-4 border-red-500' : ''
                ]) },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-surface-container-highest/30']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "line-num w-12 px-2 py-0.5 text-right text-outline select-none border-r border-outline-variant/10 bg-surface-container shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['line-num']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-12']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
        /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-r']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
        /** @type {__VLS_StyleScopedClasses['shrink-0']} */ ;
        (idx + 1);
        __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({
            ...{ class: "flex-1 px-4 py-0.5 overflow-x-auto" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({});
        __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.highlightLine(line)) }, null, null);
        // @ts-ignore
        [originalLines, isIssueLine, highlightLine,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "rounded-xl overflow-hidden border border-outline-variant/10" },
    });
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "px-4 py-2 bg-green-900/80 text-white text-sm font-bold flex items-center gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-900/80']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onScroll: (...[$event]) => {
                if (!!(__VLS_ctx.loading))
                    return;
                if (!!(__VLS_ctx.error))
                    return;
                __VLS_ctx.syncScroll('optimized');
                // @ts-ignore
                [syncScroll,];
            } },
        ref: "optimizedPanel",
        ...{ class: "code-scroll-panel overflow-auto font-mono text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['code-scroll-panel']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-auto']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "code-lines" },
    });
    /** @type {__VLS_StyleScopedClasses['code-lines']} */ ;
    for (const [line, idx] of __VLS_vFor((__VLS_ctx.optimizedLines))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (idx),
            ...{ class: ([
                    'flex hover:bg-surface-container-highest/30',
                    __VLS_ctx.isFixLine(idx + 1) ? 'bg-green-900/20 border-l-4 border-green-500' : ''
                ]) },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-surface-container-highest/30']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "line-num w-12 px-2 py-0.5 text-right text-outline select-none border-r border-outline-variant/10 bg-surface-container shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['line-num']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-12']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
        /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-r']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
        /** @type {__VLS_StyleScopedClasses['shrink-0']} */ ;
        (idx + 1);
        __VLS_asFunctionalElement1(__VLS_intrinsics.pre, __VLS_intrinsics.pre)({
            ...{ class: "flex-1 px-4 py-0.5 overflow-x-auto" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({});
        __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.highlightLine(line)) }, null, null);
        // @ts-ignore
        [highlightLine, optimizedLines, isFixLine,];
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
