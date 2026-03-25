import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/composables/useApi';
export const useFindingsStore = defineStore('findings', () => {
    const findings = ref([]);
    const selectedFinding = ref(null);
    const loading = ref(false);
    const detailsLoading = ref(false);
    const total = ref(0);
    const page = ref(1);
    const totalPages = ref(1);
    const limit = ref(10);
    const filters = ref({});
    const findingDetailsCache = ref({});
    async function fetchFindings(nextFilters = {}) {
        loading.value = true;
        try {
            filters.value = { ...filters.value, ...nextFilters };
            const { data } = await api.findings.list({
                ...filters.value,
                page: nextFilters.page ?? page.value,
                limit: nextFilters.limit ?? limit.value,
            });
            findings.value = data.findings;
            total.value = data.total;
            page.value = data.page;
            totalPages.value = data.totalPages;
            limit.value = nextFilters.limit ?? limit.value;
        }
        finally {
            loading.value = false;
        }
    }
    async function fetchFinding(id) {
        if (findingDetailsCache.value[id]) {
            selectedFinding.value = findingDetailsCache.value[id];
            return;
        }
        detailsLoading.value = true;
        try {
            const { data } = await api.findings.get(id);
            selectedFinding.value = data.finding;
            findingDetailsCache.value[id] = data.finding;
        }
        finally {
            detailsLoading.value = false;
        }
    }
    function clearSelectedFinding() {
        selectedFinding.value = null;
    }
    function setPage(nextPage) {
        page.value = nextPage;
    }
    function setLimit(nextLimit) {
        limit.value = nextLimit;
    }
    return {
        findings,
        selectedFinding,
        loading,
        detailsLoading,
        total,
        page,
        totalPages,
        limit,
        filters,
        fetchFindings,
        fetchFinding,
        clearSelectedFinding,
        setPage,
        setLimit,
    };
});
