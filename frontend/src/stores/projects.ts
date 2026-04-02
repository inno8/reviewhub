import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/composables/useApi';

interface Project {
  id: number;
  name: string;
  displayName: string;
  description?: string;
  /** Set when the project is linked to a Git remote (developer New Review flow). */
  repoUrl: string | null;
}

function mapApiProject(project: any): Project {
  const repoRaw = project.repoUrl ?? project.repo_url;
  return {
    id: project.id,
    name: project.name,
    displayName: project.name,
    description: project.description ?? '',
    repoUrl: typeof repoRaw === 'string' && repoRaw.trim() ? repoRaw.trim() : null,
  };
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
      
      // Map Django DRF response (paginated or plain)
      if (data.results) {
        projects.value = data.results.map(mapApiProject);
      } else if (data.projects) {
        projects.value = data.projects.map(mapApiProject);
      } else if (Array.isArray(data)) {
        projects.value = data.map(mapApiProject);
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

  function updateProjectRepoUrl(projectId: number, repoUrl: string) {
    const p = projects.value.find(proj => proj.id === projectId);
    if (p) p.repoUrl = repoUrl || null;
  }

  return { projects, loading, selectedProjectId, fetchProjects, setSelectedProject, updateProjectRepoUrl };
});
