"""
Verifies that CREBO_RUBRIC_CRITERIA has a pedagogically-defensible,
non-uniform weight distribution that sums to exactly 100. See
May 7 2026 pitch deck at Media College Amsterdam.
"""
from __future__ import annotations

import pytest

from grading.rubric_defaults import CREBO_RUBRIC_CRITERIA


EXPECTED_WEIGHTS = {
    "code_kwaliteit": 20,
    "veiligheid": 20,
    "testen": 20,
    "code_ontwerp": 15,
    "samenwerking": 15,
    "verbetering": 10,
}


def test_crebo_weights_sum_to_100():
    total = sum(c["weight"] for c in CREBO_RUBRIC_CRITERIA)
    assert total == 100, f"weights must sum to 100, got {total}"


def test_crebo_weights_match_expected_distribution():
    actual = {c["id"]: c["weight"] for c in CREBO_RUBRIC_CRITERIA}
    assert actual == EXPECTED_WEIGHTS, (
        f"weights drifted from pitched distribution. expected={EXPECTED_WEIGHTS} "
        f"actual={actual}"
    )


def test_weights_are_numeric_not_strings():
    for c in CREBO_RUBRIC_CRITERIA:
        assert isinstance(c["weight"], (int, float)), (
            f"criterion {c['id']} weight must be numeric, got {type(c['weight'])}"
        )


@pytest.mark.django_db
def test_sync_rubric_weights_command_idempotent():
    """After sync, stored Rubric rows have the right weights and running twice is a no-op."""
    from django.core.management import call_command
    from io import StringIO
    from grading.models import Rubric
    from users.models import Organization

    org = Organization.objects.create(name="Test Org")

    # Seed a Crebo-shaped rubric with uniform 1.0 weights (the pre-fix state).
    legacy_criteria = [
        {**c, "weight": 1.0} for c in CREBO_RUBRIC_CRITERIA
    ]
    rubric = Rubric.objects.create(
        org=org, name="Test Rubric", criteria=legacy_criteria, calibration={}
    )

    out = StringIO()
    call_command("sync_rubric_weights", stdout=out)

    rubric.refresh_from_db()
    actual = {c["id"]: c["weight"] for c in rubric.criteria}
    assert actual == EXPECTED_WEIGHTS
    assert sum(c["weight"] for c in rubric.criteria) == 100

    # Second run is a no-op.
    out2 = StringIO()
    call_command("sync_rubric_weights", stdout=out2)
    assert "Nothing to update." in out2.getvalue()
