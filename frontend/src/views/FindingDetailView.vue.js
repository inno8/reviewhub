import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import AppShell from '@/components/layout/AppShell.vue';
import DiffViewer from '@/components/code/DiffViewer.vue';
import FileViewer from '@/components/code/FileViewer.vue';
import { useFindingsStore } from '@/stores/findings';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/composables/useApi';
const route = useRoute();
const findingsStore = useFindingsStore();
const auth = useAuthStore();
const toastMessage = ref('');
const actionLoading = ref(false);
const applyFixLoading = ref(false);
const errorMessage = ref('');
const showFileViewer = ref(false);
const findingId = computed(() => Number(route.params.id));
const finding = computed(() => findingsStore.selectedFinding);
const references = computed(() => {
    const raw = finding.value?.references;
    if (!raw)
        return [];
    return Array.isArray(raw) ? raw : [];
});
const hasRealCode = computed(() => {
    const code = finding.value?.originalCode;
    return code && code.trim() !== '' && !code.trim().startsWith('//');
});
const categoryClass = computed(() => {
    const cat = finding.value?.category?.toLowerCase().replace('_', '');
    return {
        security: 'bg-error/10 text-error border-error/20',
        performance: 'bg-tertiary/10 text-tertiary border-tertiary/20',
        codestyle: 'bg-primary/10 text-primary border-primary/20',
        testing: 'bg-primary-container/10 text-primary-container border-primary-container/20',
    }[cat || ''] || 'bg-outline/10 text-outline border-outline/20';
});
const difficultyClass = computed(() => {
    const diff = finding.value?.difficulty?.toLowerCase();
    return {
        beginner: 'bg-secondary-container/10 text-secondary border-secondary-container/20',
        intermediate: 'bg-tertiary-container/10 text-tertiary-container border-tertiary-container/20',
        advanced: 'bg-error/10 text-error border-error/20',
    }[diff || ''] || 'bg-outline/10 text-outline border-outline/20';
});
onMounted(async () => {
    if (!Number.isNaN(findingId.value)) {
        await findingsStore.fetchFinding(findingId.value);
    }
});
async function markUnderstood() {
    if (!findingId.value)
        return;
    actionLoading.value = true;
    try {
        const { data } = await api.findings.markUnderstood(findingId.value);
        if (finding.value) {
            finding.value.markedUnderstood = data.markedUnderstood;
        }
        toastMessage.value = 'Understanding state saved.';
    }
    finally {
        actionLoading.value = false;
    }
}
async function requestExplanation() {
    if (!findingId.value)
        return;
    actionLoading.value = true;
    try {
        await api.findings.requestExplanation(findingId.value);
        if (finding.value) {
            finding.value.explanationRequested = true;
        }
        toastMessage.value = 'Explanation requested successfully.';
    }
    finally {
        actionLoading.value = false;
    }
}
async function applyFixAndCreatePr() {
    if (!findingId.value || !finding.value)
        return;
    applyFixLoading.value = true;
    errorMessage.value = '';
    try {
        const { data } = await api.findings.applyFix(findingId.value);
        finding.value.prCreated = true;
        finding.value.prUrl = data.prUrl;
        toastMessage.value = 'Pull request created successfully.';
    }
    catch (error) {
        errorMessage.value = error?.response?.data?.error || 'Failed to create pull request.';
    }
    finally {
        applyFixLoading.value = false;
    }
}
function clearToast() {
    toastMessage.value = '';
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
const __VLS_0 = AppShell || AppShell;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5 = {};
const { default: __VLS_6 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "p-8 flex-1" },
});
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
if (__VLS_ctx.finding) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "max-w-[90rem] mx-auto space-y-8" },
    });
    /** @type {__VLS_StyleScopedClasses['max-w-[90rem]']} */ ;
    /** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-8']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "flex flex-col md:flex-row md:items-end justify-between gap-6" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['md:flex-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['md:items-end']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-3" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-2 text-outline text-sm font-mono bg-surface-container-low px-3 py-1.5 rounded-lg w-fit" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-surface-container-low']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-fit']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (__VLS_ctx.finding.filePath);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "mx-1 text-outline-variant" },
    });
    /** @type {__VLS_StyleScopedClasses['mx-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline-variant']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-primary-fixed-dim" },
    });
    /** @type {__VLS_StyleScopedClasses['text-primary-fixed-dim']} */ ;
    (__VLS_ctx.finding.review?.branch || 'main');
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-3xl font-bold tracking-tight text-on-surface" },
    });
    /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-tight']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-on-surface']} */ ;
    (__VLS_ctx.finding.filePath.split('/').pop());
    if (__VLS_ctx.finding.review?.project?.id) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.finding))
                        return;
                    if (!(__VLS_ctx.finding.review?.project?.id))
                        return;
                    __VLS_ctx.showFileViewer = true;
                    // @ts-ignore
                    [finding, finding, finding, finding, finding, showFileViewer,];
                } },
            ...{ class: "mt-2 flex items-center gap-1.5 text-sm text-primary font-medium hover:underline" },
        });
        /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "material-symbols-outlined text-sm" },
        });
        /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex flex-wrap gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (['px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border', __VLS_ctx.categoryClass]) },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-xs" },
        ...{ style: {} },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    (__VLS_ctx.finding.category.replace('_', ' '));
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (['px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border', __VLS_ctx.difficultyClass]) },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-xs" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    (__VLS_ctx.finding.difficulty);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20 text-xs font-bold" },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-primary/10']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-primary/20']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    (__VLS_ctx.finding.id);
    if (__VLS_ctx.hasRealCode) {
        const __VLS_7 = DiffViewer;
        // @ts-ignore
        const __VLS_8 = __VLS_asFunctionalComponent1(__VLS_7, new __VLS_7({
            finding: (__VLS_ctx.finding),
        }));
        const __VLS_9 = __VLS_8({
            finding: (__VLS_ctx.finding),
        }, ...__VLS_functionalComponentArgsRest(__VLS_8));
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
            ...{ class: "bg-surface-container rounded-xl p-8 text-center space-y-4 border border-outline-variant/10" },
        });
        /** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "material-symbols-outlined text-5xl text-outline/40" },
        });
        /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-5xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-outline/40']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-on-surface-variant text-lg" },
        });
        /** @type {__VLS_StyleScopedClasses['text-on-surface-variant']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
        if (__VLS_ctx.finding.optimizedCode) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "bg-surface-container-low rounded-lg p-6 text-left max-w-2xl mx-auto" },
            });
            /** @type {__VLS_StyleScopedClasses['bg-surface-container-low']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['max-w-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
                ...{ class: "text-sm font-bold text-outline uppercase tracking-wider mb-2" },
            });
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wider']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "text-on-surface leading-relaxed" },
            });
            /** @type {__VLS_StyleScopedClasses['text-on-surface']} */ ;
            /** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
            (__VLS_ctx.finding.optimizedCode);
        }
        if (__VLS_ctx.finding.review?.project?.id) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.finding))
                            return;
                        if (!!(__VLS_ctx.hasRealCode))
                            return;
                        if (!(__VLS_ctx.finding.review?.project?.id))
                            return;
                        __VLS_ctx.showFileViewer = true;
                        // @ts-ignore
                        [finding, finding, finding, finding, finding, finding, finding, showFileViewer, categoryClass, difficultyClass, hasRealCode,];
                    } },
                ...{ class: "mt-2 px-6 py-3 primary-gradient text-on-primary font-bold rounded-lg inline-flex items-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-[0.98]" },
            });
            /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-6']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['primary-gradient']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-on-primary']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['shadow-primary/10']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:shadow-primary/20']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
            /** @type {__VLS_StyleScopedClasses['active:scale-[0.98]']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "material-symbols-outlined" },
            });
            /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
            (__VLS_ctx.finding.filePath);
        }
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "bg-surface-container-low rounded-xl p-8 border border-outline-variant/10 relative overflow-hidden" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-surface-container-low']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
    /** @type {__VLS_StyleScopedClasses['relative']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "absolute top-0 right-0 p-8 opacity-5" },
    });
    /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
    /** @type {__VLS_StyleScopedClasses['top-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['right-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['opacity-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-9xl" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-9xl']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "relative z-10 max-w-3xl" },
    });
    /** @type {__VLS_StyleScopedClasses['relative']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-10']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-3xl']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
        ...{ class: "text-xl font-bold text-on-surface mb-4 flex items-center gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-on-surface']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-primary" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-on-surface-variant leading-relaxed mb-6" },
    });
    /** @type {__VLS_StyleScopedClasses['text-on-surface-variant']} */ ;
    /** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    (__VLS_ctx.finding.explanation);
    if (__VLS_ctx.references.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "space-y-2" },
        });
        /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
            ...{ class: "text-sm font-bold text-outline uppercase tracking-wider" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wider']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
            ...{ class: "space-y-1" },
        });
        /** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
        for (const [ref, idx] of __VLS_vFor((__VLS_ctx.references))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                key: (idx),
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
                href: (typeof ref === 'string' ? ref : ref.url),
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
            (typeof ref === 'string' ? ref : ref.title || ref.url);
            // @ts-ignore
            [finding, finding, references, references,];
        }
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.section, __VLS_intrinsics.section)({
        ...{ class: "flex flex-col md:flex-row items-center justify-between gap-6 pt-4 border-t border-outline-variant/10" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['md:flex-row']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "flex items-center gap-3 cursor-pointer group" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
    /** @type {__VLS_StyleScopedClasses['group']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        ...{ onChange: (__VLS_ctx.markUnderstood) },
        type: "checkbox",
        checked: (!!__VLS_ctx.finding.markedUnderstood),
        disabled: (__VLS_ctx.actionLoading),
        ...{ class: "h-5 w-5 rounded border-outline-variant bg-surface-container text-primary focus:ring-primary focus:ring-offset-background" },
    });
    /** @type {__VLS_StyleScopedClasses['h-5']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-surface-container']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-offset-background']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-sm font-medium text-on-surface-variant group-hover:text-on-surface transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-on-surface-variant']} */ ;
    /** @type {__VLS_StyleScopedClasses['group-hover:text-on-surface']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-3 w-full md:w-auto" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['md:w-auto']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.requestExplanation) },
        disabled: (__VLS_ctx.actionLoading || __VLS_ctx.finding.explanationRequested),
        ...{ class: "flex-1 md:flex-none px-6 py-3 border border-outline-variant/30 rounded-lg flex items-center justify-center gap-2 text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-all active:scale-[0.98] disabled:opacity-50" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['md:flex-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/30']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-on-surface-variant']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-surface-container-high']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-on-surface']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
    /** @type {__VLS_StyleScopedClasses['active:scale-[0.98]']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    (__VLS_ctx.finding.explanationRequested ? 'Requested' : 'Request Explanation');
    if (__VLS_ctx.auth.isAdmin) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (__VLS_ctx.applyFixAndCreatePr) },
            disabled: (__VLS_ctx.applyFixLoading || !!__VLS_ctx.finding.prCreated),
            ...{ class: "flex-1 md:flex-none px-8 py-3 primary-gradient text-on-primary font-bold rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-primary/10 hover:shadow-primary/20 transition-all active:scale-[0.98] disabled:opacity-50" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['md:flex-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['primary-gradient']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-on-primary']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow-primary/10']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:shadow-primary/20']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
        /** @type {__VLS_StyleScopedClasses['active:scale-[0.98]']} */ ;
        /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "material-symbols-outlined" },
            ...{ style: {} },
        });
        /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
        (__VLS_ctx.finding.prCreated ? 'PR Created' : __VLS_ctx.applyFixLoading ? 'Creating...' : 'Apply Fix & Create PR');
    }
    if (__VLS_ctx.finding.prUrl) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-sm text-primary" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
            href: (__VLS_ctx.finding.prUrl),
            target: "_blank",
            rel: "noopener noreferrer",
            ...{ class: "underline hover:opacity-80" },
        });
        /** @type {__VLS_StyleScopedClasses['underline']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:opacity-80']} */ ;
        (__VLS_ctx.finding.prUrl);
    }
    if (__VLS_ctx.errorMessage) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-sm text-error" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-error']} */ ;
        (__VLS_ctx.errorMessage);
    }
    if (__VLS_ctx.showFileViewer && __VLS_ctx.finding.review?.project?.id) {
        const __VLS_12 = FileViewer;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent1(__VLS_12, new __VLS_12({
            ...{ 'onClose': {} },
            projectId: (__VLS_ctx.finding.review.project.id),
            branch: (__VLS_ctx.finding.review?.branch || 'main'),
            filePath: (__VLS_ctx.finding.filePath),
            lineStart: (__VLS_ctx.finding.lineStart || 1),
            lineEnd: (__VLS_ctx.finding.lineEnd || __VLS_ctx.finding.lineStart || 1),
            finding: (__VLS_ctx.finding),
        }));
        const __VLS_14 = __VLS_13({
            ...{ 'onClose': {} },
            projectId: (__VLS_ctx.finding.review.project.id),
            branch: (__VLS_ctx.finding.review?.branch || 'main'),
            filePath: (__VLS_ctx.finding.filePath),
            lineStart: (__VLS_ctx.finding.lineStart || 1),
            lineEnd: (__VLS_ctx.finding.lineEnd || __VLS_ctx.finding.lineStart || 1),
            finding: (__VLS_ctx.finding),
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        let __VLS_17;
        const __VLS_18 = ({ close: {} },
            { onClose: (...[$event]) => {
                    if (!(__VLS_ctx.finding))
                        return;
                    if (!(__VLS_ctx.showFileViewer && __VLS_ctx.finding.review?.project?.id))
                        return;
                    __VLS_ctx.showFileViewer = false;
                    // @ts-ignore
                    [finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, finding, showFileViewer, showFileViewer, markUnderstood, actionLoading, actionLoading, requestExplanation, auth, applyFixAndCreatePr, applyFixLoading, applyFixLoading, errorMessage, errorMessage,];
                } });
        var __VLS_15;
        var __VLS_16;
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-center h-64" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-64']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "material-symbols-outlined text-4xl text-outline animate-spin" },
    });
    /** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    /** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
}
if (__VLS_ctx.toastMessage) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (__VLS_ctx.clearToast) },
        ...{ class: "fixed bottom-4 right-4 rounded-lg bg-primary/20 border border-primary/30 px-4 py-2 text-sm text-primary shadow-lg cursor-pointer" },
    });
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['bottom-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['right-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-primary/20']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-primary/30']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
    (__VLS_ctx.toastMessage);
}
// @ts-ignore
[toastMessage, toastMessage, clearToast,];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};
