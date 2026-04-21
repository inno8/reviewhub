"""
Integration hook: run Layer 1 runners over a set of changed files and
ship findings to the Django side as DeterministicFinding rows.

SHADOW MODE in v1: this function runs in parallel with the LLM pipeline
and never mutates LLM behaviour. See
`docs/hybrid-algorithm-research-2026-04-19.md` for full rationale.

Integration point (Bucket 3 WIP territory): once the updated webhook path
lands, it should call `run_layer1_shadow(...)` alongside the LLM call.
This module is kept deliberately standalone so it can be imported without
touching webhooks.py / llm_adapter.py / schemas.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, List, Optional, Sequence, Tuple

import httpx

from app.core.config import settings
from .deterministic import (
    DeterministicFinding,
    ESLintRunner,
    RuffRunner,
    runner_for_path,
)

logger = logging.getLogger(__name__)


def run_layer1_runners(
    files: Iterable[Tuple[str, str]],
    *,
    ruff: Optional[RuffRunner] = None,
    eslint: Optional[ESLintRunner] = None,
) -> List[DeterministicFinding]:
    """
    Run Layer 1 runners over (file_path, source) pairs and return a
    flat list of findings. Synchronous — caller should run this in a
    threadpool if it's inside an async handler.
    """
    ruff = ruff or RuffRunner()
    eslint = eslint or ESLintRunner()
    out: List[DeterministicFinding] = []
    for path, source in files:
        runner = runner_for_path(path, ruff=ruff, eslint=eslint)
        if runner is None:
            continue
        try:
            out.extend(runner.run(path, source))
        except Exception as exc:  # pragma: no cover — safety net
            logger.exception("Layer 1 runner %s crashed on %s: %s", runner.name, path, exc)
    return out


async def post_deterministic_findings(
    evaluation_id: int,
    findings: Sequence[DeterministicFinding],
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> bool:
    """
    POST findings to the internal Django endpoint. Returns True on success.
    Swallows all network errors — shadow mode must never crash the pipeline.
    """
    if not findings:
        return True

    url = f"{settings.BACKEND_API_URL.rstrip('/')}/api/evaluations/internal/deterministic-findings/"
    payload = {
        "evaluation_id": evaluation_id,
        "findings": [f.as_payload() for f in findings],
    }
    headers = {}
    if settings.BACKEND_API_KEY:
        headers["X-API-Key"] = settings.BACKEND_API_KEY

    owned_client = client is None
    try:
        client = client or httpx.AsyncClient(timeout=15.0)
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "deterministic-findings POST returned %s: %s",
                    resp.status_code, resp.text[:200],
                )
                return False
            return True
        finally:
            if owned_client:
                await client.aclose()
    except Exception as exc:  # pragma: no cover — shadow mode
        logger.warning("deterministic-findings POST failed: %s", exc)
        return False


async def run_layer1_shadow(
    evaluation_id: int,
    files: Iterable[Tuple[str, str]],
) -> int:
    """
    Top-level hook: run all runners, post results. Returns the number of
    findings shipped. Safe to fire-and-forget from the webhook handler.
    """
    findings = await asyncio.to_thread(run_layer1_runners, list(files))
    ok = await post_deterministic_findings(evaluation_id, findings)
    return len(findings) if ok else 0
