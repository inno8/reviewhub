import { ref } from 'vue';
import { defineStore } from 'pinia';
import { useApi } from '@/composables/useApi';

interface Project {
  id: number;
  name: string;
  displayName: string;
}

export const useProjectsStore = defineStore('projects', () => {
  const api = useApi();
  const projects = ref<Project[]>([]);
  const loading = ref(false);

  async function fetchProjects() {
    loading.value = true;
    try {
      const { data } = await api.get('/projects');
      projects.value = data.projects;
    } finally {
      loading.value = false;
    }
  }

  return { projects, loading, fetchProjects };
});
