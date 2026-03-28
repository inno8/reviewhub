import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/composables/useApi';

interface Project {
  id: number;
  name: string;
  displayName: string;
}

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<Project[]>([]);
  const loading = ref(false);
  const selectedProjectId = ref<number | null>(
    Number(localStorage.getItem('reviewhub_project_id')) || null,
  );

  async function fetchProjects() {
    loading.value = true;
    try {
      const { data } = await api.projects.list();
      
      // Map Django DRF response to expected structure
      if (data.results) {
        projects.value = data.results.map((project: any) => ({
          id: project.id,
          name: project.name,
          displayName: project.name, // Use same name for display
        }));
      } else if (data.projects) {
        // Legacy V1 response
        projects.value = data.projects;
      } else if (Array.isArray(data)) {
        // Direct array response
        projects.value = data.map((project: any) => ({
          id: project.id,
          name: project.name,
          displayName: project.name,
        }));
      } else {
        projects.value = [];
      }
      
      if (!selectedProjectId.value && projects.value.length > 0) {
        selectedProjectId.value = projects.value[0].id;
        localStorage.setItem('reviewhub_project_id', String(selectedProjectId.value));
      }
      if (
        selectedProjectId.value &&
        projects.value.length > 0 &&
        !projects.value.some((project) => project.id === selectedProjectId.value)
      ) {
        selectedProjectId.value = projects.value[0]?.id ?? null;
        if (selectedProjectId.value) {
          localStorage.setItem('reviewhub_project_id', String(selectedProjectId.value));
        } else {
          localStorage.removeItem('reviewhub_project_id');
        }
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      projects.value = [];
    } finally {
      loading.value = false;
    }
  }

  function setSelectedProject(projectId: number | null) {
    selectedProjectId.value = projectId;
    if (projectId) {
      localStorage.setItem('reviewhub_project_id', String(projectId));
    } else {
      localStorage.removeItem('reviewhub_project_id');
    }
  }

  return { projects, loading, selectedProjectId, fetchProjects, setSelectedProject };
});
