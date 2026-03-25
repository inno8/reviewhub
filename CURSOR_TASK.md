# ReviewHub: Skill Breakdown Dialog + Fix Stats

## Task 1: Skill Calculation Breakdown Dialog

Create a modal that shows HOW a skill score was calculated, with the specific findings that affected it.

### 1.1 Backend: Add Skill Breakdown Endpoint

**File:** `backend/src/routes/skills.ts`

```typescript
// GET /api/skills/user/:userId/breakdown/:skillId?projectId=X
// Returns detailed breakdown of how skill score was calculated
router.get('/user/:userId/breakdown/:skillId', async (req, res) => {
  const { userId, skillId } = req.params;
  const projectId = Number(req.query.projectId);
  
  // Get skill with detection rules
  const skill = await prisma.skill.findUnique({
    where: { id: Number(skillId) },
    include: { category: true }
  });
  
  // Get findings that matched this skill's rules
  const findings = await getSkillFindings(Number(userId), projectId, skill);
  
  // Return breakdown
  res.json({
    skill: {
      id: skill.id,
      name: skill.displayName,
      description: skill.description,
      category: skill.category.displayName
    },
    score: userSkill.score,
    level: getLevel(userSkill.score),
    breakdown: {
      baseScore: 100,
      deductions: findings.map(f => ({
        findingId: f.id,
        filePath: f.filePath,
        explanation: f.explanation,
        impact: -5, // Points deducted
        rule: matchedRule,
        date: f.review.reviewDate
      })),
      finalScore: userSkill.score
    },
    howToImprove: getImprovementTips(skill.name)
  });
});
```

### 1.2 Frontend: Create SkillBreakdownDialog.vue

**File:** `frontend/src/components/skills/SkillBreakdownDialog.vue`

```vue
<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-surface-container rounded-2xl shadow-xl w-[600px] max-h-[80vh] overflow-hidden">
      <!-- Header -->
      <div class="p-6 border-b border-outline-variant/10">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <span class="material-symbols-outlined text-primary">{{ categoryIcon }}</span>
          </div>
          <div>
            <h3 class="text-xl font-bold">{{ skill?.name }}</h3>
            <p class="text-sm text-outline">{{ skill?.category }}</p>
          </div>
          <div class="ml-auto text-right">
            <div class="text-3xl font-black" :class="scoreColor">{{ score }}%</div>
            <div class="text-xs font-bold uppercase tracking-wider" :class="levelColor">{{ level }}</div>
          </div>
        </div>
      </div>
      
      <!-- Score Breakdown -->
      <div class="p-6 space-y-6 overflow-y-auto max-h-[50vh]">
        <div>
          <h4 class="font-bold mb-3 flex items-center gap-2">
            <span class="material-symbols-outlined text-sm">calculate</span>
            Score Calculation
          </h4>
          <div class="bg-surface-container-low rounded-xl p-4 space-y-2">
            <div class="flex justify-between">
              <span>Base Score</span>
              <span class="font-bold text-primary">100%</span>
            </div>
            <div v-for="(deduction, i) in breakdown?.deductions" :key="i" 
                 class="flex justify-between text-error">
              <span class="text-sm truncate flex-1">{{ deduction.explanation.slice(0, 50) }}...</span>
              <span class="font-bold ml-2">{{ deduction.impact }}%</span>
            </div>
            <div class="border-t border-outline-variant/20 pt-2 flex justify-between font-bold">
              <span>Final Score</span>
              <span :class="scoreColor">{{ score }}%</span>
            </div>
          </div>
        </div>
        
        <!-- Findings that affected this skill -->
        <div>
          <h4 class="font-bold mb-3 flex items-center gap-2">
            <span class="material-symbols-outlined text-sm">warning</span>
            Issues Affecting This Skill ({{ breakdown?.deductions.length || 0 }})
          </h4>
          <div class="space-y-2">
            <div v-for="deduction in breakdown?.deductions" :key="deduction.findingId"
                 class="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
              <div class="flex items-start gap-3">
                <span class="material-symbols-outlined text-error text-sm mt-0.5">error</span>
                <div class="flex-1">
                  <p class="text-sm font-medium">{{ deduction.explanation }}</p>
                  <p class="text-xs text-outline mt-1">
                    <span class="font-mono">{{ deduction.filePath }}</span>
                    • {{ formatDate(deduction.date) }}
                  </p>
                </div>
                <router-link :to="`/findings/${deduction.findingId}`" 
                             class="text-primary text-xs hover:underline">
                  View →
                </router-link>
              </div>
            </div>
          </div>
        </div>
        
        <!-- How to Improve -->
        <div>
          <h4 class="font-bold mb-3 flex items-center gap-2">
            <span class="material-symbols-outlined text-sm text-primary">lightbulb</span>
            How to Improve
          </h4>
          <ul class="space-y-2">
            <li v-for="tip in howToImprove" :key="tip" class="flex items-start gap-2 text-sm">
              <span class="material-symbols-outlined text-xs text-primary mt-0.5">check_circle</span>
              {{ tip }}
            </li>
          </ul>
        </div>
      </div>
      
      <!-- Footer -->
      <div class="p-4 border-t border-outline-variant/10 flex justify-end">
        <button @click="$emit('close')" class="px-4 py-2 bg-surface-container-highest rounded-lg font-bold text-sm">
          Close
        </button>
      </div>
    </div>
  </div>
</template>
```

