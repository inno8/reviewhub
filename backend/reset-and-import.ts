import { PrismaClient } from '@prisma/client';
import { syncAllMarkdownReviews } from './src/services/markdownImport';

const prisma = new PrismaClient();

async function reset() {
  console.log('=== Deleting all findings and reviews ===');
  await prisma.userFinding.deleteMany({});
  await prisma.finding.deleteMany({});
  await prisma.review.deleteMany({});
  
  console.log('=== Re-importing all markdown files ===');
  const result = await syncAllMarkdownReviews(1);
  console.log('Result:', result);
  
  console.log('\n=== Checking imported dates ===');
  const reviews = await prisma.review.findMany({
    orderBy: { reviewDate: 'desc' },
    select: { id: true, reviewDate: true, branch: true, _count: { select: { findings: true } } }
  });
  reviews.forEach(r => {
    console.log(`${r.reviewDate.toISOString().slice(0,10)} | ${r.branch} | ${r._count.findings} findings`);
  });
  
  await prisma.$disconnect();
}

reset();
