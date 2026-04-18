"""
Shared pytest fixtures for ReviewHub Django backend tests.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    """DRF API client for making test requests."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a basic developer user for testing."""
    user = User.objects.create_user(
        email="dev@test.com",
        username="testdev",
        password="testpass123",
        role="developer",
    )
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    user = User.objects.create_user(
        email="admin@test.com",
        username="testadmin",
        password="adminpass123",
        role="admin",
    )
    return user


@pytest.fixture
def auth_client(api_client, test_user):
    """API client authenticated as test_user."""
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """API client authenticated as admin_user."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def test_project(db, test_user):
    """Create a test project linked to test_user."""
    from projects.models import Project, ProjectMember
    project = Project.objects.create(
        name="Test Project",
        repo_owner="testorg",
        repo_name="testrepo",
        provider="github",
        created_by=test_user,
    )
    ProjectMember.objects.create(
        project=project,
        user=test_user,
        role="owner",
        git_email=test_user.email,
    )
    return project


@pytest.fixture
def skill_categories(db):
    """Seed skill categories and skills needed for tests."""
    from skills.models import SkillCategory, Skill

    categories = {}
    skill_data = {
        "Code Quality": ["clean_code", "code_structure", "dry_principle", "comments_docs"],
        "Security": ["input_validation", "auth_practices", "secrets_management", "xss_csrf_prevention"],
        "Backend": ["api_design", "database_queries", "error_handling", "performance"],
        "Testing": ["unit_testing", "test_coverage", "test_quality", "tdd"],
    }

    for idx, (cat_name, skills) in enumerate(skill_data.items()):
        slug = cat_name.lower().replace(" ", "_")
        cat = SkillCategory.objects.create(
            name=cat_name,
            slug=slug,
            order=idx,
        )
        categories[cat_name] = cat
        for skill_idx, skill_slug in enumerate(skills):
            Skill.objects.create(
                category=cat,
                name=skill_slug.replace("_", " ").title(),
                slug=skill_slug,
                order=skill_idx,
            )

    return categories


@pytest.fixture
def test_evaluation(db, test_user, test_project):
    """Create a completed evaluation with findings."""
    from evaluations.models import Evaluation, Finding

    evaluation = Evaluation.objects.create(
        project=test_project,
        author=test_user,
        commit_sha="abc123def456",
        commit_message="feat: add user login",
        branch="main",
        author_name="testdev",
        author_email="dev@test.com",
        overall_score=65.0,
        status="completed",
        files_changed=2,
    )

    finding = Finding.objects.create(
        evaluation=evaluation,
        title="SQL Injection vulnerability",
        description="Using string concatenation in SQL query",
        severity="critical",
        file_path="app/db.py",
        line_start=42,
        line_end=42,
        original_code='cursor.execute("SELECT * FROM users WHERE id = " + user_id)',
        suggested_code='cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))',
        explanation="String concatenation in SQL allows attackers to inject malicious SQL.",
    )

    return evaluation, finding
