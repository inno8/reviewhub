import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function check() {
  // Check reviews
  const reviews = await prisma.review.findMany({
    include: { _count: { select: { findings: true } } },
    orderBy: { reviewDate: 'desc' },
    take: 10
  });
  console.log('=== REVIEWS ===');
  reviews.forEach(r => {
    console.log(r.reviewDate.toISOString().slice(0,10), r.branch, 'findings:', r._count.findings);
  });

  // Check findings
  const findings = await prisma.finding.findMany({
    take: 5,
    orderBy: { id: 'desc' },
    select: { id: true, filePath: true, originalCode: true, category: true, explanation: true }
  });
  console.log('\n=== RECENT FINDINGS ===');
  findings.forEach(f => {
    console.log('ID:', f.id, '| File:', f.filePath);
    console.log('  Code:', f.originalCode?.slice(0,100));
    console.log('  Category:', f.category);
  });

  await prisma.$disconnect();
}

check();
