import { computed } from 'vue';
import Card from '@/components/common/Card.vue';
const props = withDefaults(defineProps(), {
    title: 'Trend Chart',
    width: 640,
    height: 240,
});
const padding = { top: 20, right: 20, bottom: 40, left: 36 };
const maxValue = computed(() => Math.max(1, ...props.points.map((point) => point.value)));
const minValue = computed(() => Math.min(0, ...props.points.map((point) => point.value)));
const range = computed(() => Math.max(1, maxValue.value - minValue.value));
const chartWidth = computed(() => props.width - padding.left - padding.right);
const chartHeight = computed(() => props.height - padding.top - padding.bottom);
const chartPoints = computed(() => props.points.map((point, index) => {
    const x = props.points.length <= 1
        ? padding.left + chartWidth.value / 2
        : padding.left + (index / (props.points.length - 1)) * chartWidth.value;
    const y = padding.top + ((maxValue.value - point.value) / range.value) * chartHeight.value;
    return { ...point, x, y };
}));
const linePath = computed(() => {
    if (!chartPoints.value.length)
        return '';
    return chartPoints.value
        .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
        .join(' ');
});
const areaPath = computed(() => {
    if (!chartPoints.value.length)
        return '';
    const first = chartPoints.value[0];
    const last = chartPoints.value[chartPoints.value.length - 1];
    const baseline = props.height - padding.bottom;
    return `${linePath.value} L ${last.x} ${baseline} L ${first.x} ${baseline} Z`;
});
const yTicks = computed(() => {
    const steps = 4;
    return Array.from({ length: steps + 1 }, (_, index) => {
        const value = minValue.value + ((range.value / steps) * index);
        const y = padding.top + chartHeight.value - (index / steps) * chartHeight.value;
        return { value: Math.round(value), y };
    });
});
const __VLS_defaults = {
    title: 'Trend Chart',
    width: 640,
    height: 240,
};
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
const __VLS_0 = Card || Card;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_5 = {};
const { default: __VLS_6 } = __VLS_3.slots;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "mb-3 text-lg font-semibold" },
});
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
(__VLS_ctx.title);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "rounded-lg border border-border bg-bg-darkest p-3" },
});
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-border']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-bg-darkest']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)({
    viewBox: (`0 0 ${__VLS_ctx.width} ${__VLS_ctx.height}`),
    ...{ class: "h-56 w-full" },
});
/** @type {__VLS_StyleScopedClasses['h-56']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
for (const [tick] of __VLS_vFor((__VLS_ctx.yTicks))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.line)({
        key: (`grid-${tick.y}`),
        x1: (__VLS_ctx.padding.left),
        x2: (__VLS_ctx.width - __VLS_ctx.padding.right),
        y1: (tick.y),
        y2: (tick.y),
        stroke: "#30363D",
        'stroke-width': "1",
        'stroke-dasharray': "4 4",
    });
    // @ts-ignore
    [title, width, width, height, yTicks, padding, padding,];
}
for (const [tick] of __VLS_vFor((__VLS_ctx.yTicks))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.text, __VLS_intrinsics.text)({
        key: (`label-${tick.y}`),
        x: (__VLS_ctx.padding.left - 8),
        y: (tick.y + 4),
        fill: "#8B949E",
        'font-size': "10",
        'text-anchor': "end",
    });
    (tick.value);
    // @ts-ignore
    [yTicks, padding,];
}
if (__VLS_ctx.areaPath) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.path)({
        d: (__VLS_ctx.areaPath),
        fill: "rgba(88, 166, 255, 0.16)",
    });
}
if (__VLS_ctx.linePath) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.path)({
        d: (__VLS_ctx.linePath),
        fill: "none",
        stroke: "#58A6FF",
        'stroke-width': "2.5",
    });
}
for (const [point] of __VLS_vFor((__VLS_ctx.chartPoints))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.circle)({
        key: (point.label),
        cx: (point.x),
        cy: (point.y),
        r: "3.5",
        fill: "#58A6FF",
    });
    // @ts-ignore
    [areaPath, areaPath, linePath, linePath, chartPoints,];
}
for (const [point] of __VLS_vFor((__VLS_ctx.chartPoints))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.text, __VLS_intrinsics.text)({
        key: (`x-${point.label}`),
        x: (point.x),
        y: (__VLS_ctx.height - 14),
        fill: "#8B949E",
        'font-size': "10",
        'text-anchor': "middle",
    });
    (point.label);
    // @ts-ignore
    [height, chartPoints,];
}
if (!__VLS_ctx.points.length) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "px-2 pb-1 text-sm text-text-secondary" },
    });
    /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['pb-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-text-secondary']} */ ;
}
// @ts-ignore
[points,];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
    props: {},
});
export default {};
