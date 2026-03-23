import { ref } from 'vue';
import { defineStore } from 'pinia';
import { useApi } from '@/composables/useApi';

export interface Finding {
  id: number;
  filePath: string;
  explanation: string;
  category: string;
  difficulty: string;
  originalCode: string;
  optimizedCode: string;
  references?: Array<{ type: 'docs' | 'article' | 'tutorial'; title: string; url: string }>;
  review?: {
    project?: {
      displayName: string;
    };
  };
}

export const useFindingsStore = defineStore('findings', () => {
  const api = useApi();
  const findings = ref<Finding[]>([]);
  const selectedFinding = ref<Finding | null>(null);
  const loading = ref(false);

  async function fetchFindings() {
    loading.value = true;
    try {
      const { data } = await api.get('/findings');
      findings.value = data.findings;
    } finally {
      loading.value = false;
    }
  }

  async function fetchFinding(id: number) {
    loading.value = true;
    try {
      const { data } = await api.get(`/findings/${id}`);
      selectedFinding.value = data.finding;
    } finally {
      loading.value = false;
    }
  }

  return { findings, selectedFinding, loading, fetchFindings, fetchFinding };
});
