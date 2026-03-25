import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api, type FindingFilters } from '@/composables/useApi';

export interface Finding {
  id: number;
  commitSha?: string | null;
  commitAuthor?: string | null;
  filePath: string;
  lineStart?: number | null;
  lineEnd?: number | null;
  explanation: string;
  category: string;
  difficulty: string;
  originalCode: string;
  optimizedCode: string;
  prCreated?: boolean;
  prUrl?: string | null;
  markedUnderstood?: boolean;
  explanationRequested?: boolean;
  references?: Array<{ type: 'docs' | 'article' | 'tutorial'; title: string; url: string }>;
  review?: {
    branch?: string;
    reviewDate?: string;
    project?: {
      id: number;
      displayName: string;
      githubOwner?: string;
      githubRepo?: string;
    };
  };
}

export const useFindingsStore = defineStore('findings', () => {
  const findings = ref<Finding[]>([]);
  const selectedFinding = ref<Finding | null>(null);
  const loading = ref(false);
  const detailsLoading = ref(false);
  const total = ref(0);
  const page = ref(1);
  const totalPages = ref(1);
  const limit = ref(10);
  const filters = ref<FindingFilters>({});
  const findingDetailsCache = ref<Record<number, Finding>>({});

  async function fetchFindings(nextFilters: FindingFilters = {}) {
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
    } finally {
      loading.value = false;
    }
  }

  async function fetchFinding(id: number) {
    if (findingDetailsCache.value[id]) {
      selectedFinding.value = findingDetailsCache.value[id];
      return;
    }
    detailsLoading.value = true;
    try {
      const { data } = await api.findings.get(id);
      selectedFinding.value = data.finding;
      findingDetailsCache.value[id] = data.finding;
    } finally {
      detailsLoading.value = false;
    }
  }

  function clearSelectedFinding() {
    selectedFinding.value = null;
  }

  function setPage(nextPage: number) {
    page.value = nextPage;
  }

  function setLimit(nextLimit: number) {
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
