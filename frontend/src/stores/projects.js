import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/composables/useApi';
export const useProjectsStore = defineStore('projects', () => {
    const projects = ref([]);
    const loading = ref(false);
    const selectedProjectId = ref(Number(localStorage.getItem('reviewhub_project_id')) || null);
    async function fetchProjects() {
        loading.value = true;
        try {
            const { data } = await api.projects.list();
            projects.value = data.projects;
            if (!selectedProjectId.value && projects.value.length > 0) {
                selectedProjectId.value = projects.value[0].id;
                localStorage.setItem('reviewhub_project_id', String(selectedProjectId.value));
            }
            if (selectedProjectId.value &&
                !projects.value.some((project) => project.id === selectedProjectId.value)) {
                selectedProjectId.value = projects.value[0]?.id ?? null;
                if (selectedProjectId.value) {
                    localStorage.setItem('reviewhub_project_id', String(selectedProjectId.value));
                }
                else {
                    localStorage.removeItem('reviewhub_project_id');
                }
            }
        }
        finally {
            loading.value = false;
        }
    }
    function setSelectedProject(projectId) {
        selectedProjectId.value = projectId;
        if (projectId) {
            localStorage.setItem('reviewhub_project_id', String(projectId));
        }
        else {
            localStorage.removeItem('reviewhub_project_id');
        }
    }
    return { projects, loading, selectedProjectId, fetchProjects, setSelectedProject };
});
