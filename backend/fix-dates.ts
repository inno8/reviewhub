import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function fixDates() {
  // Get all reviews
  const reviews = await prisma.review.findMany();
  
  console.log('=== Fixing review dates ===');
  
  for (const review of reviews) {
    const oldDate = review.reviewDate;
    // Extract just the date part and recreate as UTC midnight
    const dateStr = oldDate.toISOString().slice(0, 10);
    const newDate = new Date(`${dateStr}T00:00:00.000Z`);
    
    // Check if they differ (timezone offset was applied)
    if (oldDate.getTime() !== newDate.getTime()) {
      // Actually the issue is the other way - dates stored as T23:00 should be next day
      // E.g., 2026-03-24T23:00:00.000Z was meant to be 2026-03-25 local time
      const localDate = new Date(oldDate.getTime());
      const localDateStr = localDate.toLocaleDateString('sv-SE'); // YYYY-MM-DD format
      const correctedDate = new Date(`${localDateStr}T00:00:00.000Z`);
      
      console.log(`Review ${review.id}: ${oldDate.toISOString()} -> would be ${correctedDate.toISOString()}`);
    }
  }
  
  await prisma.$disconnect();
}

fixDates();
