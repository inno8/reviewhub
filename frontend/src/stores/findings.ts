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
  fixedAt?: string | null;
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
      
      // Map Django REST Framework response to expected structure
      if (data.results) {
        // DRF paginated response
        findings.value = data.results.map((finding: any) => ({
          id: finding.id,
          commitSha: finding.fixed_in_commit || null,
          commitAuthor: null, // Not in current API response
          filePath: finding.file_path,
          lineStart: finding.line_start,
          lineEnd: finding.line_end,
          explanation: finding.explanation,
          category: mapSeverityToCategory(finding.severity),
          difficulty: 'INTERMEDIATE', // Default for now
          originalCode: finding.original_code,
          optimizedCode: finding.suggested_code,
          prCreated: false,
          prUrl: null,
          fixedAt: finding.fixed_at,
          markedUnderstood: false,
          explanationRequested: false,
          references: [],
          review: {
            branch: 'main',
            reviewDate: finding.created_at,
          }
        }));
        total.value = data.count;
        page.value = nextFilters.page ?? page.value;
        // Calculate total pages from count and limit
        const perPage = nextFilters.limit ?? limit.value;
        totalPages.value = Math.ceil(data.count / perPage);
      } else {
        // Legacy V1 response
        findings.value = data.findings;
        total.value = data.total;
        page.value = data.page;
        totalPages.value = data.totalPages;
      }
      
      limit.value = nextFilters.limit ?? limit.value;
    } finally {
      loading.value = false;
    }
  }
  
  function mapSeverityToCategory(severity: string): string {
    // Map Django severity to V1 categories
    switch (severity) {
      case 'critical':
        return 'SECURITY';
      case 'warning':
        return 'CODE_STYLE';
      case 'info':
        return 'ARCHITECTURE';
      default:
        return 'CODE_STYLE';
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
      
      // Map Django response to expected structure
      const finding = {
        id: data.id,
        commitSha: data.fixed_in_commit || null,
        commitAuthor: null,
        filePath: data.file_path,
        lineStart: data.line_start,
        lineEnd: data.line_end,
        explanation: data.explanation,
        category: mapSeverityToCategory(data.severity),
        difficulty: 'INTERMEDIATE',
        originalCode: data.original_code,
        optimizedCode: data.suggested_code,
        prCreated: false,
        prUrl: null,
        fixedAt: data.fixed_at,
        markedUnderstood: false,
        explanationRequested: false,
        references: [],
        review: {
          branch: 'main',
          reviewDate: data.created_at,
        }
      };
      
      selectedFinding.value = finding;
      findingDetailsCache.value[id] = finding;
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
