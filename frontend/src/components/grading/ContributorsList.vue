<template>
  <section class="contributors-section" data-testid="contributors-section">
    <h2>Contributors ({{ contributors.length }})</h2>
    <ul class="contributor-list">
      <li
        v-for="c in sortedContributors"
        :key="c.id"
        class="contributor-row"
        :data-testid="`contributor-${c.user}`"
      >
        <button
          type="button"
          class="contributor-avatar"
          :title="`View ${c.user_name || c.user_email}'s profile`"
          @click="goToProfile(c.user)"
        >
          {{ initials(c.user_name || c.user_email) }}
        </button>
        <div class="contributor-main">
          <div class="contributor-name-row">
            <button
              type="button"
              class="contributor-name-link"
              @click="goToProfile(c.user)"
              :data-testid="`contributor-link-${c.user}`"
            >
              {{ c.user_name || c.user_email }}
            </button>
            <span v-if="c.is_primary_author" class="primary-tag">Primary author</span>
          </div>
          <div class="contributor-stats">
            <span class="stat-chip stat-fraction">
              {{ formatPct(c.contribution_fraction) }}
            </span>
            <span class="stat-chip">{{ c.commits_count }} commits</span>
            <span class="stat-chip">{{ c.lines_changed }} lines</span>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { SubmissionContributor } from '@/stores/grading';

const props = defineProps<{
  contributors: SubmissionContributor[];
}>();

const router = useRouter();

const sortedContributors = computed(() =>
  [...props.contributors].sort((a, b) => {
    // Primary author first; then by contribution_fraction desc.
    if (a.is_primary_author !== b.is_primary_author) {
      return a.is_primary_author ? -1 : 1;
    }
    return (b.contribution_fraction ?? 0) - (a.contribution_fraction ?? 0);
  }),
);

function initials(label: string): string {
  if (!label) return '?';
  const parts = label.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length === 0) return label.slice(0, 2).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function formatPct(fraction: number): string {
  const pct = Math.round((fraction ?? 0) * 100);
  return `${pct}%`;
}

function goToProfile(userId: number) {
  router.push({ name: 'grading-student-profile', params: { id: userId } });
}
</script>

<style scoped>
.contributors-section {
  margin-bottom: 2rem;
  padding: 1rem 1.25rem;
  background: rgb(15 23 42);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.5rem;
}

h2 {
  font-size: 1rem;
  font-weight: 600;
  color: rgb(226 232 240);
  margin: 0 0 0.75rem;
}

.contributor-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.contributor-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.6rem;
  background: rgb(2 6 23);
  border: 1px solid rgb(30 41 59);
  border-radius: 0.375rem;
}

.contributor-avatar {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 9999px;
  background: rgb(30 41 59);
  color: rgb(226 232 240);
  border: 1px solid rgb(51 65 85);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.contributor-avatar:hover {
  background: rgb(51 65 85);
}

.contributor-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.contributor-name-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.contributor-name-link {
  background: transparent;
  border: none;
  padding: 0;
  color: rgb(147 197 253);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  text-align: left;
}

.contributor-name-link:hover {
  text-decoration: underline;
}

.primary-tag {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.1rem 0.4rem;
  border-radius: 0.25rem;
  background: rgb(59 130 246 / 0.2);
  color: rgb(147 197 253);
  border: 1px solid rgb(59 130 246 / 0.4);
}

.contributor-stats {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.stat-chip {
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 0.25rem;
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}

.stat-chip.stat-fraction {
  background: rgb(34 197 94 / 0.15);
  color: rgb(134 239 172);
}
</style>
