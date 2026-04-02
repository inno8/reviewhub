"""
Webhook handlers for Git providers.
"""
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from typing import Optional
import hmac
import hashlib
import json

from app.models.schemas import GitHubPushEvent, WebhookResponse
from app.services.diff_extractor import DiffExtractor
from app.services.llm_adapter import LLMAdapter
from app.services.django_client import DjangoClient
from app.services.context_builder import ContextBuilder
from app.services.embedding_store import EmbeddingStore
from app.services.adaptive_profile import (
    build_profile_from_skill_data,
    enrich_context_files,
)
from app.services.classifier import CommitClassifier
from app.core.config import settings

_commit_classifier = CommitClassifier()

router = APIRouter()


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not signature or not secret:
        return False
    
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


@router.post("/github/{project_id}", response_model=WebhookResponse)
async def github_webhook(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    """
    Handle GitHub push webhook.
    
    1. Verify signature
    2. Parse push event
    3. Queue analysis for each commit
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature (if secret is configured)
    print(f"DEBUG: GITHUB_WEBHOOK_SECRET = {repr(settings.GITHUB_WEBHOOK_SECRET)}")
    if settings.GITHUB_WEBHOOK_SECRET:
        print(f"DEBUG: Verifying signature...")
        if not verify_github_signature(
            body, 
            x_hub_signature_256 or "", 
            settings.GITHUB_WEBHOOK_SECRET
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        print("DEBUG: Skipping signature verification (no secret configured)")
    
    # Only process push events
    if x_github_event != "push":
        return WebhookResponse(
            success=True,
            message=f"Ignored event: {x_github_event}",
            commits_processed=0
        )
    
    # Parse payload
    try:
        payload = json.loads(body)
        event = GitHubPushEvent(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
    
    # Skip if no commits
    if not event.commits:
        return WebhookResponse(
            success=True,
            message="No commits to process",
            commits_processed=0
        )
    
    # Extract branch name from ref (refs/heads/main -> main)
    branch = event.ref.replace("refs/heads/", "")
    
    sender_login = event.sender.get("login", "") if isinstance(event.sender, dict) else ""
    
    # Queue background processing for each commit
    for commit in event.commits:
        background_tasks.add_task(
            process_commit,
            project_id=project_id,
            commit=commit.model_dump(),
            repo_url=event.repository.html_url,
            branch=branch,
            sender_login=sender_login,
        )
    
    return WebhookResponse(
        success=True,
        message=f"Processing {len(event.commits)} commit(s)",
        commits_processed=len(event.commits)
    )


async def process_commit(
    project_id: int,
    commit: dict,
    repo_url: str,
    branch: str,
    sender_login: str = "",
):
    """
    Background task to process a single commit.

    Pipeline:
    1. Resolve commit author → user
    2. Phase 5 – fetch adaptive profile for personalised prompt
    3. Phase 3 – extract diff + build import-aware context files
    4. Phase 4 – semantic search against project FAISS index for similar patterns
    5. LLM evaluation (prompt enriched with profile + context + similar code)
    6. Phase 4 – index changed files into FAISS after evaluation
    7. Store results in Django
    """
    import time

    start_time = time.time()

    try:
        diff_extractor = DiffExtractor()
        llm_adapter = LLMAdapter()
        django_client = DjangoClient()

        author_email = commit["author"].get("email", "unknown@example.com")

        # ── 1. Resolve user ────────────────────────────────────────────────
        user = await django_client.get_user_by_email(author_email)
        if not user:
            member = await django_client.get_project_member_by_email(project_id, author_email)
            if member:
                user = {"id": member.get("user")}

        # ── 2. Phase 5 – adaptive profile ─────────────────────────────────
        profile: dict = {}
        if user and user.get("id"):
            raw = await django_client.get_adaptive_profile(user["id"], project_id)
            if raw and isinstance(raw, dict):
                if raw.get("level"):
                    profile = raw
                elif raw.get("categories"):
                    # Fallback shape from get_user_skill_profile
                    eval_count = raw.get("evaluation_count", 0)
                    profile = build_profile_from_skill_data(raw["categories"], eval_count)

        # ── 3. Phase 3 – extract diff ──────────────────────────────────────
        diff_data = await diff_extractor.extract_commit_diff(
            repo_url=repo_url,
            commit_sha=commit["id"],
        )

        if not diff_data or not diff_data.get("files"):
            print(f"No diff data for commit {commit['id'][:7]}")
            return

        # ── 3b. Classify commit complexity (heuristic, no I/O) ────────────
        complexity = _commit_classifier.classify(
            diff_data=diff_data,
            commit_meta={"message": commit.get("message", ""), "id": commit.get("id", "")},
            profile=profile or {},
        )
        print(
            f"[CLASSIFIER] commit={commit['id'][:7]} level={complexity.level} "
            f"score={complexity.score} reasons={complexity.reasons}"
        )

        # Build import-based context from the cached repo
        repo_path = diff_extractor._get_repo_path(repo_url)
        context_builder = ContextBuilder(repo_path)
        import_context = await context_builder.build(diff_data["files"])

        # ── 4. Phase 4 – FAISS semantic context ───────────────────────────
        embedding_store = EmbeddingStore(project_id, settings.GIT_CACHE_DIR)
        semantic_chunks: list[dict] = []
        for file_diff in diff_data["files"][:3]:
            chunks = await embedding_store.search_by_diff(file_diff.get("diff", ""), top_k=3)
            for chunk in chunks:
                semantic_chunks.append({
                    "path": f"[similar] {chunk['path']}:{chunk['start_line']}-{chunk['end_line']}",
                    "content": chunk["text"],
                })

        # Merge context: profile + imports + semantic (deduplicate by path)
        # The complexity.context_file_limit cap is applied inside evaluate_diff
        base_context = enrich_context_files(import_context + semantic_chunks, profile)

        # ── 5. Analyze each changed file ──────────────────────────────────
        all_findings = []
        total_score = 0.0
        file_count = 0
        total_tokens = 0

        for file_diff in diff_data["files"]:
            result = await llm_adapter.evaluate_diff(
                diff=file_diff["diff"],
                file_path=file_diff["path"],
                language=file_diff.get("language", "unknown"),
                context_files=base_context,
                complexity=complexity,
            )
            if result:
                all_findings.extend(result.findings)
                total_score += result.overall_score
                total_tokens += result.tokens_used
                file_count += 1

        overall_score = total_score / file_count if file_count > 0 else 100.0
        processing_ms = int((time.time() - start_time) * 1000)

        # ── 6. Phase 4 – index changed files into FAISS ───────────────────
        files_to_index = []
        for file_diff in diff_data["files"]:
            content = await context_builder._read_file(file_diff["path"])
            if content:
                files_to_index.append({"path": file_diff["path"], "content": content})
        if files_to_index:
            await embedding_store.index_files(files_to_index)

        # Active model may differ from org default when complexity < complex
        active_model = llm_adapter.model_for_complexity(complexity.level)

        # ── 7. Store in Django ─────────────────────────────────────────────
        await django_client.create_evaluation({
            "project_id": project_id,
            "commit_sha": commit["id"],
            "commit_message": commit["message"],
            "commit_timestamp": commit.get("timestamp"),
            "branch": branch,
            "author_name": commit["author"].get("name", "Unknown"),
            "author_email": author_email,
            "files_changed": len(diff_data["files"]),
            "lines_added": diff_data.get("lines_added", 0),
            "lines_removed": diff_data.get("lines_removed", 0),
            "overall_score": overall_score,
            "llm_model": active_model,
            "llm_tokens_used": total_tokens,
            "processing_ms": processing_ms,
            "findings": [f.model_dump() for f in all_findings],
            "sender_login": sender_login,
            "commit_complexity": complexity.level,
            "complexity_score": complexity.score,
        })

        print(
            f"[OK] Processed commit {commit['id'][:7]}: "
            f"{len(all_findings)} findings, score {overall_score:.1f}, "
            f"complexity={complexity.level}({complexity.score}), "
            f"model={active_model}, "
            f"context={len(import_context)} import files, "
            f"semantic={len(semantic_chunks)} chunks, "
            f"profile_level={profile.get('level', 'n/a')}"
        )

    except Exception as e:
        print(f"[ERROR] Error processing commit {commit['id'][:7]}: {str(e)}")


@router.post("/gitlab/{project_id}", response_model=WebhookResponse)
async def gitlab_webhook(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_token: Optional[str] = Header(None),
):
    """Handle GitLab push webhook."""
    body = await request.body()

    # Verify token
    if settings.GITHUB_WEBHOOK_SECRET and x_gitlab_token != settings.GITHUB_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        payload = json.loads(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    if payload.get("object_kind") != "push":
        return WebhookResponse(success=True, message=f"Ignored event: {payload.get('object_kind')}", commits_processed=0)

    commits = payload.get("commits", [])
    if not commits:
        return WebhookResponse(success=True, message="No commits", commits_processed=0)

    branch = (payload.get("ref", "")).replace("refs/heads/", "")
    repo_url = payload.get("repository", {}).get("homepage", "") or payload.get("project", {}).get("web_url", "")
    sender_login = payload.get("user_username", "")

    for c in commits:
        background_tasks.add_task(
            process_commit,
            project_id=project_id,
            commit={
                "id": c.get("id", ""),
                "message": c.get("message", ""),
                "timestamp": c.get("timestamp", ""),
                "author": c.get("author", {}),
            },
            repo_url=repo_url,
            branch=branch,
            sender_login=sender_login,
        )

    return WebhookResponse(success=True, message=f"Processing {len(commits)} commit(s)", commits_processed=len(commits))


@router.post("/bitbucket/{project_id}", response_model=WebhookResponse)
async def bitbucket_webhook(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handle Bitbucket push webhook."""
    body = await request.body()

    try:
        payload = json.loads(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    push_data = payload.get("push", {})
    changes = push_data.get("changes", [])
    if not changes:
        return WebhookResponse(success=True, message="No changes", commits_processed=0)

    repo_url = payload.get("repository", {}).get("links", {}).get("html", {}).get("href", "")
    sender_login = payload.get("actor", {}).get("username", "")
    total = 0

    for change in changes:
        branch = change.get("new", {}).get("name", "main")
        for c in change.get("commits", []):
            author = c.get("author", {})
            raw = author.get("raw", "Unknown <unknown@example.com>")
            # Parse "Name <email>" format
            import re
            m = re.match(r"(.+?)\s*<(.+?)>", raw)
            name = m.group(1) if m else raw
            email = m.group(2) if m else "unknown@example.com"

            background_tasks.add_task(
                process_commit,
                project_id=project_id,
                commit={
                    "id": c.get("hash", ""),
                    "message": c.get("message", ""),
                    "timestamp": c.get("date", ""),
                    "author": {"name": name, "email": email},
                },
                repo_url=repo_url,
                branch=branch,
                sender_login=sender_login,
            )
            total += 1

    return WebhookResponse(success=True, message=f"Processing {total} commit(s)", commits_processed=total)
