"""
Learning Recommendations View
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from datetime import timedelta

from django.utils import timezone

from .models import SkillMetric


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
                'reason': f'Low score in {metric.skill.name}',
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
                    'reason': f'{data["count"]} recent issues in {skill.name}',
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
                    'reason': f'Declining trend in {metric.skill.name}',
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
                        f'Recurring pattern: {pattern.frequency} occurrences '
                        f'of {pattern.pattern_type} issues'
                    ),
                    'priority': 'high' if pattern.frequency >= 10 else 'medium',
                    'issue_count': pattern.frequency,
                    'pattern_key': pattern.pattern_key,
                    'improvement_tip': (
                        f'You have {pattern.frequency} recurring {pattern.pattern_type} '
                        f'issues. Focus on this area to see the biggest improvement.'
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
                    'reason': f'Great progress! {metric.skill.name} improved from {metric.previous_score:.0f} to {metric.score:.0f}',
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
                        'reason': f'Good at {metric.skill.name} ({metric.score:.0f}/100) — push to expert level',
                        'priority': 'growth',
                        'issue_count': metric.issue_count,
                        'suggested_resources': self._get_advanced_resources(metric.skill.slug, primary_language),
                        'improvement_tip': self._get_next_level_tip(metric.skill.slug, metric.score, primary_language),
                        'user_level': user_level,
                    })

        # Sort by priority and limit
        priority_order = {'high': 0, 'medium': 1, 'low': 2, 'mastered': 3, 'growth': 4}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 5))

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
            'clean_code': f'Your code has naming and formatting issues. Follow {lang.upper() or "language"} style conventions consistently.',
            'code_structure': 'Break large functions into smaller, focused ones. Each function should do one thing well.',
            'dry_principle': 'Look for repeated patterns in your code. Extract shared logic into reusable functions.',
            'input_validation': 'Never trust user input. Always validate and sanitize before using in queries or rendering.',
            'secrets_management': 'Move all secrets (API keys, passwords) to environment variables. Never commit them to git.',
            'error_handling': 'Wrap risky operations in try/except blocks. Handle specific exceptions, not bare except.',
            'edge_cases': 'Think about what happens with empty input, None values, or unexpected types.',
            'html_semantics': 'Use semantic HTML tags (<header>, <nav>, <main>, <section>) instead of generic <div>.',
            'accessibility': 'Add alt text to images, use ARIA labels on interactive elements, ensure keyboard navigation.',
            'css_organization': 'Avoid inline styles. Use CSS classes and combine shared properties to reduce duplication.',
            'responsive_design': 'Use relative units (rem, %) and media queries for layouts that adapt to screen size.',
            'xss_csrf_prevention': 'Never use innerHTML with user data. Use textContent or a sanitization library.',
            'database_queries': 'Use parameterized queries with ? placeholders. Never build SQL with string concatenation.',
            'comments_docs': 'Add docstrings to functions explaining what they do, their parameters, and return values.',
        }

        base_tip = tips_map.get(skill_slug, f'Review recent issues and identify common patterns in your {skill_slug.replace("_", " ")} code.')

        if issue_count > 10:
            return f'{base_tip} You have {issue_count} issues — start with the most critical ones first.'
        elif issue_count > 5:
            return f'{base_tip} Focus on preventing similar issues in new code.'
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
        'clean_code': 'You write clean code consistently. Level up by applying design patterns and teaching others through code reviews.',
        'code_structure': 'Your code structure is solid. Focus on architectural patterns — how modules communicate and system boundaries.',
        'dry_principle': 'You avoid duplication well. Now focus on the right abstractions — over-DRY code can be harder to read than some repetition.',
        'error_handling': 'Your error handling is strong. Advance to resilience patterns: retries, circuit breakers, graceful degradation.',
        'input_validation': 'Validation is on point. Explore fuzz testing and security-first design to proactively find edge cases.',
        'edge_cases': 'You handle edge cases well. Push further with property-based testing to discover cases you haven\'t thought of.',
        'secrets_management': 'Secrets are managed well. Look into secret rotation, audit logging, and zero-trust architecture.',
        'database_queries': 'Your queries are safe. Level up with query optimization, explain plans, and indexing strategies.',
        'xss_csrf_prevention': 'Security fundamentals are solid. Advance to Content Security Policy, security headers, and penetration testing.',
        'accessibility': 'Great accessibility practices. Push to WCAG AA/AAA compliance and screen reader testing.',
        'responsive_design': 'Responsive design is strong. Explore container queries, progressive enhancement, and performance budgets.',
        'comments_docs': 'Documentation is good. Consider architecture decision records (ADRs) and automated doc generation.',
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
        return f'You\'re doing well at {readable} ({current_score:.0f}/100). Look for advanced patterns and teach this skill to solidify your expertise.'
