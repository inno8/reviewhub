import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import FileViewer from '@/components/code/FileViewer.vue';
const props = defineProps();
const router = useRouter();
const showFileViewer = ref(false);
const categoryClass = computed(() => {
    const cat = props.finding.category.toLowerCase().replace('_', '');
    return {
        security: 'bg-error/10 text-error border-error/20',
        performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
        codestyle: 'bg-primary/10 text-primary border-primary/20',
        testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
        architecture: 'bg-secondary/10 text-secondary border-secondary/20',
    }[cat] || 'bg-outline/10 text-outline border-outline/20';
});
const difficultyClass = computed(() => {
    const diff = props.finding.difficulty.toLowerCase();
    return {
        beginner: 'bg-secondary-container/10 text-secondary border-secondary-container/20',
        intermediate: 'bg-tertiary-container/10 text-tertiary-container border-tertiary-container/20',
        advanced: 'bg-error/10 text-error border-error/20',
    }[diff] || 'bg-outline/10 text-outline border-outline/20';
});
const hasRealCode = computed(() => {
    const code = props.finding.originalCode;
    return code && code.trim() !== '' && !code.trim().startsWith('//');
});
const authorName = computed(() => props.finding.commitAuthor || 'Unknown');
const fileIcon = computed(() => {
    const ext = props.finding.filePath.split('.').pop()?.toLowerCase();
    if (['ts', 'tsx', 'js', 'jsx'].includes(ext || ''))
        return 'code';
    if (['go', 'rs', 'py'].includes(ext || ''))
        return 'description';
    if (['test', 'spec'].some(s => props.finding.filePath.includes(s)))
        return 'biotech';
    return 'folder_open';
});
async function openFinding() {
    await router.push(`/findings/${props.finding.id}`);
}
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
    ...{ onClick: (__VLS_ctx.openFinding) },
    ...{ class: "bg-surface-container-low p-6 rounded-xl border border-outline-variant/5 hover:border-primary/20 transition-all duration-300 cursor-pointer group relative" },
});
/** @type {__VLS_StyleScopedClasses['bg-surface-container-low']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-outline-variant/5']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-primary/20']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['group']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex justify-between items-start mb-4" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-2 text-outline text-xs font-mono" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "material-symbols-outlined text-sm" },
});
/** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
(__VLS_ctx.fileIcon);
(__VLS_ctx.finding.filePath);
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "bg-surface-container-highest text-outline text-[10px] px-2 py-0.5 rounded font-medium" },
});
/** @type {__VLS_StyleScopedClasses['bg-surface-container-highest']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
(__VLS_ctx.finding.review?.branch || 'main');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex gap-2 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: (['px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border', __VLS_ctx.categoryClass]) },
});
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-wider']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
(__VLS_ctx.finding.category.replace('_', ' '));
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: (['px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border', __VLS_ctx.difficultyClass]) },
});
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-wider']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
(__VLS_ctx.finding.difficulty);
if (!__VLS_ctx.hasRealCode) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-1.5 text-outline text-xs mb-3 bg-surface-container px-2 py-1 rounded w-fit" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-fit']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-xs" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-on-surface text-sm mb-6 line-clamp-2 font-medium" },
});
/** @type {__VLS_StyleScopedClasses['text-on-surface']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['line-clamp-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
(__VLS_ctx.finding.explanation);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between mt-auto" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-auto']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-2" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "w-6 h-6 rounded-full bg-surface-container-highest flex items-center justify-center text-[10px] font-bold text-primary" },
});
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-surface-container-highest']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
(__VLS_ctx.authorName.charAt(0).toUpperCase());
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text-xs text-outline font-medium" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
(__VLS_ctx.authorName);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-3" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
if (__VLS_ctx.finding.review?.project?.id) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.finding.review?.project?.id))
                    return;
                __VLS_ctx.showFileViewer = true;
                // @ts-ignore
                [openFinding, fileIcon, finding, finding, finding, finding, finding, finding, categoryClass, difficultyClass, hasRealCode, authorName, authorName, showFileViewer,];
            } },
        ...{ class: "text-outline text-xs font-medium flex items-center gap-1 hover:text-primary transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ class: "text-primary text-xs font-bold flex items-center gap-1 hover:underline" },
});
/** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "material-symbols-outlined text-sm" },
});
/** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
if (__VLS_ctx.showFileViewer && __VLS_ctx.finding.review?.project?.id) {
    const __VLS_0 = FileViewer;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        ...{ 'onClose': {} },
        projectId: (__VLS_ctx.finding.review.project.id),
        branch: (__VLS_ctx.finding.review?.branch || 'main'),
        filePath: (__VLS_ctx.finding.filePath),
        lineStart: (__VLS_ctx.finding.lineStart || 1),
        lineEnd: (__VLS_ctx.finding.lineEnd || __VLS_ctx.finding.lineStart || 1),
        finding: (__VLS_ctx.finding),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClose': {} },
        projectId: (__VLS_ctx.finding.review.project.id),
        branch: (__VLS_ctx.finding.review?.branch || 'main'),
        filePath: (__VLS_ctx.finding.filePath),
        lineStart: (__VLS_ctx.finding.lineStart || 1),
        lineEnd: (__VLS_ctx.finding.lineEnd || __VLS_ctx.finding.lineStart || 1),
        finding: (__VLS_ctx.finding),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ close: {} },
        { onClose: (...[$event]) => {
                if (!(__VLS_ctx.showFileViewer && __VLS_ctx.finding.review?.project?.id))
                    return;
                __VLS_ctx.showFileViewer = false;
                // @ts-ignore
                [finding, finding, finding, finding, finding, finding, finding, finding, showFileViewer, showFileViewer,];
            } });
    var __VLS_3;
    var __VLS_4;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};
