import { PrismaClient, PeriodType } from '@prisma/client';

const prisma = new PrismaClient();

export async function calculateMetrics(
  userId: number,
  projectId: number,
  periodType: PeriodType,
  periodStart: Date,
  periodEnd: Date,
) {
  const findings = await prisma.finding.findMany({
    where: {
      review: {
        projectId,
        reviewDate: { gte: periodStart, lte: periodEnd },
      },
      commitAuthor: {
        not: null,
      },
    },
    include: { review: true },
  });

  const findingsByCategory: Record<string, number> = {};
  const findingsByDifficulty: Record<string, number> = {};

  for (const finding of findings) {
    findingsByCategory[finding.category] = (findingsByCategory[finding.category] || 0) + 1;
    findingsByDifficulty[finding.difficulty] = (findingsByDifficulty[finding.difficulty] || 0) + 1;
  }

  return prisma.performanceMetric.upsert({
    where: {
      userId_projectId_periodType_periodStart: {
        userId,
        projectId,
        periodType,
        periodStart,
      },
    },
    update: {
      periodEnd,
      findingCount: findings.length,
      findingsByCategory,
      findingsByDifficulty,
      calculatedAt: new Date(),
    },
    create: {
      userId,
      projectId,
      periodType,
      periodStart,
      periodEnd,
      findingCount: findings.length,
      findingsByCategory,
      findingsByDifficulty,
    },
  });
}
