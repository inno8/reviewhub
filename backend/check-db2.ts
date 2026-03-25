import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function check() {
  const reviews = await prisma.review.findMany({
    orderBy: { reviewDate: 'desc' },
    take: 10,
    select: { id: true, reviewDate: true, branch: true, rawMarkdown: true, _count: { select: { findings: true } } }
  });
  
  console.log('=== ALL REVIEWS ===');
  reviews.forEach(r => {
    const hasMd = r.rawMarkdown ? '✓ imported' : '';
    console.log(`${r.reviewDate.toISOString().slice(0,10)} | ${r.branch} | ${r._count.findings} findings | ${hasMd}`);
  });
  
  await prisma.$disconnect();
}

check();
