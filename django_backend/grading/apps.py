"""
Grading app — Nakijken Copilot v1.

Teacher-facing grading copilot. Reuses evaluations/skills engine.
Adds: Class (docent's class), Rubric (criteria + calibration),
GradingSession (AI draft + docent review state), LLMCostLog (metering).

See ~/.gstack/projects/inno8-reviewhub/yanic-main-design-20260417-175102.md.
"""
from django.apps import AppConfig


class GradingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "grading"
    verbose_name = "Grading (Nakijken Copilot)"
