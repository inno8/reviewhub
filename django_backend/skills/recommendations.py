"""
Learning Recommendations View
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from datetime import timedelta

from django.utils import timezone

from .models import SkillMetric


# v1.1 task E3 (May 2 2026): map every skill_slug back to a Crebo werkproces
# so recommendations can display the docent-recognisable kerntaak code.
#
# Two layers:
#   1. Direct match for the 6 rubric-criterion slugs (these ARE Crebo
#      werkprocessen by definition — see grading/rubric_defaults.py).
#   2. Fallback by SkillCategory.name for the per-commit slugs (clean_code,
#      input_validation, html_semantics, etc) so we always surface SOMETHING.
#
# Crebo 25604 (MBO-4 ICT-developer) kerntaakcodes:
#   B1-K1-W2  Ontwerpt software
#   B1-K1-W3  Realiseert software           (also covers Veiligheid sub)
#   B1-K1-W4  Test software
#   B1-K1-W5  Doet verbetervoorstellen
#   B1-K2-W1  Voert overleg                 (combined with W3)
#   B1-K2-W3  Reflecteert op werk
CREBO_BY_SKILL_SLUG = {
    # Direct rubric-criterion mappings (6 Crebo werkprocessen = 6 slugs).
    'code_ontwerp':   ('B1-K1-W2', 'Ontwerpt software'),
    'code_kwaliteit': ('B1-K1-W3', 'Realiseert software'),
    'veiligheid':     ('B1-K1-W3', 'Realiseert software (veiligheid)'),
    'testen':         ('B1-K1-W4', 'Test software'),
    'verbetering':    ('B1-K1-W5', 'Doet verbetervoorstellen'),
    'samenwerking':   ('B1-K2-W1+W3', 'Voert overleg & reflecteert'),
}

# Fallback when a skill_slug isn't one of the 6 rubric criteria — map by
# SkillCategory.name. The 8 SkillCategory names come from
# skills/models.py:90 (Code Quality, Design Patterns, Logic & Algorithms,
# Security, Testing, Frontend, Backend, DevOps).
CREBO_BY_CATEGORY = {
    'Code Quality':         ('B1-K1-W3', 'Realiseert software'),
    'Design Patterns':      ('B1-K1-W2', 'Ontwerpt software'),
    'Logic & Algorithms':   ('B1-K1-W3', 'Realiseert software'),
    'Security':             ('B1-K1-W3', 'Realiseert software (veiligheid)'),
    'Testing':              ('B1-K1-W4', 'Test software'),
    'Frontend':             ('B1-K1-W3', 'Realiseert software'),
    'Backend':              ('B1-K1-W3', 'Realiseert software'),
    'DevOps':               ('B1-K1-W5', 'Doet verbetervoorstellen'),
}


def crebo_for(skill_slug, category_name=None):
    """Return (werkproces_code, werkproces_name) or (None, None) if no match."""
    if skill_slug in CREBO_BY_SKILL_SLUG:
        return CREBO_BY_SKILL_SLUG[skill_slug]
    if category_name and category_name in CREBO_BY_CATEGORY:
        return CREBO_BY_CATEGORY[category_name]
    return (None, None)


class LearningRecommendationsView(APIView):
    """
    Get personalized learning recommendations based on:
    - Skills with low scores
    - Recent findings by category
    - Skills that haven't improved recently
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from evaluations.models import Finding

        project_id = request.query_params.get('project')
        limit = int(request.query_params.get('limit', 5))

        # Get developer's primary language for targeted recommendations
        primary_language = None
        try:
            if hasattr(request.user, 'dev_profile') and request.user.dev_profile:
                primary_language = request.user.dev_profile.primary_language
        except Exception:
            pass

        # Get user's skill metrics
        metrics = SkillMetric.objects.filter(
            user=request.user
        ).select_related('skill', 'skill__category')

        if project_id:
            metrics = metrics.filter(project_id=project_id)
        
        recommendations = []
        
        # 1. Find skills with low scores (below 70)
        low_score_metrics = metrics.filter(score__lt=70).order_by('score')[:limit]
        
        for metric in low_score_metrics:
            priority = 'high' if metric.score < 50 else 'medium'
            
            recommendations.append({
                'skill': {
                    'id': metric.skill.id,
                    'name': metric.skill.name,
                    'slug': metric.skill.slug,
                    'category': metric.skill.category.name
                },
                'current_score': metric.score,
                'reason': f'Lage score op {metric.skill.name}',
                'priority': priority,
                'issue_count': metric.issue_count,
                'suggested_resources': self._get_resources_for_skill(metric.skill.slug, primary_language),
                'improvement_tip': self._get_improvement_tip(metric.skill.slug, metric.issue_count, primary_language)
            })

        # 2. Find skills with many recent issues (last 30 days)
        from evaluations.models import Evaluation

        thirty_days_ago = timezone.now() - timedelta(days=30)
        user_evals = Evaluation.objects.for_user(request.user)
        if project_id:
            user_evals = user_evals.filter(project_id=project_id)
        recent_findings = Finding.objects.filter(
            evaluation__in=user_evals,
            created_at__gte=thirty_days_ago,
            is_fixed=False,
        ).prefetch_related('skills')
        
        # Count issues by skill
        skill_issue_counts = {}
        for finding in recent_findings:
            for skill in finding.skills.all():
                if skill.id not in skill_issue_counts:
                    skill_issue_counts[skill.id] = {
                        'skill': skill,
                        'count': 0,
                        'severity_counts': {'critical': 0, 'warning': 0, 'info': 0, 'suggestion': 0}
                    }
                skill_issue_counts[skill.id]['count'] += 1
                sev = finding.severity.lower()
                if sev in skill_issue_counts[skill.id]['severity_counts']:
                    skill_issue_counts[skill.id]['severity_counts'][sev] += 1
        
        # Add recommendations for skills with many recent issues
        for skill_id, data in sorted(
            skill_issue_counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:3]:
            skill = data['skill']
            
            # Check if not already in recommendations
            if not any(r['skill']['id'] == skill.id for r in recommendations):
                priority = 'high' if data['severity_counts']['critical'] > 0 else 'medium'
                
                recommendations.append({
                    'skill': {
                        'id': skill.id,
                        'name': skill.name,
                        'slug': skill.slug,
                        'category': skill.category.name
                    },
                    'current_score': next(
                        (m.score for m in metrics if m.skill.id == skill.id),
                        0
                    ),
                    'reason': f'{data["count"]} recente bevindingen in {skill.name}',
                    'priority': priority,
                    'issue_count': data['count'],
                    'severity_breakdown': data['severity_counts'],
                    'suggested_resources': self._get_resources_for_skill(skill.slug, primary_language),
                    'improvement_tip': self._get_improvement_tip(skill.slug, data['count'], primary_language)
                })
        
        # 3. Skills with negative trends
        # NOTE: SkillMetric.trend choices are 'up'|'down'|'stable' (see migration 0001).
        # This filter previously used 'declining' which never matched, so layer 3
        # of the recommendation engine never fired. Fixed May 2 2026.
        declining_metrics = metrics.filter(trend='down').order_by('score')[:2]
        
        for metric in declining_metrics:
            # Check if not already in recommendations
            if not any(r['skill']['id'] == metric.skill.id for r in recommendations):
                recommendations.append({
                    'skill': {
                        'id': metric.skill.id,
                        'name': metric.skill.name,
                        'slug': metric.skill.slug,
                        'category': metric.skill.category.name
                    },
                    'current_score': metric.score,
                    'reason': f'Dalende trend voor {metric.skill.name}',
                    'priority': 'medium',
                    'issue_count': metric.issue_count,
                    'trend': metric.trend,
                    'suggested_resources': self._get_resources_for_skill(metric.skill.slug, primary_language),
                    'improvement_tip': self._get_improvement_tip(metric.skill.slug, metric.issue_count, primary_language)
                })
        
        # 4. Pattern-based recommendations (recurring issues)
        from evaluations.models import Pattern
        high_freq_patterns = Pattern.objects.filter(
            user=request.user,
            frequency__gte=3,
            is_resolved=False,
        ).order_by('-frequency')[:5]

        for pattern in high_freq_patterns:
            if not any(
                r.get('pattern_key') == pattern.pattern_key for r in recommendations
            ):
                recommendations.append({
                    'skill': {
                        'id': None,
                        'name': pattern.pattern_type,
                        'slug': pattern.pattern_key,
                        'category': pattern.pattern_type,
                    },
                    'current_score': None,
                    'reason': (
                        f'Terugkerend patroon: {pattern.frequency} keer '
                        f'{pattern.pattern_type}-issues'
                    ),
                    'priority': 'high' if pattern.frequency >= 10 else 'medium',
                    'issue_count': pattern.frequency,
                    'pattern_key': pattern.pattern_key,
                    'improvement_tip': (
                        f'Je hebt {pattern.frequency} terugkerende {pattern.pattern_type}-issues. '
                        f'Focus op dit gebied voor de grootste verbetering.'
                    ),
                    'suggested_resources': self._get_resources_for_skill(
                        pattern.pattern_key.split(':')[0], primary_language
                    ),
                })

        # 5. Add profile context (user level)
        user_level = 'intermediate'
        profile_weaknesses = []
        try:
            from batch.models import DeveloperProfile
            profile = DeveloperProfile.objects.get(user=request.user)
            user_level = profile.level
            profile_weaknesses = profile.weaknesses or []
        except Exception:
            pass

        for rec in recommendations:
            rec['user_level'] = user_level

        # 6. Recently mastered skills — skills that were weak but improved above 70
        mastered_metrics = metrics.filter(
            score__gte=70,
            previous_score__isnull=False,
            previous_score__lt=70,
        ).order_by('-score')[:3]

        for metric in mastered_metrics:
            existing_ids = {r['skill']['id'] for r in recommendations}
            if metric.skill.id not in existing_ids:
                recommendations.append({
                    'skill': {
                        'id': metric.skill.id,
                        'name': metric.skill.name,
                        'slug': metric.skill.slug,
                        'category': metric.skill.category.name,
                    },
                    'current_score': metric.score,
                    'reason': f'Mooie vooruitgang! {metric.skill.name} ging van {metric.previous_score:.0f} naar {metric.score:.0f}',
                    'priority': 'mastered',
                    'issue_count': metric.issue_count,
                    'suggested_resources': self._get_advanced_resources(metric.skill.slug, primary_language),
                    'improvement_tip': self._get_next_level_tip(metric.skill.slug, metric.score, primary_language),
                    'user_level': user_level,
                })

        # 7. Growth opportunities — high-scoring skills to take to the next level
        if len(recommendations) < limit:
            growth_metrics = (
                metrics
                .filter(score__gte=70, score__lt=90)
                .exclude(id__in=[m.id for m in mastered_metrics])
                .order_by('-score')[:3]
            )
            existing_ids = {r['skill']['id'] for r in recommendations}
            for metric in growth_metrics:
                if metric.skill.id not in existing_ids and len(recommendations) < limit:
                    recommendations.append({
                        'skill': {
                            'id': metric.skill.id,
                            'name': metric.skill.name,
                            'slug': metric.skill.slug,
                            'category': metric.skill.category.name,
                        },
                        'current_score': metric.score,
                        'reason': f'Sterk in {metric.skill.name} ({metric.score:.0f}/100) — push naar expert-niveau',
                        'priority': 'growth',
                        'issue_count': metric.issue_count,
                        'suggested_resources': self._get_advanced_resources(metric.skill.slug, primary_language),
                        'improvement_tip': self._get_next_level_tip(metric.skill.slug, metric.score, primary_language),
                        'user_level': user_level,
                    })

        # Sort by priority and limit
        priority_order = {'high': 0, 'medium': 1, 'low': 2, 'mastered': 3, 'growth': 4}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 5))

        # v1.1 task E3: tag every recommendation with the Crebo werkproces it
        # belongs to so the frontend can render a kerntaak-pill ("B1-K1-W3 ·
        # Realiseert software") next to the rec. Pattern recs without a real
        # SkillCategory get (None, None) and the pill is hidden.
        for rec in recommendations:
            skill = rec.get('skill') or {}
            code, name = crebo_for(skill.get('slug'), skill.get('category'))
            rec['werkproces_code'] = code
            rec['werkproces_name'] = name

        return Response(recommendations[:limit])
    
    # Language-specific documentation for each skill
    SKILL_DOCS = {
        'input_validation': {
            'python': [{'title': 'Python: Parameterized SQL Queries', 'type': 'documentation', 'url': 'https://docs.python.org/3/library/sqlite3.html#how-to-use-placeholders'}],
            'javascript': [{'title': 'MDN: Client-side Form Validation', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Learn/Forms/Form_validation'}],
            '_default': [{'title': 'OWASP: Input Validation Cheat Sheet', 'type': 'documentation', 'url': 'https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html'}],
        },
        'secrets_management': {
            'python': [{'title': 'Python: Environment Variables (os.environ)', 'type': 'documentation', 'url': 'https://docs.python.org/3/library/os.html#os.environ'}],
            '_default': [{'title': '12-Factor App: Config', 'type': 'article', 'url': 'https://12factor.net/config'}],
        },
        'clean_code': {
            'python': [{'title': 'PEP 8 — Python Style Guide', 'type': 'documentation', 'url': 'https://peps.python.org/pep-0008/'}],
            'javascript': [{'title': 'MDN: JavaScript Best Practices', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Learn/JavaScript/Howto'}],
            '_default': [{'title': 'Refactoring Guru: Code Smells', 'type': 'article', 'url': 'https://refactoring.guru/refactoring/smells'}],
        },
        'code_structure': {
            'python': [{'title': 'Python: Modules and Packages', 'type': 'documentation', 'url': 'https://docs.python.org/3/tutorial/modules.html'}],
            'javascript': [{'title': 'MDN: JavaScript Modules', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules'}],
            '_default': [{'title': 'Refactoring Guru: Extract Method', 'type': 'article', 'url': 'https://refactoring.guru/extract-method'}],
        },
        'dry_principle': {
            '_default': [{'title': 'Refactoring Guru: Extract Method Pattern', 'type': 'article', 'url': 'https://refactoring.guru/extract-method'}],
        },
        'error_handling': {
            'python': [{'title': 'Python: Errors and Exceptions', 'type': 'documentation', 'url': 'https://docs.python.org/3/tutorial/errors.html'}],
            'javascript': [{'title': 'MDN: Error Handling (try...catch)', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/try...catch'}],
        },
        'edge_cases': {
            '_default': [{'title': 'Defensive Programming Techniques', 'type': 'article', 'url': 'https://refactoring.guru/extract-method'}],
        },
        'html_semantics': {
            '_default': [{'title': 'MDN: HTML Semantic Elements', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Glossary/Semantics#semantics_in_html'}],
        },
        'accessibility': {
            '_default': [{'title': 'MDN: Accessibility Fundamentals', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Learn/Accessibility'}],
        },
        'css_organization': {
            '_default': [{'title': 'MDN: Organizing Your CSS', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Organizing'}],
        },
        'responsive_design': {
            '_default': [{'title': 'MDN: Responsive Design', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Learn/CSS/CSS_layout/Responsive_Design'}],
        },
        'xss_csrf_prevention': {
            '_default': [{'title': 'OWASP: XSS Prevention Cheat Sheet', 'type': 'documentation', 'url': 'https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html'}],
        },
        'database_queries': {
            'python': [{'title': 'Python: sqlite3 — Safe Query Patterns', 'type': 'documentation', 'url': 'https://docs.python.org/3/library/sqlite3.html#how-to-use-placeholders'}],
            '_default': [{'title': 'OWASP: SQL Injection Prevention', 'type': 'documentation', 'url': 'https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html'}],
        },
        'api_design': {
            'python': [{'title': 'Flask: Quickstart — Routing', 'type': 'documentation', 'url': 'https://flask.palletsprojects.com/en/latest/quickstart/#routing'}],
            '_default': [{'title': 'RESTful API Design Best Practices', 'type': 'article', 'url': 'https://restfulapi.net/resource-naming/'}],
        },
        'comments_docs': {
            'python': [{'title': 'PEP 257 — Docstring Conventions', 'type': 'documentation', 'url': 'https://peps.python.org/pep-0257/'}],
            'javascript': [{'title': 'JSDoc: Getting Started', 'type': 'documentation', 'url': 'https://jsdoc.app/about-getting-started'}],
        },
        'solid_principles': {
            '_default': [{'title': 'SOLID Principles Explained', 'type': 'article', 'url': 'https://refactoring.guru/solid'}],
        },
        # ──────────────────────────────────────────────────────────────────
        # v1.1 task E4 (May 2 2026): fill the ~22 hardcoded skill_slug gaps
        # below. Before this batch, recommendations for these slugs fell
        # through to a Google search URL — embarrassing for a docent demo
        # ("the AI just sends students to Google?"). Each slug now has at
        # least a _default authoritative resource; major slugs also have
        # python + javascript variants. Curated for Dutch MBO-4 ICT use.
        # ──────────────────────────────────────────────────────────────────

        # Logic & Algorithms category
        'abstraction': {
            '_default': [{'title': 'Refactoring Guru: Abstract Factory', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns/abstract-factory'}],
        },
        'algorithm_efficiency': {
            '_default': [{'title': 'Big-O Cheat Sheet', 'type': 'article', 'url': 'https://www.bigocheatsheet.com/'}],
            'python': [{'title': 'Python: TimeComplexity (CPython operations)', 'type': 'documentation', 'url': 'https://wiki.python.org/moin/TimeComplexity'}],
        },
        'data_structures': {
            'python': [{'title': 'Python: Data Structures', 'type': 'documentation', 'url': 'https://docs.python.org/3/tutorial/datastructures.html'}],
            'javascript': [{'title': 'MDN: JavaScript Data Structures', 'type': 'documentation', 'url': 'https://developer.mozilla.org/en-US/docs/Web/JavaScript/Data_structures'}],
            '_default': [{'title': 'Visualgo: Data Structure Visualizations', 'type': 'tutorial', 'url': 'https://visualgo.net/'}],
        },
        'problem_decomposition': {
            '_default': [{'title': 'Refactoring Guru: Extract Function', 'type': 'article', 'url': 'https://refactoring.guru/extract-method'}],
        },
        'performance': {
            'javascript': [{'title': 'Web.dev: Performance', 'type': 'documentation', 'url': 'https://web.dev/learn/performance/'}],
            'python': [{'title': 'Python: Profilers (cProfile)', 'type': 'documentation', 'url': 'https://docs.python.org/3/library/profile.html'}],
            '_default': [{'title': 'Use the Index, Luke! — SQL Performance', 'type': 'article', 'url': 'https://use-the-index-luke.com/'}],
        },

        # Security category
        'auth_practices': {
            '_default': [{'title': 'OWASP: Authentication Cheat Sheet', 'type': 'documentation', 'url': 'https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html'}],
            'javascript': [{'title': 'Auth0: Web Auth Best Practices', 'type': 'article', 'url': 'https://auth0.com/blog/web-application-security-101/'}],
        },

        # Testing category
        'tdd': {
            '_default': [{'title': 'Martin Fowler: Test Driven Development', 'type': 'article', 'url': 'https://martinfowler.com/bliki/TestDrivenDevelopment.html'}],
            'python': [{'title': 'pytest: Get Started', 'type': 'documentation', 'url': 'https://docs.pytest.org/en/stable/getting-started.html'}],
            'javascript': [{'title': 'Vitest: Getting Started', 'type': 'documentation', 'url': 'https://vitest.dev/guide/'}],
        },
        'unit_testing': {
            'python': [{'title': 'Python: unittest', 'type': 'documentation', 'url': 'https://docs.python.org/3/library/unittest.html'}],
            'javascript': [{'title': 'Vitest: Writing Tests', 'type': 'documentation', 'url': 'https://vitest.dev/guide/features.html'}],
            '_default': [{'title': 'Martin Fowler: UnitTest', 'type': 'article', 'url': 'https://martinfowler.com/bliki/UnitTest.html'}],
        },
        'test_coverage': {
            'python': [{'title': 'pytest-cov: Coverage Reporting', 'type': 'documentation', 'url': 'https://pytest-cov.readthedocs.io/en/latest/'}],
            'javascript': [{'title': 'Vitest: Coverage', 'type': 'documentation', 'url': 'https://vitest.dev/guide/coverage.html'}],
            '_default': [{'title': 'Martin Fowler: TestCoverage', 'type': 'article', 'url': 'https://martinfowler.com/bliki/TestCoverage.html'}],
        },
        'test_quality': {
            '_default': [{'title': 'Test Smells: Common Anti-Patterns', 'type': 'article', 'url': 'https://martinfowler.com/articles/practical-test-pyramid.html'}],
        },

        # DevOps / Backend
        'ci_cd': {
            '_default': [{'title': 'GitHub Actions: Quickstart', 'type': 'documentation', 'url': 'https://docs.github.com/en/actions/quickstart'}],
        },
        'git_practices': {
            '_default': [{'title': 'Atlassian: Gitflow Workflow', 'type': 'tutorial', 'url': 'https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow'}],
        },
        'environment_config': {
            'python': [{'title': 'python-dotenv: Loading .env', 'type': 'documentation', 'url': 'https://github.com/theskumar/python-dotenv#getting-started'}],
            '_default': [{'title': '12-Factor App: Config', 'type': 'article', 'url': 'https://12factor.net/config'}],
        },
        'build_tools': {
            'javascript': [{'title': 'Vite: Why Vite', 'type': 'documentation', 'url': 'https://vitejs.dev/guide/why.html'}],
            'python': [{'title': 'Python Packaging User Guide', 'type': 'documentation', 'url': 'https://packaging.python.org/en/latest/'}],
        },

        # Design Patterns
        'mvc_patterns': {
            '_default': [{'title': 'Refactoring Guru: MVC', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns/strategy'}],
        },
        'reusability': {
            '_default': [{'title': 'Refactoring Guru: Composition over Inheritance', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns/strategy'}],
        },

        # Crebo rubric criterion slugs — fall back to deeper-skill resources
        # so a "code_kwaliteit" rec gives the docent something concrete.
        'code_kwaliteit': {
            '_default': [
                {'title': 'Refactoring Guru: Code Smells', 'type': 'article', 'url': 'https://refactoring.guru/refactoring/smells'},
                {'title': 'Clean Code by Robert C. Martin (samenvatting)', 'type': 'article', 'url': 'https://gist.github.com/wojteklu/73c6914cc446146b8b533c0988cf8d29'},
            ],
        },
        'code_ontwerp': {
            '_default': [
                {'title': 'Refactoring Guru: SOLID Principles', 'type': 'article', 'url': 'https://refactoring.guru/solid'},
                {'title': 'Refactoring Guru: Design Patterns', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns'},
            ],
        },
        'veiligheid': {
            '_default': [
                {'title': 'OWASP Top 10', 'type': 'documentation', 'url': 'https://owasp.org/www-project-top-ten/'},
                {'title': 'OWASP Cheat Sheet Series', 'type': 'documentation', 'url': 'https://cheatsheetseries.owasp.org/'},
            ],
        },
        'testen': {
            '_default': [
                {'title': 'Martin Fowler: Practical Test Pyramid', 'type': 'article', 'url': 'https://martinfowler.com/articles/practical-test-pyramid.html'},
            ],
            'python': [{'title': 'pytest: Get Started', 'type': 'documentation', 'url': 'https://docs.pytest.org/en/stable/getting-started.html'}],
            'javascript': [{'title': 'Vitest: Getting Started', 'type': 'documentation', 'url': 'https://vitest.dev/guide/'}],
        },
        'verbetering': {
            '_default': [
                {'title': 'Refactoring Guru: Refactoring Catalog', 'type': 'article', 'url': 'https://refactoring.guru/refactoring/catalog'},
                {'title': 'Martin Fowler: Refactoring (book overview)', 'type': 'article', 'url': 'https://martinfowler.com/books/refactoring.html'},
            ],
        },
        'samenwerking': {
            '_default': [
                {'title': 'Atlassian: Code Review Best Practices', 'type': 'article', 'url': 'https://www.atlassian.com/agile/software-development/code-reviews'},
                {'title': 'Conventional Commits', 'type': 'documentation', 'url': 'https://www.conventionalcommits.org/en/v1.0.0/'},
            ],
        },
    }

    def _get_resources_for_skill(self, skill_slug, primary_language=None):
        """Get targeted, language-specific resources for a skill."""
        lang = (primary_language or '').lower()
        skill_docs = self.SKILL_DOCS.get(skill_slug, {})

        # Try language-specific first, then default
        resources = skill_docs.get(lang) or skill_docs.get('_default') or []
        if not resources:
            # Fallback: try to find any matching docs
            for key in skill_docs:
                if key != '_default':
                    resources = skill_docs[key]
                    break

        if not resources:
            # Final fallback: generic search but with better formatting
            readable = skill_slug.replace('_', ' ').title()
            resources = [{'title': f'{readable} Best Practices', 'type': 'article', 'url': f'https://www.google.com/search?q={skill_slug.replace("_", "+")}+best+practices+{lang or "programming"}'}]

        return resources

    def _get_improvement_tip(self, skill_slug, issue_count, primary_language=None):
        """Get a targeted improvement tip for a skill."""
        lang = (primary_language or '').lower()
        tips_map = {
            'clean_code': f'Je code heeft naamgevings- en opmaak-issues. Volg de {lang.upper() or "taal"}-stijlconventies consequent.',
            'code_structure': 'Splits grote functies op in kleine, gefocuste functies. Elke functie doet één ding goed.',
            'dry_principle': 'Zoek herhaalde patronen in je code. Extract gedeelde logica in herbruikbare functies.',
            'input_validation': 'Vertrouw nooit op gebruikersinvoer. Valideer en saneer altijd voordat je het gebruikt in queries of rendert.',
            'secrets_management': 'Verplaats alle geheimen (API-keys, wachtwoorden) naar environment variables. Commit ze nooit naar git.',
            'error_handling': 'Wrap riskante operaties in try/except blokken. Vang specifieke exceptions, geen bare except.',
            'edge_cases': 'Denk na over wat er gebeurt bij lege invoer, None-waarden of onverwachte types.',
            'html_semantics': 'Gebruik semantische HTML-tags (<header>, <nav>, <main>, <section>) in plaats van generieke <div>.',
            'accessibility': 'Voeg alt-tekst toe aan afbeeldingen, gebruik ARIA-labels op interactieve elementen, zorg voor toetsenbordnavigatie.',
            'css_organization': 'Vermijd inline styles. Gebruik CSS-classes en combineer gedeelde eigenschappen om duplicatie te verminderen.',
            'responsive_design': 'Gebruik relatieve units (rem, %) en media queries voor layouts die zich aanpassen aan schermformaat.',
            'xss_csrf_prevention': 'Gebruik nooit innerHTML met gebruikersdata. Gebruik textContent of een sanitization-library.',
            'database_queries': 'Gebruik parameterized queries met ? placeholders. Bouw SQL nooit op met string-concatenatie.',
            'comments_docs': 'Voeg docstrings toe aan functies die uitleggen wat ze doen, hun parameters en retourwaarden.',
        }

        base_tip = tips_map.get(skill_slug, f'Bekijk recente bevindingen en identificeer veelvoorkomende patronen in je {skill_slug.replace("_", " ")}-code.')

        if issue_count > 10:
            return f'{base_tip} Je hebt {issue_count} bevindingen — begin met de meest kritieke.'
        elif issue_count > 5:
            return f'{base_tip} Focus op het voorkomen van vergelijkbare issues in nieuwe code.'
        else:
            return base_tip

    ADVANCED_DOCS = {
        'clean_code': {
            'python': [{'title': 'Python: Advanced Design Patterns', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns/python'}],
            'javascript': [{'title': 'JavaScript: Clean Architecture', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns/typescript'}],
            '_default': [{'title': 'Refactoring Guru: Design Patterns', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns'}],
        },
        'code_structure': {
            '_default': [{'title': 'Refactoring Guru: SOLID Principles', 'type': 'article', 'url': 'https://refactoring.guru/solid'}],
        },
        'error_handling': {
            'python': [{'title': 'Python: Custom Exception Hierarchies', 'type': 'documentation', 'url': 'https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions'}],
            '_default': [{'title': 'Error Handling Patterns in Distributed Systems', 'type': 'article', 'url': 'https://refactoring.guru/design-patterns/chain-of-responsibility'}],
        },
        'input_validation': {
            '_default': [{'title': 'OWASP: Advanced Input Validation & Security Testing', 'type': 'documentation', 'url': 'https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/'}],
        },
        'database_queries': {
            '_default': [{'title': 'Advanced SQL: Query Optimization & Indexing', 'type': 'article', 'url': 'https://use-the-index-luke.com/'}],
        },
        'xss_csrf_prevention': {
            '_default': [{'title': 'OWASP: Advanced Security Headers & CSP', 'type': 'documentation', 'url': 'https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html'}],
        },
        'accessibility': {
            '_default': [{'title': 'WAI-ARIA: Advanced Accessible Patterns', 'type': 'documentation', 'url': 'https://www.w3.org/WAI/ARIA/apg/patterns/'}],
        },
        'api_design': {
            '_default': [{'title': 'API Design: Versioning, Pagination & HATEOAS', 'type': 'article', 'url': 'https://restfulapi.net/hateoas/'}],
        },
    }

    NEXT_LEVEL_TIPS = {
        'clean_code': 'Je schrijft consistent schone code. Level up met design patterns en door anderen te onderwijzen via code reviews.',
        'code_structure': 'Je codestructuur is solide. Focus op architectuur-patronen — hoe modules met elkaar communiceren en systeemgrenzen.',
        'dry_principle': 'Je vermijdt duplicatie goed. Focus nu op de juiste abstracties — over-DRY-code kan lastiger te lezen zijn dan wat herhaling.',
        'error_handling': 'Je error handling is sterk. Ga door naar resilience-patronen: retries, circuit breakers, graceful degradation.',
        'input_validation': 'Validatie is op orde. Verken fuzz-testing en security-first design om proactief edge cases te vinden.',
        'edge_cases': 'Je handelt edge cases goed af. Push verder met property-based testing om cases te ontdekken waar je niet aan dacht.',
        'secrets_management': 'Geheimen worden goed beheerd. Verdiep je in secret rotation, audit logging en zero-trust architectuur.',
        'database_queries': 'Je queries zijn veilig. Level up met query-optimalisatie, explain plans en indexing-strategieën.',
        'xss_csrf_prevention': 'Security-fundamenten zijn solide. Ga door naar Content Security Policy, security headers en penetration testing.',
        'accessibility': 'Sterke accessibility-praktijken. Push naar WCAG AA/AAA compliance en screen reader testing.',
        'responsive_design': 'Responsive design is sterk. Verken container queries, progressive enhancement en performance budgets.',
        'comments_docs': 'Documentatie is goed. Overweeg architecture decision records (ADRs) en automatische doc-generatie.',
    }

    def _get_advanced_resources(self, skill_slug, primary_language=None):
        """Get advanced resources for a skill the developer has mastered."""
        lang = (primary_language or '').lower()
        adv_docs = self.ADVANCED_DOCS.get(skill_slug, {})
        resources = adv_docs.get(lang) or adv_docs.get('_default') or []
        if not resources:
            # Fall back to regular resources
            return self._get_resources_for_skill(skill_slug, primary_language)
        return resources

    def _get_next_level_tip(self, skill_slug, current_score, primary_language=None):
        """Get a tip for pushing a good skill to expert level."""
        tip = self.NEXT_LEVEL_TIPS.get(skill_slug)
        if tip:
            return tip
        readable = skill_slug.replace('_', ' ').title()
        return f'Je doet het goed op {readable} ({current_score:.0f}/100). Zoek geavanceerde patronen en leer deze skill aan anderen om je expertise te verstevigen.'
