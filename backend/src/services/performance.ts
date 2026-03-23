import { Category, PeriodType, PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

type PeriodInput = 'DAILY' | 'WEEKLY' | 'MONTHLY';
type RecommendationType = 'book' | 'article' | 'tutorial' | 'video';

export interface Recommendation {
  type: RecommendationType;
  title: string;
  url: string;
  category: string;
  reason: string;
}

export interface PerformanceData {
  userId: number;
  projectId: number;
  periodType: PeriodInput;
  periodStart: Date;
  periodEnd: Date;
  commitCount: number;
  findingCount: number;
  findingsByCategory: Record<string, number>;
  findingsByDifficulty: Record<string, number>;
  strengths: string[];
  growthAreas: string[];
  recommendations: Recommendation[];
  fixRate: number;
}

export interface CodeProgression {
  weekStart: Date;
  weekEnd: Date;
  findingCount: number;
  categories: Record<string, number>;
  trend: 'improving' | 'stable' | 'declining';
}

const ALL_CATEGORIES: string[] = Object.values(Category);

const RECOMMENDATIONS: Record<string, Recommendation[]> = {
  SECURITY: [
    {
      type: 'book',
      title: 'Web Security for Developers',
      url: 'https://www.amazon.com/dp/1593279949',
      category: 'SECURITY',
      reason: 'Covers common vulnerabilities and prevention',
    },
    {
      type: 'article',
      title: 'OWASP Top 10',
      url: 'https://owasp.org/Top10/',
      category: 'SECURITY',
      reason: 'Essential security knowledge',
    },
  ],
  PERFORMANCE: [
    {
      type: 'book',
      title: 'High Performance JavaScript',
      url: 'https://www.amazon.com/dp/059680279X',
      category: 'PERFORMANCE',
      reason: 'Deep dive into JS performance',
    },
    {
      type: 'article',
      title: 'Web.dev Performance Guide',
      url: 'https://web.dev/performance/',
      category: 'PERFORMANCE',
      reason: 'Modern performance best practices',
    },
  ],
  CODE_STYLE: [
    {
      type: 'book',
      title: 'Clean Code',
      url: 'https://www.amazon.com/dp/0132350882',
      category: 'CODE_STYLE',
      reason: 'Industry standard for code quality',
    },
    {
      type: 'article',
      title: 'Google Style Guides',
      url: 'https://google.github.io/styleguide/',
      category: 'CODE_STYLE',
      reason: 'Professional style guidelines',
    },
  ],
  TESTING: [
    {
      type: 'book',
      title: 'Testing JavaScript Applications',
      url: 'https://www.amazon.com/dp/1617297917',
      category: 'TESTING',
      reason: 'Comprehensive testing guide',
    },
    {
      type: 'tutorial',
      title: 'Jest Documentation',
      url: 'https://jestjs.io/docs/getting-started',
      category: 'TESTING',
      reason: 'Learn the most popular testing framework',
    },
  ],
  ARCHITECTURE: [
    {
      type: 'book',
      title: 'Clean Architecture',
      url: 'https://www.amazon.com/dp/0134494164',
      category: 'ARCHITECTURE',
      reason: 'Fundamental architecture principles',
    },
    {
      type: 'article',
      title: 'Patterns.dev',
      url: 'https://www.patterns.dev/',
      category: 'ARCHITECTURE',
      reason: 'Modern design patterns',
    },
  ],
  DOCUMENTATION: [
    {
      type: 'article',
      title: 'Write the Docs Guide',
      url: 'https://www.writethedocs.org/guide/',
      category: 'DOCUMENTATION',
      reason: 'Documentation best practices',
    },
  ],
};

function getPeriodRange(periodType: PeriodInput): { periodStart: Date; periodEnd: Date } {
  const now = new Date();
  const periodEnd = now;
  const periodStart = new Date(now);

  if (periodType === 'DAILY') {
    periodStart.setDate(now.getDate() - 1);
  } else if (periodType === 'WEEKLY') {
    periodStart.setDate(now.getDate() - 7);
  } else {
    periodStart.setMonth(now.getMonth() - 1);
  }

  return { periodStart, periodEnd };
}

function emptyCategoryCount(): Record<string, number> {
  return ALL_CATEGORIES.reduce<Record<string, number>>((acc, category) => {
    acc[category] = 0;
    return acc;
  }, {});
}

function parsePeriodType(periodType: PeriodInput): PeriodType {
  return periodType as PeriodType;
}

export async function calculatePerformance(
  userId: number,
  projectId: number,
  periodType: PeriodInput,
): Promise<PerformanceData> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { username: true },
  });

  if (!user) {
    throw new Error('User not found');
  }

  const { periodStart, periodEnd } = getPeriodRange(periodType);
  const findings = await prisma.finding.findMany({
    where: {
      review: {
        projectId,
        reviewDate: { gte: periodStart, lte: periodEnd },
      },
      commitAuthor: user.username,
    },
    select: {
      category: true,
      difficulty: true,
      commitSha: true,
      prCreated: true,
    },
  });

  const findingsByCategory = emptyCategoryCount();
  const findingsByDifficulty: Record<string, number> = {};

  for (const finding of findings) {
    findingsByCategory[finding.category] = (findingsByCategory[finding.category] || 0) + 1;
    findingsByDifficulty[finding.difficulty] = (findingsByDifficulty[finding.difficulty] || 0) + 1;
  }

  const strengths = ALL_CATEGORIES.filter((category) => (findingsByCategory[category] || 0) <= 1);
  const growthAreas = ALL_CATEGORIES.filter((category) => (findingsByCategory[category] || 0) >= 3);
  const recommendations = growthAreas.flatMap((category) => RECOMMENDATIONS[category] || []);

  const commitCount = new Set(findings.map((finding) => finding.commitSha).filter(Boolean)).size;
  const findingCount = findings.length;
  const fixedCount = findings.filter((finding) => finding.prCreated).length;
  const fixRate = findingCount ? Math.round((fixedCount / findingCount) * 100) : 0;

  await prisma.performanceMetric.upsert({
    where: {
      userId_projectId_periodType_periodStart: {
        userId,
        projectId,
        periodType: parsePeriodType(periodType),
        periodStart,
      },
    },
    update: {
      periodEnd,
      commitCount,
      findingCount,
      findingsByCategory: JSON.stringify(findingsByCategory),
      findingsByDifficulty: JSON.stringify(findingsByDifficulty),
      strengths: JSON.stringify(strengths),
      growthAreas: JSON.stringify(growthAreas),
      recommendations: JSON.stringify(recommendations),
      calculatedAt: new Date(),
    },
    create: {
      userId,
      projectId,
      periodType: parsePeriodType(periodType),
      periodStart,
      periodEnd,
      commitCount,
      findingCount,
      findingsByCategory: JSON.stringify(findingsByCategory),
      findingsByDifficulty: JSON.stringify(findingsByDifficulty),
      strengths: JSON.stringify(strengths),
      growthAreas: JSON.stringify(growthAreas),
      recommendations: JSON.stringify(recommendations),
    },
  });

  return {
    userId,
    projectId,
    periodType,
    periodStart,
    periodEnd,
    commitCount,
    findingCount,
    findingsByCategory,
    findingsByDifficulty,
    strengths,
    growthAreas,
    recommendations,
    fixRate,
  };
}

