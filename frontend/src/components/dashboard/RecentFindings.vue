<script setup lang="ts">
interface Skill {
  id: number;
  name: string;
  category: string;
}

interface Finding {
  id: number;
  title: string;
  description: string;
  severity: string;
  file_path: string;
  line_start: number;
  is_fixed: boolean;
  created_at: string;
  skills: Skill[];
}

const props = withDefaults(
  defineProps<{
    findings: Finding[];
    title?: string;
  }>(),
  {
    title: 'Recent Findings'
  }
);

function getSeverityClass(severity: string) {
  const sev = severity.toLowerCase();
  return {
    critical: 'bg-error/10 text-error border-error/20',
    warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    info: 'bg-primary/10 text-primary border-primary/20',
    suggestion: 'bg-outline/10 text-outline border-outline/20',
  }[sev] || 'bg-outline/10 text-outline border-outline/20';
}

function getSeverityIcon(severity: string) {
  const sev = severity.toLowerCase();
  return {
    critical: 'error',
    warning: 'warning',
    info: 'info',
    suggestion: 'lightbulb',
  }[sev] || 'info';
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function truncate(text: string, maxLength: number = 80) {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}
</script>

<template>
  <div class="bg-surface-container-low rounded-2xl p-6 border border-outline-variant/10">
    <h4 class="text-xl font-bold mb-6">{{ title }}</h4>
    
    <div v-if="findings.length > 0" class="space-y-3">
      <div
        v-for="finding in findings"
        :key="finding.id"
        class="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10 hover:border-primary/20 transition-all cursor-pointer group"
      >
        <!-- Header -->
        <div class="flex items-start justify-between mb-3">
          <div class="flex items-center gap-3 flex-1">
            <span
              class="material-symbols-outlined text-lg"
              :class="getSeverityClass(finding.severity).split(' ')[1]"
            >
              {{ getSeverityIcon(finding.severity) }}
            </span>
            <div class="flex-1 min-w-0">
              <h5 class="font-bold text-sm truncate group-hover:text-primary transition-colors">
                {{ finding.title }}
              </h5>
              <p class="text-xs text-outline font-mono mt-1 truncate">
                {{ finding.file_path }}:{{ finding.line_start }}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span
              v-if="finding.is_fixed"
              class="flex items-center gap-1 text-xs font-bold text-primary bg-primary/10 px-2 py-1 rounded-full"
            >
              <span class="material-symbols-outlined text-xs">check_circle</span>
              Fixed
            </span>
            <span
              :class="['px-2 py-1 rounded-full text-[10px] font-bold uppercase border', getSeverityClass(finding.severity)]"
            >
              {{ finding.severity }}
            </span>
          </div>
        </div>

        <!-- Description -->
        <p class="text-sm text-on-surface-variant mb-3">
          {{ truncate(finding.description) }}
        </p>

        <!-- Footer -->
        <div class="flex items-center justify-between">
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="skill in finding.skills"
              :key="skill.id"
              class="text-[10px] font-bold px-2 py-0.5 bg-surface-container rounded-full text-outline border border-outline-variant/20"
            >
              {{ skill.name }}
            </span>
          </div>
          <span class="text-xs text-outline">
            {{ formatDate(finding.created_at) }}
          </span>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8">
      <span class="material-symbols-outlined text-4xl text-outline mb-2">inbox</span>
      <p class="text-sm text-outline">No recent findings</p>
    </div>
  </div>
</template>
