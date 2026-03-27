# ReviewHub: Parse Skills from @code-review Markdown

## Context
@code-review now includes **Skills Affected** in each finding. We need to:
1. Parse the skills from markdown
2. Store them with findings
3. Use them directly instead of keyword matching

## Task 1: Update Prisma Schema

**File:** `backend/prisma/schema.prisma`

Add skills field to Finding:

```prisma
model Finding {
  // ... existing fields
  skills      String[]   // Array of skill names like ['secrets_management', 'clean_code']
}
```

Run migration: `npx prisma migrate dev --name add_finding_skills`

## Task 2: Update Markdown Parser

**File:** `backend/src/services/markdownImport.ts`

Parse the **Skills Affected:** line:

```typescript
interface ParsedFinding {
  // ... existing
  skills: string[];  // Add this
}

// In parseMarkdownReview():
// Look for: **Skills Affected:** skill1, skill2
const skillsMatch = body.match(/\*\*Skills Affected:\*\*\s*([^\n]+)/);
const skills = skillsMatch 
  ? skillsMatch[1].split(',').map(s => s.trim().toLowerCase().replace(/\s+/g, '_'))
  : [];

findings.push({
  // ... existing
  skills,
});
```

Update the import function to save skills:

```typescript
await prisma.finding.create({
  data: {
    // ... existing fields
    skills: f.skills,  // Add this
  },
});
```

## Task 3: Update Skill Scoring

**File:** `backend/src/services/skillMapping.ts`

Update `calculateSkillScores()` to use the `finding.skills` array directly instead of keyword matching:

```typescript
export async function calculateSkillScores(userId: number, projectId: number) {
  const findings = await prisma.finding.findMany({
    where: {
      review: { projectId },
      commitAuthor: username
    },
    select: {
      id: true,
      skills: true,  // Use the parsed skills
      explanation: true,
      filePath: true,
      review: { select: { reviewDate: true } }
    }
  });

  // Count findings per skill directly
  const skillCounts: Record<string, number> = {};
  for (const finding of findings) {
    for (const skill of finding.skills) {
      skillCounts[skill] = (skillCounts[skill] || 0) + 1;
    }
  }

  // Calculate scores (100 - 5 per finding)
  const skills = await prisma.skill.findMany();
  for (const skill of skills) {
    const count = skillCounts[skill.name] || 0;
    const score = Math.max(0, 100 - (count * 5));
    
    await prisma.userSkill.upsert({
      where: { userId_skillId: { userId, skillId: skill.id } },
      update: { score, updatedAt: new Date() },
      create: { userId, skillId: skill.id, score }
    });
  }
}
```

## Task 4: Update Skill Breakdown

**File:** `backend/src/routes/skills.ts`

In the breakdown endpoint, return findings that have this skill in their `skills` array:

```typescript
const findings = await prisma.finding.findMany({
  where: {
    review: { projectId },
    commitAuthor: username,
    skills: { has: skill.name }  // Prisma array contains
  },
  select: {
    id: true,
    explanation: true,
    filePath: true,
    review: { select: { reviewDate: true } }
  }
});
```

## Task 5: Backfill Existing Findings (Optional)

For existing findings without skills, run the keyword matcher as a fallback:

```typescript
async function backfillSkills() {
  const findings = await prisma.finding.findMany({
    where: { skills: { isEmpty: true } }
  });
  
  for (const finding of findings) {
    const skills = detectSkillsFromExplanation(finding.explanation);
    await prisma.finding.update({
      where: { id: finding.id },
      data: { skills }
    });
  }
}
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `schema.prisma` | Add `skills String[]` to Finding |
| `markdownImport.ts` | Parse **Skills Affected:** line |
| `skillMapping.ts` | Use `finding.skills` instead of keyword matching |
| `routes/skills.ts` | Query by `skills: { has: skillName }` |

## Migration

```bash
npx prisma migrate dev --name add_finding_skills
```

---

Commit: feat: parse skills directly from @code-review findings
