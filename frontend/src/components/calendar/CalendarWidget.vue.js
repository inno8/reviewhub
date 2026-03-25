import { computed, ref, onMounted, watch } from 'vue';
import { api } from '@/composables/useApi';
const props = defineProps();
const emit = defineEmits();
const days = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const currentMonth = ref(new Date());
const activeDates = ref(new Set());
const selectedDate = ref(null);
const today = new Date().toISOString().split('T')[0];
const monthString = computed(() => {
    const year = currentMonth.value.getFullYear();
    const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
});
const monthName = computed(() => currentMonth.value.toLocaleDateString('en-US', { month: 'long', year: 'numeric' }));
const firstDayOffset = computed(() => {
    return new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth(), 1).getDay();
});
const daysInMonth = computed(() => new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 0).getDate());
const calendarCells = computed(() => {
    const blanks = Array.from({ length: firstDayOffset.value }, () => null);
    const monthDays = Array.from({ length: daysInMonth.value }, (_, i) => i + 1);
    return [...blanks, ...monthDays];
});
async function fetchActiveDates() {
    if (!props.projectId) {
        activeDates.value = new Set();
        return;
    }
    try {
        const { data } = await api.reviews.calendar(props.projectId, monthString.value);
        activeDates.value = new Set(data.dates);
    }
    catch {
        activeDates.value = new Set();
    }
}
function toDateString(day) {
    const year = currentMonth.value.getFullYear();
    const month = String(currentMonth.value.getMonth() + 1).padStart(2, '0');
    const paddedDay = String(day).padStart(2, '0');
    return `${year}-${month}-${paddedDay}`;
}
function isHighlighted(day) {
    return activeDates.value.has(toDateString(day));
}
function isToday(day) {
    return toDateString(day) === today;
}
function isSelected(day) {
    return toDateString(day) === selectedDate.value;
}
function selectDate(day) {
    const dateStr = toDateString(day);
    if (selectedDate.value === dateStr) {
        selectedDate.value = null;
        emit('dateSelected', null);
    }
    else {
        selectedDate.value = dateStr;
        emit('dateSelected', dateStr);
    }
}
function prevMonth() {
    currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() - 1, 1);
}
function nextMonth() {
    currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 1);
}
onMounted(fetchActiveDates);
watch(() => props.projectId, () => {
    selectedDate.value = null;
    fetchActiveDates();
});
watch(monthString, fetchActiveDates);
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-surface-container-lowest rounded-xl p-3 border border-outline-variant/10" },
});
/** @type {__VLS_StyleScopedClasses['bg-surface-container-lowest']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between mb-3" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text-[10px] uppercase tracking-widest text-outline font-bold" },
});
/** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-widest']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
(__VLS_ctx.monthName);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex gap-1" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.prevMonth) },
    ...{ class: "p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors" },
});
/** @type {__VLS_StyleScopedClasses['p-1']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-surface-container']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-on-surface']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "material-symbols-outlined text-sm" },
});
/** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.nextMonth) },
    ...{ class: "p-1 hover:bg-surface-container rounded text-outline hover:text-on-surface transition-colors" },
});
/** @type {__VLS_StyleScopedClasses['p-1']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-surface-container']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-on-surface']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "material-symbols-outlined text-sm" },
});
/** @type {__VLS_StyleScopedClasses['material-symbols-outlined']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "grid grid-cols-7 gap-1 text-center mb-2" },
});
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-7']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
for (const [day] of __VLS_vFor((__VLS_ctx.days))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        key: (day),
        ...{ class: "text-[8px] text-outline" },
    });
    /** @type {__VLS_StyleScopedClasses['text-[8px]']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    (day);
    // @ts-ignore
    [monthName, prevMonth, nextMonth, days,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "grid grid-cols-7 gap-1 text-[10px]" },
});
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-7']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
for (const [day, index] of __VLS_vFor((__VLS_ctx.calendarCells))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                day && __VLS_ctx.selectDate(day);
                // @ts-ignore
                [calendarCells, selectDate,];
            } },
        key: (`cell-${index}`),
        disabled: (!day),
        ...{ class: ([
                'p-1 text-center rounded transition-all',
                !day && 'invisible',
                day && __VLS_ctx.isToday(day) && !__VLS_ctx.isSelected(day) && 'bg-primary text-on-primary font-bold shadow-lg shadow-primary/20',
                day && __VLS_ctx.isSelected(day) && 'ring-2 ring-primary bg-primary/20 text-primary font-bold',
                day && !__VLS_ctx.isToday(day) && !__VLS_ctx.isSelected(day) && __VLS_ctx.isHighlighted(day) && 'bg-primary-container/20 text-primary border border-primary/30 hover:bg-primary-container/40 cursor-pointer',
                day && !__VLS_ctx.isToday(day) && !__VLS_ctx.isSelected(day) && !__VLS_ctx.isHighlighted(day) && 'text-on-surface-variant hover:bg-surface-container cursor-pointer',
            ]) },
    });
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
    (day || '');
    // @ts-ignore
    [isToday, isToday, isToday, isSelected, isSelected, isSelected, isSelected, isHighlighted, isHighlighted,];
}
if (__VLS_ctx.selectedDate) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mt-3 pt-3 border-t border-outline-variant/10" },
    });
    /** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-outline-variant/10']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-between" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-[10px] text-primary font-bold" },
    });
    /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-primary']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    (__VLS_ctx.selectedDate);
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.selectedDate))
                    return;
                __VLS_ctx.selectDate(parseInt(__VLS_ctx.selectedDate.split('-')[2]));
                // @ts-ignore
                [selectDate, selectedDate, selectedDate, selectedDate,];
            } },
        ...{ class: "text-[10px] text-outline hover:text-error" },
    });
    /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-outline']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-error']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
    __typeProps: {},
});
export default {};
