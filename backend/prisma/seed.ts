import { PrismaClient, Category, Difficulty } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  console.log('Seeding database...');

  // Create admin user (Yanick)
  const adminPassword = await bcrypt.hash('admin123', 12);
  const admin = await prisma.user.upsert({
    where: { email: 'yanick@itec.nl' },
    update: {},
    create: {
      username: 'yanick',
      email: 'yanick@itec.nl',
      passwordHash: adminPassword,
      role: 'ADMIN',
    },
  });

  // Create intern users (Amanks Market team)
  const internPassword = await bcrypt.hash('intern123', 12);
  const dollarDonut = await prisma.user.upsert({
    where: { email: 'benlassinadiaby@gmail.com' },
    update: {},
    create: {
      username: 'DollarDonut',
      email: 'benlassinadiaby@gmail.com',
      passwordHash: internPassword,
      role: 'INTERN',
    },
  });

  const reikdv = await prisma.user.upsert({
    where: { email: '37676@ma-web.nl' },
    update: {},
    create: {
      username: 'Reikdv',
      email: '37676@ma-web.nl',
      passwordHash: internPassword,
      role: 'INTERN',
    },
  });

  // Create Amanks Market project
  const project = await prisma.project.upsert({
    where: { name: 'amanks-market' },
    update: {},
    create: {
      name: 'amanks-market',
      displayName: 'Amanks Market',
      githubOwner: 'inno8',
      githubRepo: 'amanks-market',
    },
  });

  // Assign users to project
  for (const user of [admin, dollarDonut, reikdv]) {
    await prisma.userProject.upsert({
      where: { userId_projectId: { userId: user.id, projectId: project.id } },
      update: {},
      create: { userId: user.id, projectId: project.id },
    });
  }

  // Review 1: feature/issue-32-Home-page-template (DollarDonut)
  const review1 = await prisma.review.upsert({
    where: {
      projectId_branch_reviewDate: {
        projectId: project.id,
        branch: 'feature/issue-32-Home-page-template',
        reviewDate: new Date('2026-03-23'),
      },
    },
    update: {},
    create: {
      projectId: project.id,
      branch: 'feature/issue-32-Home-page-template',
      reviewDate: new Date('2026-03-23'),
      rawMarkdown: '# Code Review - March 23, 2026\n\nAutomated review for issue-32 branch.',
    },
  });

  // Review 2: feature/issue35-about-page-template-clean (Reikdv)
  const review2 = await prisma.review.upsert({
    where: {
      projectId_branch_reviewDate: {
        projectId: project.id,
        branch: 'feature/issue35-about-page-template-clean',
        reviewDate: new Date('2026-03-23'),
      },
    },
    update: {},
    create: {
      projectId: project.id,
      branch: 'feature/issue35-about-page-template-clean',
      reviewDate: new Date('2026-03-23'),
      rawMarkdown: '# Code Review - March 23, 2026\n\nAutomated review for issue-35 branch.',
    },
  });

  // Findings for DollarDonut's branch
  const findingsDollar = [
    {
      reviewId: review1.id,
      commitSha: '683e0e7',
      commitAuthor: 'DollarDonut',
      filePath: 'templates/home.html',
      lineStart: 83,
      lineEnd: 130,
      originalCode: `<!-- Weekly Flash Deals Section -->
<article class="max-w-7xl mx-auto px-4 py-8">
  <h2 class="text-2xl font-bold mb-6">Weekly Flash Deals</h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
      <img src="{% static 'images/flash-deal1.jpg' %}" alt="Flash Deal 1">
      <div class="p-4">
        <h3 class="font-semibold">Special Offer</h3>
        <p class="text-green-700 font-bold">€9.99</p>
      </div>
    </div>
    <!-- ... more deals ... -->
  </div>
</article>

<!-- DUPLICATE: Same section appears again below -->
<article class="max-w-7xl mx-auto px-4 py-8">
  <h2 class="text-2xl font-bold mb-6">Weekly Flash Deals</h2>
  <!-- ... identical content ... -->
</article>`,
      optimizedCode: `<!-- Weekly Flash Deals Section - Only once! -->
<article class="max-w-7xl mx-auto px-4 py-8">
  <h2 class="text-2xl font-bold mb-6">Weekly Flash Deals</h2>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    {% for deal in flash_deals %}
    <div class="bg-white rounded-lg shadow-md overflow-hidden">
      <img src="{{ deal.image.url }}" alt="{{ deal.title }}">
      <div class="p-4">
        <h3 class="font-semibold">{{ deal.title }}</h3>
        <p class="text-green-700 font-bold">€{{ deal.price }}</p>
      </div>
    </div>
    {% endfor %}
  </div>
</article>`,
      explanation: 'The "Weekly Flash Deals" section appears TWICE in home.html. This is likely copy-paste that wasn\'t cleaned up. Remove the duplicate block and convert to a Django loop that renders deals from the backend dynamically.',
      references: JSON.stringify([
        { type: 'docs', title: 'Django Template Tags', url: 'https://docs.djangoproject.com/en/5.0/ref/templates/builtins/#for' },
      ]),
      category: Category.CODE_STYLE,
      difficulty: Difficulty.BEGINNER,
    },
    {
      reviewId: review1.id,
      commitSha: '683e0e7',
      commitAuthor: 'DollarDonut',
      filePath: 'templates/home.html',
      lineStart: 10,
      lineEnd: 45,
      originalCode: `<!-- Navigation in home.html -->
<header class="bg-green-700 sticky top-0 z-30">
  <nav class="max-w-7xl mx-auto px-4">
    <input type="checkbox" id="menu-toggle" class="peer hidden" />
    <label for="menu-toggle" class="md:hidden cursor-pointer">
      <svg class="w-6 h-6 text-white"><!-- hamburger icon --></svg>
    </label>
    <ul class="hidden peer-checked:block md:flex">
      <li><a href="/">Home</a></li>
      <li><a href="/producten/">Producten</a></li>
      <li><a href="/contact/">Contact</a></li>
    </ul>
  </nav>
</header>

<!-- Same code duplicated in categories.html and contact.html -->`,
      optimizedCode: `<!-- templates/partials/_navbar.html -->
<header class="bg-green-700 sticky top-0 z-30">
  <nav class="max-w-7xl mx-auto px-4">
    <input type="checkbox" id="menu-toggle" class="peer hidden"
           aria-label="Toggle navigation menu" />
    <label for="menu-toggle" class="md:hidden cursor-pointer"
           aria-expanded="false" aria-controls="mobile-menu">
      <svg class="w-6 h-6 text-white"><!-- hamburger icon --></svg>
    </label>
    <ul id="mobile-menu" class="hidden peer-checked:block md:flex">
      <li><a href="{% url 'home' %}">Home</a></li>
      <li><a href="{% url 'products' %}">Producten</a></li>
      <li><a href="{% url 'contact' %}">Contact</a></li>
    </ul>
  </nav>
</header>

<!-- In all pages: -->
{% include 'partials/_navbar.html' %}`,
      explanation: 'The hamburger navigation code is duplicated across home.html, categories.html, and contact.html. If you need to change the navigation, you\'ll have to update it in 3+ places. Extract to a Django partial template for maintainability. Also added accessibility attributes for screen readers.',
      references: JSON.stringify([
        { type: 'docs', title: 'Django include tag', url: 'https://docs.djangoproject.com/en/5.0/ref/templates/builtins/#include' },
        { type: 'docs', title: 'ARIA Authoring Practices', url: 'https://www.w3.org/WAI/ARIA/apg/patterns/menu/' },
      ]),
      category: Category.ARCHITECTURE,
      difficulty: Difficulty.INTERMEDIATE,
    },
    {
      reviewId: review1.id,
      commitSha: '683e0e7',
      commitAuthor: 'DollarDonut',
      filePath: 'templates/home.html',
      lineStart: 15,
      lineEnd: 18,
      originalCode: `<input type="checkbox" id="menu-toggle" class="peer hidden" />
<label for="menu-toggle" class="md:hidden cursor-pointer">
  <svg class="w-6 h-6 text-white"><!-- hamburger icon --></svg>
</label>`,
      optimizedCode: `<input type="checkbox" id="menu-toggle" class="peer hidden"
       aria-label="Toggle navigation menu"
       role="button" />
<label for="menu-toggle" 
       class="md:hidden cursor-pointer"
       aria-expanded="false" 
       aria-controls="mobile-menu">
  <svg class="w-6 h-6 text-white" aria-hidden="true">
    <!-- hamburger icon -->
  </svg>
  <span class="sr-only">Open menu</span>
</label>`,
      explanation: 'Screen readers can\'t tell users what this checkbox does. Missing aria-label, aria-expanded, and aria-controls attributes. The SVG icon should be aria-hidden with a sr-only text fallback for accessibility.',
      references: JSON.stringify([
        { type: 'docs', title: 'WCAG 2.1 - Name, Role, Value', url: 'https://www.w3.org/WAI/WCAG21/Understanding/name-role-value.html' },
      ]),
      category: Category.SECURITY,
      difficulty: Difficulty.BEGINNER,
    },
  ];

  // Findings for Reikdv's branch
  const findingsReik = [
    {
      reviewId: review2.id,
      commitSha: '97b59c2',
      commitAuthor: 'Reikdv',
      filePath: 'templates/about.html',
      lineStart: 20,
      lineEnd: 50,
      originalCode: `<section class="py-12">
  <div class="max-w-4xl mx-auto">
    <h2 class="text-3xl font-bold mb-6">Over Ons</h2>
    <p class="text-gray-600 mb-4">
      Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
      Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
    </p>
    <p class="text-gray-600 mb-4">
      Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris 
      nisi ut aliquip ex ea commodo consequat.
    </p>
    <p class="text-gray-600">
      Duis aute irure dolor in reprehenderit in voluptate velit esse 
      cillum dolore eu fugiat nulla pariatur.
    </p>
  </div>
</section>`,
      optimizedCode: `<section class="py-12">
  <div class="max-w-4xl mx-auto">
    <h2 class="text-3xl font-bold mb-6">Over Ons</h2>
    <p class="text-gray-600 mb-4">
      AmanksMarket is jouw online bestemming voor authentieke Afrikaanse 
      producten in Nederland. Wij brengen de smaken van Afrika naar jouw deur.
    </p>
    <p class="text-gray-600 mb-4">
      Opgericht in 2024, werken wij samen met lokale Afrikaanse winkels om 
      de beste producten tegen eerlijke prijzen aan te bieden.
    </p>
    <p class="text-gray-600">
      Onze missie is om de Afrikaanse diaspora in Nederland te verbinden 
      met de producten die zij kennen en liefhebben.
    </p>
  </div>
</section>`,
      explanation: 'The entire About page is filled with "Lorem ipsum dolor sit amet..." placeholder text. If this gets merged and deployed, users see meaningless Latin text. Replace with actual brand content before merging to main.',
      references: JSON.stringify([]),
      category: Category.CODE_STYLE,
      difficulty: Difficulty.BEGINNER,
    },
    {
      reviewId: review2.id,
      commitSha: '97b59c2',
      commitAuthor: 'Reikdv',
      filePath: 'terms-and-conditions/apps.py',
      lineStart: 1,
      lineEnd: 3,
      originalCode: `from django.apps import AppConfig

# (empty - no AppConfig class)`,
      optimizedCode: `from django.apps import AppConfig


class TermsAndConditionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'terms_and_conditions'
    verbose_name = 'Terms and Conditions'`,
      explanation: 'Django expects an AppConfig class for the app to work properly. The apps.py file is empty which will cause import errors. Also note: the folder uses hyphens (terms-and-conditions) but Python module names must use underscores (terms_and_conditions).',
      references: JSON.stringify([
        { type: 'docs', title: 'Django Applications', url: 'https://docs.djangoproject.com/en/5.0/ref/applications/' },
      ]),
      category: Category.ARCHITECTURE,
      difficulty: Difficulty.INTERMEDIATE,
    },
    {
      reviewId: review2.id,
      commitSha: '97b59c2',
      commitAuthor: 'Reikdv',
      filePath: 'templates/about.html',
      lineStart: 5,
      lineEnd: 10,
      originalCode: `<img src="https://picsum.photos/seed/ghana/1200/500" 
     class="w-full h-64 object-cover"
     alt="Ghana landscape">
<img src="https://images.unsplash.com/photo-1523805009345-7448845a9e53" 
     class="w-full h-64 object-cover"
     alt="African market">`,
      optimizedCode: `<img src="{% static 'images/about/hero-ghana.jpg' %}" 
     class="w-full h-64 object-cover"
     alt="Ghana landscape"
     loading="lazy">
<img src="{% static 'images/about/african-market.jpg' %}" 
     class="w-full h-64 object-cover"
     alt="African market"
     loading="lazy">`,
      explanation: 'External image dependencies (picsum.photos, unsplash.com) mean: 1) Pages won\'t load if these services are down, 2) No control over image content, 3) GDPR considerations with external image loading (leaks user IP). Download and self-host key images with lazy loading.',
      references: JSON.stringify([
        { type: 'article', title: 'GDPR and Third-Party Resources', url: 'https://gdpr.eu/third-party-cookies/' },
      ]),
      category: Category.SECURITY,
      difficulty: Difficulty.INTERMEDIATE,
    },
    {
      reviewId: review2.id,
      commitSha: '97b59c2',
      commitAuthor: 'Reikdv',
      filePath: 'terms-and-conditions/templates/terms.html',
      lineStart: 1,
      lineEnd: 10,
      originalCode: `<!DOCTYPE html>
<html lang="nl">
<head>
    <title>Terms and Conditions</title>
</head>
<body>
    
</body>
</html>`,
      optimizedCode: `{% extends 'base.html' %}
{% block title %}Algemene Voorwaarden - AmanksMarket{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto py-12 px-4">
  <h1 class="text-3xl font-bold mb-8">Algemene Voorwaarden</h1>
  
  <section class="mb-8">
    <h2 class="text-xl font-semibold mb-4">1. Algemeen</h2>
    <p class="text-gray-600">
      Deze voorwaarden zijn van toepassing op alle bestellingen 
      bij AmanksMarket...
    </p>
  </section>
  
  <!-- Add more sections -->
</div>
{% endblock %}`,
      explanation: 'The terms.html template is completely empty. If someone navigates to /terms/, they see a blank page. Add actual terms content, extend the base template for consistent styling, and use Dutch language to match the rest of the site.',
      references: JSON.stringify([]),
      category: Category.CODE_STYLE,
      difficulty: Difficulty.BEGINNER,
    },
  ];

  // Create all findings
  for (const finding of [...findingsDollar, ...findingsReik]) {
    await prisma.finding.create({ data: finding });
  }

  // Seed skill categories and skills
  const skillCategories = [
    {
      name: 'code_quality',
      displayName: 'Code Quality',
      description: 'Writing clean, maintainable, and readable code',
      icon: 'code',
      skills: [
        { name: 'clean_code', displayName: 'Clean Code', description: 'Readable, well-organized code with clear naming' },
        { name: 'code_structure', displayName: 'Code Structure', description: 'Proper organization of files, classes, and functions' },
        { name: 'dry_principle', displayName: 'DRY Principle', description: "Don't Repeat Yourself - avoiding code duplication" },
        { name: 'comments_docs', displayName: 'Comments & Documentation', description: 'Clear comments and documentation' },
      ],
    },
    {
      name: 'design_patterns',
      displayName: 'Design Patterns',
      description: 'Applying proven software design solutions',
      icon: 'architecture',
      skills: [
        { name: 'solid_principles', displayName: 'SOLID Principles', description: 'Single Responsibility, Open/Closed, etc.' },
        { name: 'mvc_patterns', displayName: 'MVC/MVP/MVVM', description: 'Model-View-Controller and related patterns' },
        { name: 'reusability', displayName: 'Reusability', description: 'Creating reusable components and functions' },
        { name: 'abstraction', displayName: 'Abstraction', description: 'Proper use of interfaces and abstract classes' },
      ],
    },
    {
      name: 'logic_algorithms',
      displayName: 'Logic & Algorithms',
      description: 'Problem solving and algorithmic thinking',
      icon: 'psychology',
      skills: [
        { name: 'problem_decomposition', displayName: 'Problem Decomposition', description: 'Breaking down complex problems into smaller parts' },
        { name: 'data_structures', displayName: 'Data Structures', description: 'Choosing appropriate data structures' },
        { name: 'algorithm_efficiency', displayName: 'Algorithm Efficiency', description: 'Writing efficient algorithms (Big O awareness)' },
        { name: 'edge_cases', displayName: 'Edge Case Handling', description: 'Anticipating and handling edge cases' },
      ],
    },
    {
      name: 'security',
      displayName: 'Security',
      description: 'Writing secure code and avoiding vulnerabilities',
      icon: 'security',
      skills: [
        { name: 'input_validation', displayName: 'Input Validation', description: 'Validating and sanitizing user input' },
        { name: 'auth_practices', displayName: 'Authentication Practices', description: 'Proper auth implementation' },
        { name: 'secrets_management', displayName: 'Secrets Management', description: 'Not hardcoding credentials, using env vars' },
        { name: 'xss_csrf_prevention', displayName: 'XSS/CSRF Prevention', description: 'Preventing common web vulnerabilities' },
      ],
    },
    {
      name: 'testing',
      displayName: 'Testing',
      description: 'Writing tests and ensuring code quality',
      icon: 'bug_report',
      skills: [
        { name: 'unit_testing', displayName: 'Unit Testing', description: 'Writing unit tests for functions/methods' },
        { name: 'test_coverage', displayName: 'Test Coverage', description: 'Adequate test coverage of code' },
        { name: 'test_quality', displayName: 'Test Quality', description: 'Meaningful tests that catch real bugs' },
        { name: 'tdd', displayName: 'TDD', description: 'Test-Driven Development practices' },
      ],
    },
    {
      name: 'frontend',
      displayName: 'Frontend',
      description: 'UI/UX and frontend-specific skills',
      icon: 'web',
      skills: [
        { name: 'html_semantics', displayName: 'HTML Semantics', description: 'Using semantic HTML elements properly' },
        { name: 'css_organization', displayName: 'CSS Organization', description: 'Clean, maintainable CSS/Tailwind' },
        { name: 'accessibility', displayName: 'Accessibility', description: 'ARIA labels, keyboard navigation, etc.' },
        { name: 'responsive_design', displayName: 'Responsive Design', description: 'Mobile-first, responsive layouts' },
      ],
    },
    {
      name: 'backend',
      displayName: 'Backend',
      description: 'Server-side and API skills',
      icon: 'dns',
      skills: [
        { name: 'api_design', displayName: 'API Design', description: 'RESTful design, proper status codes' },
        { name: 'database_queries', displayName: 'Database Queries', description: 'Efficient and safe database queries' },
        { name: 'error_handling', displayName: 'Error Handling', description: 'Proper error handling and logging' },
        { name: 'performance', displayName: 'Performance', description: 'Optimizing backend performance' },
      ],
    },
    {
      name: 'devops',
      displayName: 'DevOps & Tools',
      description: 'Version control, CI/CD, and tooling',
      icon: 'settings',
      skills: [
        { name: 'git_practices', displayName: 'Git Practices', description: 'Proper commits, branching, PRs' },
        { name: 'build_tools', displayName: 'Build Tools', description: 'Understanding of build systems' },
        { name: 'ci_cd', displayName: 'CI/CD', description: 'Continuous integration/deployment awareness' },
        { name: 'environment_config', displayName: 'Environment Config', description: 'Proper use of env vars and config' },
      ],
    },
  ];

  let skillCount = 0;
  for (const cat of skillCategories) {
    const category = await prisma.skillCategory.upsert({
      where: { name: cat.name },
      update: { displayName: cat.displayName, description: cat.description, icon: cat.icon },
      create: { name: cat.name, displayName: cat.displayName, description: cat.description, icon: cat.icon },
    });

    for (const skill of cat.skills) {
      await prisma.skill.upsert({
        where: { name: skill.name },
        update: { displayName: skill.displayName, description: skill.description, categoryId: category.id },
        create: {
          name: skill.name,
          displayName: skill.displayName,
          description: skill.description,
          categoryId: category.id,
        },
      });
      skillCount++;
    }
  }

  console.log('Seed data created:');
  console.log('  - Users: yanick (yanick@itec.nl / admin123)');
  console.log('  - Interns: DollarDonut, Reikdv (intern123)');
  console.log(`  - Project: ${project.displayName}`);
  console.log(`  - Review 1: ${review1.branch} with 3 findings`);
  console.log(`  - Review 2: ${review2.branch} with 4 findings`);
  console.log(`  - Skill categories: ${skillCategories.length}, Skills: ${skillCount}`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