export async function getCodeProgression(
  userId: number,
  projectId: number,
  weeks = 8,
): Promise<CodeProgression[]> {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { username: true },
  });

  if (!user) {
    throw new Error('User not found');
  }

  const now = new Date();
  const progression: CodeProgression[] = [];
  let previousCount: number | null = null;

  for (let index = weeks - 1; index >= 0; index -= 1) {
    const weekEnd = new Date(now);
    weekEnd.setHours(23, 59, 59, 999);
    weekEnd.setDate(now.getDate() - index * 7);

    const weekStart = new Date(weekEnd);
    weekStart.setHours(0, 0, 0, 0);
    weekStart.setDate(weekEnd.getDate() - 6);

    const findings = await prisma.finding.findMany({
      where: {
        review: {
          projectId,
          reviewDate: { gte: weekStart, lte: weekEnd },
        },
        commitAuthor: user.username,
      },
      select: { category: true },
    });

    const categories = emptyCategoryCount();
    for (const finding of findings) {
      categories[finding.category] = (categories[finding.category] || 0) + 1;
    }

    const findingCount = findings.length;
    let trend: 'improving' | 'stable' | 'declining' = 'stable';
    if (previousCount !== null) {
      if (findingCount < previousCount) {
        trend = 'improving';
      } else if (findingCount > previousCount) {
        trend = 'declining';
      }
    }

    progression.push({
      weekStart,
      weekEnd,
      findingCount,
      categories,
      trend,
    });

    previousCount = findingCount;
  }

  return progression;
}
