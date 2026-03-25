import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function check() {
  const users = await prisma.user.findMany();
  console.log('Users:', users.length);
  users.forEach(u => console.log(`  ${u.id}: ${u.email}`));
  
  const projects = await prisma.project.findMany();
  console.log('\nProjects:', projects.length);
  projects.forEach(p => console.log(`  ${p.id}: ${p.name}`));
  
  await prisma.$disconnect();
}

check();
