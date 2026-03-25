import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

interface DetectionRule {
  positive?: string[];
  negative?: string[];
}

const SKILL_DETECTION_RULES: Record<string, DetectionRule> = {
  // Code Quality
  clean_code: {
    positive: ['good naming', 'readable', 'well-organized'],
    negative: ['poor naming', 'unclear', 'confusing', 'mono-syllable'],
  },
  code_structure: {
    positive: ['well-structured', 'good organization'],
    negative: ['bad structure', 'disorganized', 'spaghetti'],
  },
  dry_principle: {
    negative: ['duplicate', 'copy-paste', 'repeated code', 'code duplication', 'duplicated'],
  },
  comments_docs: {
    positive: ['well-documented', 'good comments'],
    negative: ['missing docstring', 'no documentation', 'undocumented'],
  },

  // Design Patterns
  solid_principles: {
    negative: ['single responsibility', 'too many responsibilities', 'god class'],
  },
  mvc_patterns: {
    negative: ['mixed concerns', 'business logic in view', 'logic in template'],
  },
  reusability: {
    positive: ['reusable', 'shared component'],
    negative: ['not reusable', 'tightly coupled'],
  },
  abstraction: {
    negative: ['no abstraction', 'hardcoded', 'magic number'],
  },

  // Logic & Algorithms
  problem_decomposition: {
    negative: ['too complex', 'should be split', 'break down'],
  },
  data_structures: {
    negative: ['wrong data structure', 'inefficient lookup'],
  },
  algorithm_efficiency: {
    negative: ['inefficient', 'O(n^2)', 'nested loop', 'performance issue'],
  },
  edge_cases: {
    negative: ['edge case', 'corner case', 'missing case', 'null check'],
  },

  // Security
  input_validation: {
    negative: ['no validation', 'missing validation', 'unsanitized', 'injection'],
  },
  auth_practices: {
    negative: ['authentication', 'unauthorized', 'missing auth'],
  },
  secrets_management: {
    negative: ['hardcoded url', 'hardcoded credential', 'hardcoded password', 'hardcoded api key', 'env var', 'secret'],
  },
  xss_csrf_prevention: {
    negative: ['xss', 'csrf', 'cross-site', 'unsafe html'],
  },

  // Testing
  unit_testing: {
    negative: ['no unit tests', 'missing tests', 'test coverage', 'untested'],
  },
  test_coverage: {
    negative: ['low coverage', 'no coverage', 'missing test'],
  },
  test_quality: {
    negative: ['flaky test', 'brittle test', 'weak assertion'],
  },
  tdd: {
    positive: ['test-driven', 'tdd'],
    negative: ['test after', 'no test'],
  },

  // Frontend
  html_semantics: {
    negative: ['invalid html', 'missing html tag', 'broken html structure', 'missing meta', 'non-semantic'],
  },
  css_organization: {
    negative: ['inline style', 'css duplication', 'unused css'],
  },
  accessibility: {
    negative: ['missing alt', 'no aria', 'accessibility', 'screen reader', 'aria-label'],
  },
  responsive_design: {
    negative: ['not responsive', 'fixed width', 'mobile'],
  },

  // Backend
  api_design: {
    negative: ['rest', 'status code', 'api design', 'endpoint'],
  },
  database_queries: {
    negative: ['n+1', 'slow query', 'missing index', 'inefficient query'],
  },
  error_handling: {
    negative: ['no error handling', 'swallowed exception', 'missing try', 'unhandled'],
  },
  performance: {
    negative: ['slow', 'memory leak', 'performance', 'optimization'],
  },

  // DevOps
  git_practices: {
    negative: ['commit message', 'typo in commit', 'large commit'],
  },
  build_tools: {
    negative: ['build config', 'webpack', 'bundle size'],
  },
  ci_cd: {
    negative: ['pipeline', 'ci/cd', 'deployment'],
  },
  environment_config: {
    negative: ['env var', 'configuration', 'hardcoded config'],
  },
};

function scoreFromLevel(level: number): number {
  // level 0 = 0-24, 1 = 25-49, 2 = 50-74, 3 = 75-89, 4 = 90-100
  const bases = [0, 25, 50, 75, 90];
  return bases[level] || 0;
}

function levelFromScore(score: number): number {
  if (score >= 90) return 4;
  if (score >= 75) return 3;
  if (score >= 50) return 2;
  if (score >= 25) return 1;
  return 0;
}

