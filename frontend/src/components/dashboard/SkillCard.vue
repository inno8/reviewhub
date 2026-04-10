<script setup lang="ts">
interface Skill {
  id: number;
  displayName: string;
  score: number;
  level: number;
}

interface SkillCategory {
  id: number;
  name: string;
  displayName: string;
  description: string;
  icon: string;
  skills: Skill[];
}

const props = defineProps<{
  category: SkillCategory;
}>();

const emit = defineEmits<{
  'click-skill': [skillId: number];
}>();

function getSkillLevel(score: number): string {
  if (score >= 90) return 'Expert';
  if (score >= 75) return 'Advanced';
  if (score >= 50) return 'Intermediate';
  if (score >= 25) return 'Developing';
  return 'Beginner';
}

function getSkillBarColor(score: number): string {
  if (score >= 90) return 'bg-primary';
  if (score >= 75) return 'bg-green-500';
  if (score >= 50) return 'bg-yellow-500';
  if (score >= 25) return 'bg-orange-500';
  return 'bg-red-500';
}

function categoryAverage(category: SkillCategory): number {
  if (!category.skills.length) return 0;
  const total = category.skills.reduce((sum, s) => sum + s.score, 0);
  return Math.round(total / category.skills.length);
}

function getLevelColor(level: string): string {
  switch (level) {
    case 'Expert': return 'text-primary';
    case 'Advanced': return 'text-green-500';
    case 'Intermediate': return 'text-yellow-500';
    case 'Developing': return 'text-orange-500';
    default: return 'text-red-500';
  }
}
</script>

<template>
  <div class="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10 hover:border-primary/20 transition-all">
    <!-- Category Header -->
    <div class="flex items-center gap-3 mb-6 pb-4 border-b border-outline-variant/10">
      <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
        <span class="material-symbols-outlined text-primary">{{ category.icon }}</span>
      </div>
      <div class="flex-1">
        <h5 class="font-bold text-lg">{{ category.displayName }}</h5>
        <p class="text-xs text-outline">{{ category.skills.length }} skills</p>
      </div>
      <div class="text-right">
        <div class="text-2xl font-black text-primary">{{ categoryAverage(category) }}%</div>
        <p class="text-xs text-outline">Average</p>
      </div>
    </div>

    <!-- Skills List -->
    <div class="space-y-4">
      <div
        v-for="skill in category.skills"
        :key="skill.id"
        class="space-y-2 cursor-pointer hover:bg-surface-container-lowest rounded-lg p-1 -m-1 transition-colors"
        @click="emit('click-skill', skill.id)"
      >
        <div class="flex justify-between text-sm">
          <span class="font-medium">{{ skill.displayName }}</span>
          <div class="flex items-center gap-2">
            <span :class="['text-xs font-bold', getLevelColor(getSkillLevel(skill.score))]">
              {{ getSkillLevel(skill.score) }}
            </span>
            <span class="text-outline">{{ skill.score }}%</span>
          </div>
        </div>
        <div class="h-2 bg-surface-container-highest rounded-full overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="getSkillBarColor(skill.score)"
            :style="{ width: skill.score + '%' }"
          ></div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="category.skills.length === 0" class="text-center py-8">
      <span class="material-symbols-outlined text-2xl text-outline mb-2">school</span>
      <p class="text-sm text-outline">No skills in this category yet</p>
    </div>
  </div>
</template>
