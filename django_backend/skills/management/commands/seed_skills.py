"""
Seed skill categories and skills.
"""
from django.core.management.base import BaseCommand
from skills.models import SkillCategory, Skill


SKILL_DATA = {
    "code_quality": {
        "name": "Code Quality",
        "icon": "✨",
        "color": "#10b981",
        "skills": [
            {"slug": "clean_code", "name": "Clean Code", "description": "Naming, formatting, simplicity"},
            {"slug": "code_structure", "name": "Code Structure", "description": "Organization, modularity"},
            {"slug": "dry_principle", "name": "DRY Principle", "description": "Avoiding repetition"},
            {"slug": "comments_docs", "name": "Comments & Docs", "description": "Inline docs, docstrings"},
            # ── Crebo 25604 (MBO-4 Software Developer) aligned skills ──
            # These slugs mirror the criterion IDs in
            # grading.rubric_defaults.CREBO_RUBRIC_CRITERIA so
            # grading.services.skill_binding can look them up 1:1.
            {"slug": "code_ontwerp", "name": "Code-ontwerp", "description": "Crebo B1-K1-W2 — Ontwerpt software"},
            {"slug": "code_kwaliteit", "name": "Code-kwaliteit", "description": "Crebo B1-K1-W3 — Realiseert software"},
            {"slug": "verbetering", "name": "Verbetering", "description": "Crebo B1-K1-W5 — Doet verbetervoorstellen"},
        ]
    },
    "design_patterns": {
        "name": "Design Patterns",
        "icon": "🏗️",
        "color": "#8b5cf6",
        "skills": [
            {"slug": "solid_principles", "name": "SOLID Principles", "description": "S.O.L.I.D. adherence"},
            {"slug": "mvc_patterns", "name": "MVC Patterns", "description": "Separation of concerns"},
            {"slug": "reusability", "name": "Reusability", "description": "Component/function reuse"},
            {"slug": "abstraction", "name": "Abstraction", "description": "Proper interfaces, layers"},
        ]
    },
    "logic_algorithms": {
        "name": "Logic & Algorithms",
        "icon": "🧠",
        "color": "#f59e0b",
        "skills": [
            {"slug": "problem_decomposition", "name": "Problem Decomposition", "description": "Breaking down problems"},
            {"slug": "data_structures", "name": "Data Structures", "description": "Appropriate structure choices"},
            {"slug": "algorithm_efficiency", "name": "Algorithm Efficiency", "description": "Time/space complexity"},
            {"slug": "edge_cases", "name": "Edge Cases", "description": "Boundary condition handling"},
        ]
    },
    "security": {
        "name": "Security",
        "icon": "🔒",
        "color": "#ef4444",
        "skills": [
            {"slug": "input_validation", "name": "Input Validation", "description": "Sanitization, validation"},
            {"slug": "auth_practices", "name": "Auth Practices", "description": "Authentication, authorization"},
            {"slug": "secrets_management", "name": "Secrets Management", "description": "API keys, credentials"},
            {"slug": "xss_csrf_prevention", "name": "XSS/CSRF Prevention", "description": "Web security"},
            # Crebo alias — grading.rubric_defaults criterion id "veiligheid"
            {"slug": "veiligheid", "name": "Veiligheid", "description": "Crebo B1-K1-W3 (sub) — Veiligheid"},
        ]
    },
    "testing": {
        "name": "Testing",
        "icon": "🧪",
        "color": "#06b6d4",
        "skills": [
            {"slug": "unit_testing", "name": "Unit Testing", "description": "Test writing quality"},
            {"slug": "test_coverage", "name": "Test Coverage", "description": "Code coverage"},
            {"slug": "test_quality", "name": "Test Quality", "description": "Meaningful assertions"},
            {"slug": "tdd", "name": "TDD", "description": "Test-first approach"},
            # Crebo alias — grading.rubric_defaults criterion id "testen"
            {"slug": "testen", "name": "Testen", "description": "Crebo B1-K1-W4 — Test software"},
        ]
    },
    "collaboration": {
        "name": "Collaboration",
        "icon": "🤝",
        "color": "#14b8a6",
        "skills": [
            # Crebo criterion id "samenwerking" — B1-K2-W1+W3
            {"slug": "samenwerking", "name": "Samenwerking", "description": "Crebo B1-K2-W1+W3 — Voert overleg & reflecteert"},
        ]
    },
    "frontend": {
        "name": "Frontend",
        "icon": "🎨",
        "color": "#ec4899",
        "skills": [
            {"slug": "html_semantics", "name": "HTML Semantics", "description": "Semantic markup"},
            {"slug": "css_organization", "name": "CSS Organization", "description": "Styling best practices"},
            {"slug": "accessibility", "name": "Accessibility", "description": "A11y compliance"},
            {"slug": "responsive_design", "name": "Responsive Design", "description": "Mobile-first, breakpoints"},
        ]
    },
    "backend": {
        "name": "Backend",
        "icon": "⚙️",
        "color": "#3b82f6",
        "skills": [
            {"slug": "api_design", "name": "API Design", "description": "REST/GraphQL best practices"},
            {"slug": "database_queries", "name": "Database Queries", "description": "Efficient queries, N+1"},
            {"slug": "error_handling", "name": "Error Handling", "description": "Graceful errors, logging"},
            {"slug": "performance", "name": "Performance", "description": "Optimization, caching"},
        ]
    },
    "devops": {
        "name": "DevOps",
        "icon": "🚀",
        "color": "#6366f1",
        "skills": [
            {"slug": "git_practices", "name": "Git Practices", "description": "Commits, branching"},
            {"slug": "build_tools", "name": "Build Tools", "description": "Bundlers, compilers"},
            {"slug": "ci_cd", "name": "CI/CD", "description": "Pipelines, automation"},
            {"slug": "environment_config", "name": "Environment Config", "description": "Env vars, configs"},
        ]
    },
}


