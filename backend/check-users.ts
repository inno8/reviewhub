import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function check() {
  console.log('=== Users ===');
  const users = await prisma.user.findMany({
    select: { id: true, email: true, name: true, role: true }
  });
  console.log(users);
  
  console.log('\n=== Projects ===');
  const projects = await prisma.project.findMany({
    select: { id: true, name: true, displayName: true }
  });
  console.log(projects);
  
  await prisma.$disconnect();
}

check();