### 1.3 Add Click Handler to Skill Bars

In PerformanceView, make skill bars clickable:

```vue
<div v-for="skill in category.skills" :key="skill.id" 
     class="space-y-1 cursor-pointer hover:bg-surface-container-lowest rounded p-1 -m-1"
     @click="openSkillBreakdown(skill)">
  <!-- existing skill bar content -->
</div>

<SkillBreakdownDialog 
  v-if="selectedSkill"
  :skill-id="selectedSkill.id"
  :user-id="selectedUserId"
  :project-id="projectsStore.selectedProjectId"
  @close="selectedSkill = null"
/>
```

---

## Task 2: Fix Review Velocity Stat

Review Velocity should measure average time to fix issues, not just weeks tracked.

### 2.1 Update Backend

**File:** `backend/src/services/performance.ts`

```typescript
// Add to calculatePerformance():

// Calculate review velocity (average days from finding to fix)
const fixedFindings = await prisma.finding.findMany({
  where: {
    review: { projectId },
    commitAuthor: user.username,
    fixedAt: { not: null }
  },
  select: {
    createdAt: true,
    fixedAt: true
  }
});

let reviewVelocity = null;
if (fixedFindings.length > 0) {
  const totalDays = fixedFindings.reduce((sum, f) => {
    const days = (f.fixedAt.getTime() - f.createdAt.getTime()) / (1000 * 60 * 60 * 24);
    return sum + days;
  }, 0);
  reviewVelocity = (totalDays / fixedFindings.length).toFixed(1);
}

// Return reviewVelocity in response
```

### 2.2 Add fixedAt Field to Prisma Schema

**File:** `prisma/schema.prisma`

```prisma
model Finding {
  // ... existing fields
  fixedAt     DateTime?  // When the finding was marked as fixed
}
```

### 2.3 Update Frontend

Show actual velocity or "No fixes yet":

```vue
<div class="bg-surface-container-low p-6 rounded-xl border-l-4 border-outline">
  <p class="text-outline text-xs font-bold uppercase tracking-wider mb-2">Review Velocity</p>
  <div class="flex items-end justify-between">
    <h3 class="text-3xl font-black">
      {{ performance.reviewVelocity ? performance.reviewVelocity + 'd' : '—' }}
    </h3>
    <span class="text-outline text-xs font-bold">
      {{ performance.reviewVelocity ? 'avg/fix' : 'No fixes yet' }}
    </span>
  </div>
</div>
```

---

## Task 3: Make Fix Rate Work

Fix Rate depends on tracking when findings are fixed. Add a "Mark as Fixed" action.

### 3.1 Add Endpoint to Mark Finding as Fixed

**File:** `backend/src/routes/findings.ts`

```typescript
// PATCH /api/findings/:id/fixed
router.patch('/:id/fixed', async (req, res) => {
  const { id } = req.params;
  
  await prisma.finding.update({
    where: { id: Number(id) },
    data: { 
      fixedAt: new Date(),
      prCreated: true  // Legacy field
    }
  });
  
  res.json({ success: true });
});
```

### 3.2 Add "Mark Fixed" Button in Finding Detail

**File:** `frontend/src/views/FindingDetailView.vue`

Add a button next to "Mark as Understood":

```vue
<button 
  v-if="!finding.fixedAt"
  @click="markAsFixed"
  class="px-4 py-2 bg-primary text-on-primary rounded-lg font-bold">
  <span class="material-symbols-outlined mr-1">check</span>
  Mark as Fixed
</button>
<span v-else class="text-primary flex items-center">
  <span class="material-symbols-outlined mr-1">verified</span>
  Fixed on {{ formatDate(finding.fixedAt) }}
</span>
```

---

## Task 4: Add Improvement Tips per Skill

**File:** `backend/src/services/skillMapping.ts`

```typescript
export const IMPROVEMENT_TIPS: Record<string, string[]> = {
  'clean_code': [
    'Use descriptive variable and function names',
    'Keep functions small and focused (single responsibility)',
    'Remove commented-out code',
    'Use consistent formatting and indentation'
  ],
  'secrets_management': [
    'Move hardcoded URLs to environment variables',
    'Never commit API keys or passwords',
    'Use .env files with .env.example templates',
    'Consider using a secrets manager for production'
  ],
  'html_semantics': [
    'Use semantic elements (<header>, <nav>, <main>, <article>)',
    'Always include <!DOCTYPE html> and <html lang="">',
    'Use proper heading hierarchy (h1 → h2 → h3)',
    'Add meta tags for SEO and viewport'
  ],
  // ... add for all 32 skills
};
```

---

## Files to Create/Modify

### Backend:
- `src/routes/skills.ts` — Add breakdown endpoint
- `src/routes/findings.ts` — Add mark-fixed endpoint  
- `src/services/performance.ts` — Calculate real review velocity
- `src/services/skillMapping.ts` — Add improvement tips
- `prisma/schema.prisma` — Add fixedAt field

### Frontend:
- `src/components/skills/SkillBreakdownDialog.vue` — New component
- `src/views/PerformanceView.vue` — Add click handlers, fix velocity display
- `src/views/FindingDetailView.vue` — Add mark-fixed button
- `src/composables/useApi.ts` — Add new endpoints

---

## Migration

```bash
npx prisma migrate dev --name add_fixed_at
```

---

Commit: feat: skill breakdown dialog + fix rate and velocity tracking