class Command(BaseCommand):
    help = 'Seed skill categories and skills'

    def handle(self, *args, **options):
        self.stdout.write('Seeding skills...')
        
        order = 0
        for cat_slug, cat_data in SKILL_DATA.items():
            order += 1
            
            category, created = SkillCategory.objects.update_or_create(
                slug=cat_slug,
                defaults={
                    'name': cat_data['name'],
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'order': order,
                }
            )
            
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} category: {category.name}')
            
            skill_order = 0
            for skill_data in cat_data['skills']:
                skill_order += 1
                
                skill, created = Skill.objects.update_or_create(
                    slug=skill_data['slug'],
                    defaults={
                        'category': category,
                        'name': skill_data['name'],
                        'description': skill_data['description'],
                        'order': skill_order,
                    }
                )
                
                action = 'Created' if created else 'Updated'
                self.stdout.write(f'    {action} skill: {skill.name}')
        
        # ── Rubric-criterion Skills ──────────────────────────────────────
        # The PR-level rubric grades against 8 category-level criteria
        # (security, code_quality, etc. — see grading.services.skill_binding).
        # bind_rubric_to_observations does Skill.objects.get(slug=criterion_id)
        # — without these 8 rows, every PR draft binds 0 observations and
        # the teacher's "Eindniveau" / "Per criterium" widgets stay empty.
        # These are intentionally separate from the per-commit Skill granularity
        # above (clean_code, input_validation, etc.) — they're aggregates that
        # match the rubric's eight categories one-to-one.
        rubric_criterion_skills = [
            ('security',       'Beveiliging',      'security'),
            ('code_quality',   'Code Kwaliteit',   'code_quality'),
            ('architecture',   'Architectuur',     'design_patterns'),
            ('testing',        'Testen',           'testing'),
            ('performance',    'Performance',      'backend'),
            ('documentation',  'Documentatie',     'code_quality'),
            ('validation',     'Validatie',        'security'),
            ('best_practices', 'Best Practices',   'code_quality'),
        ]
        for slug, name, cat_slug in rubric_criterion_skills:
            category = SkillCategory.objects.filter(slug=cat_slug).first()
            if not category:
                self.stdout.write(self.style.WARNING(
                    f'  rubric skill {slug}: category {cat_slug!r} not found, skipping'
                ))
                continue
            skill, created = Skill.objects.update_or_create(
                slug=slug,
                defaults={
                    'category': category,
                    'name': name,
                    'description': f'Rubric criterium: {name}',
                    'order': 100,  # sort after per-commit skills in the radar
                },
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(f'  {action} rubric skill: {skill.slug} → {category.name}')

        total_categories = SkillCategory.objects.count()
        total_skills = Skill.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {total_categories} categories, {total_skills} skills.'
        ))
