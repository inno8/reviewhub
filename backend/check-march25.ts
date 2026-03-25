import { PrismaClient } from '@prisma/client';
import { parseMarkdownReview } from './src/services/markdownImport';
import * as fs from 'fs';

const prisma = new PrismaClient();

async function check() {
  // Check all reviews with dates
  const reviews = await prisma.review.findMany({
    select: { id: true, reviewDate: true, branch: true, rawMarkdown: true },
    orderBy: { reviewDate: 'desc' }
  });
  
  console.log('=== All reviews in DB ===');
  reviews.forEach(r => {
    console.log(`ID ${r.id}: ${r.reviewDate.toISOString()} | ${r.branch} | rawMarkdown: ${r.rawMarkdown ? 'yes' : 'no'}`);
  });
  
  // Check March 25 specifically
  console.log('\n=== Looking for March 25 ===');
  const march25 = await prisma.review.findMany({
    where: {
      reviewDate: {
        gte: new Date('2026-03-25'),
        lt: new Date('2026-03-26')
      }
    }
  });
  console.log('Found', march25.length, 'reviews for March 25');
  
  // Parse the markdown file
  console.log('\n=== Parsing 2026-03-25.md ===');
  const content = fs.readFileSync('C:/Users/yanic/.openclaw/workspace/projects/amanks-market/reviews/2026-03-25.md', 'utf-8');
  const findings = parseMarkdownReview(content);
  console.log('Parsed', findings.length, 'findings');
  if (findings.length > 0) {
    console.log('First finding:', findings[0]);
  }
  
  await prisma.$disconnect();
}

check();
