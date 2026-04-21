"""
Internal endpoint for the ai_engine Layer 1 shadow-mode pipeline to write
DeterministicFinding rows. Strictly additive — NOT surfaced to teachers yet.

Scope B2 of Nakijken Copilot v1 (hybrid architecture).
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeterministicFinding, Evaluation


class _DeterministicFindingIn(serializers.Serializer):
    runner = serializers.ChoiceField(choices=DeterministicFinding.Runner.choices)
    rule_id = serializers.CharField(max_length=64)
    message = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=DeterministicFinding.Severity.choices,
        default=DeterministicFinding.Severity.WARNING,
    )
    file_path = serializers.CharField(max_length=500)
    line_start = serializers.IntegerField(min_value=1)
    line_end = serializers.IntegerField(min_value=1)


class InternalDeterministicFindingCreateView(APIView):
    """
    POST /api/evaluations/internal/deterministic-findings/

    Body:
      {
        "evaluation_id": 123,
        "findings": [
          {"runner": "ruff", "rule_id": "E501", "message": "line too long",
           "severity": "info", "file_path": "app/x.py",
           "line_start": 42, "line_end": 42},
          ...
        ]
      }

    Protected by INTERNAL_API_KEY header (same as other internal endpoints).
    """

    authentication_classes: list = []

    def get_permissions(self):
        from reviewhub.permissions import IsInternalAPIKey
        return [IsInternalAPIKey()]

    def post(self, request, *args, **kwargs):
        eval_id = request.data.get('evaluation_id')
        if not eval_id:
            return Response(
                {'detail': 'evaluation_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        evaluation = get_object_or_404(Evaluation, pk=eval_id)

        raw_findings = request.data.get('findings') or []
        if not isinstance(raw_findings, list):
            return Response(
                {'detail': 'findings must be a list'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = _DeterministicFindingIn(data=raw_findings, many=True)
        serializer.is_valid(raise_exception=True)

        created = DeterministicFinding.objects.bulk_create([
            DeterministicFinding(evaluation=evaluation, **row)
            for row in serializer.validated_data
        ])

        return Response(
            {'created': len(created), 'evaluation_id': evaluation.id},
            status=status.HTTP_201_CREATED,
        )
