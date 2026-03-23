import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database...');

  // Create admin user
  const adminPassword = await bcrypt.hash('admin123', 12);
  const admin = await prisma.user.upsert({
    where: { email: 'admin@reviewhub.dev' },
    update: {},
    create: {
      username: 'admin',
      email: 'admin@reviewhub.dev',
      passwordHash: adminPassword,
      role: 'ADMIN',
    },
  });

  // Create intern users
  const internPassword = await bcrypt.hash('intern123', 12);
  const intern1 = await prisma.user.upsert({
    where: { email: 'alice@reviewhub.dev' },
    update: {},
    create: {
      username: 'alice',
      email: 'alice@reviewhub.dev',
      passwordHash: internPassword,
      role: 'INTERN',
    },
  });

  const intern2 = await prisma.user.upsert({
    where: { email: 'bob@reviewhub.dev' },
    update: {},
    create: {
      username: 'bob',
      email: 'bob@reviewhub.dev',
      passwordHash: internPassword,
      role: 'INTERN',
    },
  });

  // Create project
  const project = await prisma.project.upsert({
    where: { name: 'reviewhub' },
    update: {},
    create: {
      name: 'reviewhub',
      displayName: 'ReviewHub',
      githubOwner: 'inno8',
      githubRepo: 'reviewhub',
    },
  });

  // Assign users to project
  for (const user of [admin, intern1, intern2]) {
    await prisma.userProject.upsert({
      where: { userId_projectId: { userId: user.id, projectId: project.id } },
      update: {},
      create: { userId: user.id, projectId: project.id },
    });
  }

  // Create a review with findings
  const review = await prisma.review.upsert({
    where: {
      projectId_branch_reviewDate: {
        projectId: project.id,
        branch: 'main',
        reviewDate: new Date('2026-03-23'),
      },
    },
    update: {},
    create: {
      projectId: project.id,
      branch: 'main',
      reviewDate: new Date('2026-03-23'),
      rawMarkdown: '# Code Review - March 23, 2026\n\nAutomated review findings for the main branch.',
    },
  });

  // Create findings
  await prisma.finding.createMany({
    skipDuplicates: true,
    data: [
      {
        reviewId: review.id,
        commitSha: 'abc1234',
        commitAuthor: 'alice',
        filePath: 'src/api/auth.ts',
        lineStart: 15,
        lineEnd: 22,
        originalCode: `app.post('/login', (req, res) => {\n  const user = db.query(\`SELECT * FROM users WHERE email = '\${req.body.email}'\`);\n  if (user && req.body.password === user.password) {\n    res.json({ token: createToken(user) });\n  }\n});`,
        optimizedCode: `app.post('/login', async (req, res) => {\n  const { email, password } = loginSchema.parse(req.body);\n  const user = await db.user.findUnique({ where: { email } });\n  if (!user || !await bcrypt.compare(password, user.passwordHash)) {\n    return res.status(401).json({ error: 'Invalid credentials' });\n  }\n  res.json({ token: createToken(user) });\n});`,
        explanation:
          'This code has two critical security issues: **SQL injection** via string interpolation in the query, and **plaintext password comparison**. The fix uses parameterized queries (via Prisma ORM), bcrypt for password hashing, and input validation with Zod schema.',
        references: JSON.stringify([
          { type: 'docs', title: 'OWASP SQL Injection Prevention', url: 'https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html' },
          { type: 'docs', title: 'bcrypt.js Documentation', url: 'https://github.com/dcodeIO/bcrypt.js' },
        ]),
        category: 'SECURITY',
        difficulty: 'BEGINNER',
      },
      {
        reviewId: review.id,
        commitSha: 'def5678',
        commitAuthor: 'bob',
        filePath: 'src/utils/data.ts',
        lineStart: 8,
        lineEnd: 15,
        originalCode: `function getUsers() {\n  const users = db.getAllUsers();\n  const result = [];\n  for (let i = 0; i < users.length; i++) {\n    result.push({ ...users[i], fullName: users[i].first + ' ' + users[i].last });\n  }\n  return result;\n}`,
        optimizedCode: `function getUsers() {\n  return db.getAllUsers().map(user => ({\n    ...user,\n    fullName: \`\${user.first} \${user.last}\`,\n  }));\n}`,
        explanation:
          'The original code uses an imperative loop with manual array building. Using `Array.map()` is more idiomatic, concise, and clearly expresses the intent of transforming each element. Template literals are preferred over string concatenation.',
        references: JSON.stringify([
          { type: 'docs', title: 'MDN Array.prototype.map()', url: 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/map' },
        ]),
        category: 'CODE_STYLE',
        difficulty: 'BEGINNER',
      },
      {
        reviewId: review.id,
        commitSha: 'ghi9012',
        commitAuthor: 'alice',
        filePath: 'src/services/cache.ts',
        lineStart: 1,
        lineEnd: 20,
        originalCode: `const cache: any = {};\n\nfunction getData(key: string) {\n  if (cache[key]) return cache[key];\n  const data = fetchFromDB(key);\n  cache[key] = data;\n  return data;\n}`,
        optimizedCode: `const cache = new Map<string, { data: unknown; expiry: number }>();\nconst TTL = 5 * 60 * 1000; // 5 minutes\n\nfunction getData(key: string): unknown {\n  const cached = cache.get(key);\n  if (cached && cached.expiry > Date.now()) return cached.data;\n  const data = fetchFromDB(key);\n  cache.set(key, { data, expiry: Date.now() + TTL });\n  return data;\n}`,
        explanation:
          'The original cache has no expiry mechanism (stale data risk), uses `any` type (loses type safety), and plain objects as maps (prototype pollution risk). Using `Map` with TTL-based expiry is safer, typed, and prevents unbounded memory growth.',
        references: JSON.stringify([
          { type: 'article', title: 'Caching Strategies in Node.js', url: 'https://blog.logrocket.com/caching-strategies-node-js/' },
        ]),
        category: 'PERFORMANCE',
        difficulty: 'INTERMEDIATE',
      },
    ],
  });

  console.log('Seed data created:');
  console.log(`  - Users: admin (admin@reviewhub.dev / admin123), alice, bob (intern123)`);
  console.log(`  - Project: ${project.displayName}`);
  console.log(`  - Review with 3 findings`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