export async function calculateSkillScores(userId: number, projectId: number) {
  // Get all findings for user in project
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { username: true },
  });
  if (!user) throw new Error('User not found');

  const findings = await prisma.finding.findMany({
    where: {
      review: { projectId },
      commitAuthor: user.username,
    },
    select: { explanation: true, category: true },
  });

  // Get all skills
  const skills = await prisma.skill.findMany({
    include: { category: true },
  });

  const results = [];

  for (const skill of skills) {
    const rules = SKILL_DETECTION_RULES[skill.name];
    if (!rules) {
      // No rules for this skill - default to high score (no issues found)
      const score = 85;
      const level = levelFromScore(score);
      const userSkill = await prisma.userSkill.upsert({
        where: { userId_skillId: { userId, skillId: skill.id } },
        update: { score, level },
        create: { userId, skillId: skill.id, score, level },
      });
      results.push(userSkill);
      continue;
    }

    let negativeHits = 0;
    let positiveHits = 0;

    for (const finding of findings) {
      const text = finding.explanation.toLowerCase();

      if (rules.negative) {
        for (const keyword of rules.negative) {
          if (text.includes(keyword.toLowerCase())) {
            negativeHits++;
          }
        }
      }

      if (rules.positive) {
        for (const keyword of rules.positive) {
          if (text.includes(keyword.toLowerCase())) {
            positiveHits++;
          }
        }
      }
    }

    // Start at 85, subtract 15 per negative hit, add 5 per positive hit
    let score = 85 - negativeHits * 15 + positiveHits * 5;
    score = Math.max(0, Math.min(100, score));
    const level = levelFromScore(score);

    const userSkill = await prisma.userSkill.upsert({
      where: { userId_skillId: { userId, skillId: skill.id } },
      update: { score, level },
      create: { userId, skillId: skill.id, score, level },
    });
    results.push(userSkill);
  }

  return results;
}

export async function getSkillBreakdown(userId: number, skillId: number, projectId: number) {
  const skill = await prisma.skill.findUnique({
    where: { id: skillId },
    include: {
      category: true,
      userSkills: { where: { userId } },
    },
  });
  if (!skill) throw new Error('Skill not found');

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { username: true },
  });
  if (!user) throw new Error('User not found');

  const userSkill = skill.userSkills[0];
  const score = userSkill?.score ?? 0;
  const level = userSkill?.level ?? 0;

  const rules = SKILL_DETECTION_RULES[skill.name];

  // Find all findings for user in project
  const findings = await prisma.finding.findMany({
    where: {
      review: { projectId },
      commitAuthor: user.username,
    },
    select: {
      id: true,
      explanation: true,
      filePath: true,
      createdAt: true,
      category: true,
    },
    orderBy: { createdAt: 'desc' },
  });

  // Build deductions array - which findings triggered which keyword matches
  const deductions: {
    findingId: number;
    explanation: string;
    impact: number;
    keyword: string;
    type: 'positive' | 'negative';
    filePath: string;
    date: string;
  }[] = [];

  if (rules) {
    for (const finding of findings) {
      const text = finding.explanation.toLowerCase();

      if (rules.negative) {
        for (const keyword of rules.negative) {
          if (text.includes(keyword.toLowerCase())) {
            deductions.push({
              findingId: finding.id,
              explanation: finding.explanation,
              impact: -15,
              keyword,
              type: 'negative',
              filePath: finding.filePath,
              date: finding.createdAt.toISOString(),
            });
          }
        }
      }

      if (rules.positive) {
        for (const keyword of rules.positive) {
          if (text.includes(keyword.toLowerCase())) {
            deductions.push({
              findingId: finding.id,
              explanation: finding.explanation,
              impact: +5,
              keyword,
              type: 'positive',
              filePath: finding.filePath,
              date: finding.createdAt.toISOString(),
            });
          }
        }
      }
    }
  }

  // Generate improvement tips based on score
  const tips: string[] = [];
  if (score < 50) {
    tips.push(`Focus on addressing ${skill.displayName.toLowerCase()} issues in your code reviews`);
    tips.push('Review the flagged findings below and apply fixes where possible');
  }
  if (score < 75) {
    tips.push(`Study best practices for ${skill.category.displayName.toLowerCase()}`);
  }
  if (deductions.some(d => d.type === 'negative')) {
    const topKeyword = deductions.filter(d => d.type === 'negative')[0]?.keyword;
    if (topKeyword) {
      tips.push(`Most common issue: "${topKeyword}" — pay extra attention to this pattern`);
    }
  }
  if (score >= 75) {
    tips.push('Great progress! Keep maintaining this quality level');
  }

  return {
    skill: {
      id: skill.id,
      name: skill.name,
      displayName: skill.displayName,
      description: skill.description,
      category: {
        id: skill.category.id,
        name: skill.category.name,
        displayName: skill.category.displayName,
        icon: skill.category.icon,
      },
    },
    score,
    level,
    baseScore: 85,
    deductions,
    tips,
  };
}

export async function getUserSkillsByCategory(userId: number) {
  const categories = await prisma.skillCategory.findMany({
    include: {
      skills: {
        include: {
          userSkills: {
            where: { userId },
          },
        },
      },
    },
    orderBy: { id: 'asc' },
  });

  return categories.map((cat) => ({
    id: cat.id,
    name: cat.name,
    displayName: cat.displayName,
    description: cat.description,
    icon: cat.icon,
    skills: cat.skills.map((skill) => {
      const userSkill = skill.userSkills[0];
      return {
        id: skill.id,
        displayName: skill.displayName,
        score: userSkill?.score ?? 0,
        level: userSkill?.level ?? 0,
      };
    }),
  }));
}
