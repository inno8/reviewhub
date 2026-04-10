"""
Batch Processing API - Phase 6
Handles repository analysis for building developer profiles.
"""
import os
import asyncio
import shutil
import subprocess
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx

from app.core.config import settings
from app.services.llm_adapter import LLMAdapter
from app.services.django_client import DjangoClient
from app.services.context_builder import ContextBuilder
from app.services.embedding_store import EmbeddingStore
from app.services.adaptive_profile import (
    build_profile_from_skill_data,
    enrich_context_files,
)
from app.services.classifier import CommitClassifier

_commit_classifier = CommitClassifier()

# Batch-only: skip LLM entirely for trivially simple commits (score < this threshold)
BATCH_SKIP_SCORE_THRESHOLD = 3.0

router = APIRouter()

# In-memory job tracking (for simplicity; use Redis in production)
active_jobs: dict = {}

# Batch is slower than webhooks; cap work per commit to keep small repos fast.
BATCH_MAX_FILES_PER_COMMIT = 4
BATCH_MAX_DIFF_CHARS = 14_000
# Concurrent LLM calls per commit (still bounded to avoid rate limits)
BATCH_LLM_CONCURRENCY = 3


class BatchStartRequest(BaseModel):
    job_id: int
    repo_url: str
    branch: str = "main"
    # Populated by Django from GitHub + optional author filter (or a single branch).
    resolved_branches: Optional[list[str]] = None
    target_github_username: Optional[str] = None
    max_commits: int = 500
    since_date: Optional[str] = None
    # Django Project FK when the batch job is linked to a project (evaluations require it).
    project_id: Optional[int] = None
    # User who started the batch (Django user id); used for adaptive profile enrichment.
    submitter_user_id: Optional[int] = None
    # Org admin LLM credentials passed from Django so the AI engine uses the right provider
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None


def _evaluation_project_id(req: BatchStartRequest) -> int:
    """Use linked project when present; otherwise legacy fallback (job_id == project pk)."""
    if req.project_id is not None:
        return req.project_id
    return req.job_id


class BatchCancelRequest(BaseModel):
    job_id: int


def _is_windows() -> bool:
    return os.name == "nt"


def _git_cmd(*args: str) -> list[str]:
    """
    Build a git argv. On Windows, prefer long paths and symlinks as plain files —
    without this, many repos fail with 'Clone succeeded, but checkout failed'.
    """
    cmd = ["git"]
    if _is_windows():
        cmd.extend(
            [
                "-c",
                "core.longpaths=true",
                "-c",
                "core.symlinks=false",
            ]
        )
    cmd.extend(args)
    return cmd


def _git_clone_cmd(repo_url: str, dest: str, *, ntfs_relaxed: bool = False) -> list[str]:
    cmd = ["git"]
    if _is_windows():
        cmd.extend(
            [
                "-c",
                "core.longpaths=true",
                "-c",
                "core.symlinks=false",
            ]
        )
        if ntfs_relaxed:
            cmd.extend(["-c", "core.protectNTFS=false"])
    cmd.extend(["clone", repo_url, dest])
    return cmd


def _git_run(*git_args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        _git_cmd(*git_args),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _repo_is_usable(repo_path: Path) -> bool:
    if not repo_path.is_dir() or not (repo_path / ".git").exists():
        return False
    r = _git_run("rev-parse", "--git-dir", cwd=repo_path)
    return r.returncode == 0


def _clone_with_windows_fallback(repo_url: str, repo_path: Path) -> subprocess.CompletedProcess:
    """Clone repository; on Windows repair worktree or re-clone with relaxed NTFS rules if checkout fails."""
    dest = str(repo_path)
    result = subprocess.run(
        _git_clone_cmd(repo_url, dest, ntfs_relaxed=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return result

    err = (result.stderr or "") + (result.stdout or "")
    if not _is_windows() or not repo_path.exists():
        return result

    if "checkout failed" not in err and "unable to checkout" not in err.lower():
        return result

    print(f"[BATCH] Git checkout failed after clone; attempting repair in {repo_path}", flush=True)
    _git_run("config", "core.longpaths", "true", cwd=repo_path)
    _git_run("config", "core.symlinks", "false", cwd=repo_path)
    repair = _git_run("restore", "--source=HEAD", ":/", cwd=repo_path)
    if repair.returncode == 0:
        return subprocess.CompletedProcess(_git_clone_cmd(repo_url, dest), 0, repair.stdout or "", "")

    print(
        f"[BATCH] Repair failed; removing cache dir and cloning with relaxed NTFS rules → {repo_path}",
        flush=True,
    )
    shutil.rmtree(repo_path, ignore_errors=True)
    return subprocess.run(
        _git_clone_cmd(repo_url, dest, ntfs_relaxed=True),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _django_batch_internal_url(job_id: int) -> str:
    """Django mounts batch routes at /api/batch/ (same pattern as /api/evaluations/...)."""
    base = settings.BACKEND_API_URL.rstrip("/")
    return f"{base}/api/batch/jobs/{job_id}/internal/"


async def update_job_status(job_id: int, status: str, **kwargs):
    """Update job status in Django backend."""
    headers = {"Content-Type": "application/json"}
    if settings.BACKEND_API_KEY:
        headers["X-API-Key"] = settings.BACKEND_API_KEY
    try:
        async with httpx.AsyncClient() as client:
            r = await client.patch(
                _django_batch_internal_url(job_id),
                json={"status": status, **kwargs},
                headers=headers,
                timeout=10,
            )
            if r.status_code >= 400:
                print(f"Batch status PATCH failed {r.status_code}: {r.text[:500]}")
    except Exception as e:
        print(f"Failed to update job {job_id}: {e}")


def _git_checkout_branch(repo_path: Path, branch: str) -> None:
    """Check out a branch; fetch from origin if missing locally."""
    r = _git_run("checkout", branch, cwd=repo_path)
    if r.returncode == 0:
        return
    _git_run("fetch", "origin", branch, cwd=repo_path)
    r2 = _git_run("checkout", "-B", branch, f"origin/{branch}", cwd=repo_path)
    if r2.returncode != 0:
        msg = (r2.stderr or r2.stdout or r.stderr or "").strip()
        raise Exception(f"Cannot checkout branch {branch}: {msg}")


def _git_commits_for_batch(
    repo_path: Path,
    max_commits: int,
    since_date: Optional[str],
    author_pattern: str,
) -> list[dict]:
    """Commit history on current HEAD (cap per branch)."""
    git_log_cmd = _git_cmd(
        "log",
        f"--max-count={max_commits}",
        "--format=%H|%an|%ae|%ad|%s",
        "--date=iso",
    )
    if (author_pattern or "").strip():
        git_log_cmd.extend(["--author", author_pattern.strip()])
    if since_date:
        git_log_cmd.extend(["--since", since_date])

    result = subprocess.run(
        git_log_cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    commits: list[dict] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append(
                {
                    "sha": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                }
            )
    return commits


async def process_batch_job(job_id: int, request: BatchStartRequest):
    """
    Background task to process a batch job.
    
    Steps:
    1. Clone/fetch repository
    2. Get commit history
    3. Analyze each commit
    4. Build developer profile
    """
    repos_dir = Path(settings.GIT_CACHE_DIR)
    repos_dir.mkdir(exist_ok=True)
    
    # Extract owner/repo from URL
    # https://github.com/owner/repo.git -> owner/repo
    parts = request.repo_url.rstrip('/').rstrip('.git').split('/')
    owner, repo = parts[-2], parts[-1]
    repo_path = repos_dir / f"{owner}_{repo}"
    
    try:
        active_jobs[job_id] = {"status": "cloning", "cancelled": False}
        
        # Step 1: Clone or fetch repository
        await update_job_status(job_id, "cloning")
        
        if repo_path.exists() and not _repo_is_usable(repo_path):
            print(f"[BATCH] Removing unusable git cache dir → {repo_path}", flush=True)
            shutil.rmtree(repo_path, ignore_errors=True)

        if repo_path.exists():
            # Fetch latest
            result = subprocess.run(
                _git_cmd("fetch", "--all"),
                cwd=repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        else:
            result = _clone_with_windows_fallback(request.repo_url, repo_path)
        
        if result.returncode != 0:
            raise Exception(f"Git error: {result.stderr}")

        branches_to_run = list(request.resolved_branches or [])
        if not branches_to_run:
            if request.branch and request.branch != "__all__":
                branches_to_run = [request.branch]
            else:
                raise Exception(
                    "No branches to process (resolved_branches empty). Recreate the job from the app."
                )

        await update_job_status(job_id, "analyzing")

        author_filter = (request.target_github_username or "").strip()
        plan: list[tuple[str, list[dict]]] = []
        for bname in branches_to_run:
            if active_jobs.get(job_id, {}).get("cancelled"):
                await update_job_status(job_id, "cancelled")
                return
            _git_checkout_branch(repo_path, bname)
            commits = _git_commits_for_batch(
                repo_path,
                request.max_commits,
                request.since_date,
                author_filter,
            )
            plan.append((bname, commits))

        total_commits = sum(len(c) for _, c in plan)
        await update_job_status(job_id, "analyzing", total_commits=total_commits)

        eval_project = _evaluation_project_id(request)
        if request.project_id is None:
            print(
                f"[BATCH] evaluation project_id={eval_project} (legacy: same as job_id). "
                "Link BatchJob.project in Django if evaluations fail with 'Project not found'."
            )

        try:
            llm = LLMAdapter(
                api_key=request.llm_api_key or None,
                provider_override=request.llm_provider or None,
                model_override=request.llm_model or None,
            )
            print(
                f"[BATCH] LLM provider={llm.provider} model={llm.model_name}",
                flush=True,
            )
        except ValueError as e:
            raise Exception(
                "No LLM configured for batch analysis. Set LLM_API_KEY / LLM_PROVIDER "
                "in the AI engine environment, or configure an LLM in Django Settings."
            ) from e

        # ── Phase 3 + 4 setup ──────────────────────────────────────────────
        context_builder = ContextBuilder(repo_path)
        embedding_store = EmbeddingStore(request.job_id, settings.GIT_CACHE_DIR)
        django_client_shared = DjangoClient()

        # ── Phase 5 – build adaptive profile once per job ─────────────────
        base_profile: dict = {}
        profile_uid = request.submitter_user_id
        if profile_uid:
            raw_profile = await django_client_shared.get_adaptive_profile(
                profile_uid, project_id=eval_project
            )
            if raw_profile and isinstance(raw_profile, dict):
                if raw_profile.get("level"):
                    base_profile = raw_profile
                elif raw_profile.get("categories"):
                    base_profile = build_profile_from_skill_data(
                        raw_profile["categories"],
                        raw_profile.get("evaluation_count", 0),
                    )

        sem = asyncio.Semaphore(BATCH_LLM_CONCURRENCY)
        sender_login = (request.target_github_username or "").strip()

        commit_queue: list[tuple[str, dict]] = []
        for bn, cms in plan:
            for c in cms:
                commit_queue.append((bn, c))

        # Step 3: Analyze each commit
        processed = 0
        findings_count = 0
        skills_detected = set()
        patterns_detected = set()

        for bname, commit in commit_queue:
            # Check if cancelled
            if active_jobs.get(job_id, {}).get("cancelled"):
                await update_job_status(job_id, "cancelled")
                return

            # Get full diff for this commit
            full_diff_result = subprocess.run(
                _git_cmd("diff", f"{commit['sha']}^", commit["sha"], "--no-color"),
                cwd=repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            diff_text = full_diff_result.stdout
            if not diff_text.strip():
                processed += 1
                continue

            # Parse diff into per-file chunks; prioritize largest changes
            file_diffs = _parse_diff_into_files(diff_text)
            files_changed = len(file_diffs)
            lines_added = sum(f.get("additions", 0) for f in file_diffs)
            lines_removed = sum(f.get("deletions", 0) for f in file_diffs)
            file_diffs.sort(
                key=lambda f: f.get("additions", 0) + f.get("deletions", 0),
                reverse=True,
            )
            to_analyze = file_diffs[:BATCH_MAX_FILES_PER_COMMIT]

            # ── Classify commit complexity (heuristic, no I/O) ────────────
            diff_data_for_classifier = {
                "files": to_analyze,
                "lines_added": lines_added,
                "lines_removed": lines_removed,
            }
            complexity = _commit_classifier.classify(
                diff_data=diff_data_for_classifier,
                commit_meta={"message": commit.get("message", ""), "id": commit.get("sha", "")},
                profile=base_profile or {},
            )
            print(
                f"[BATCH CLASSIFIER] {commit['sha'][:7]} "
                f"level={complexity.level} score={complexity.score}"
            )

            # Batch-only optimisation: skip trivially simple commits entirely
            if complexity.score < BATCH_SKIP_SCORE_THRESHOLD:
                print(f"[BATCH] Skipping trivial commit {commit['sha'][:7]} (score={complexity.score})")
                try:
                    await django_client_shared.create_evaluation({
                        "project_id": eval_project,
                        "batch_job_id": job_id,
                        "commit_sha": commit["sha"],
                        "commit_message": commit["message"],
                        "branch": bname,
                        "author_name": commit["author_name"],
                        "author_email": commit["author_email"],
                        "files_changed": files_changed,
                        "lines_added": lines_added,
                        "lines_removed": lines_removed,
                        "overall_score": None,
                        "llm_model": "skipped:simple",
                        "llm_tokens_used": 0,
                        "processing_ms": 0,
                        "findings": [],
                        "commit_complexity": complexity.level,
                        "complexity_score": complexity.score,
                        "sender_login": sender_login,
                    })
                except Exception as store_err:
                    print(f"[BATCH] Store error (skip) for {commit['sha'][:7]}: {store_err}")
                processed += 1
                if total_commits <= 20 or processed % 5 == 0 or processed == total_commits:
                    await update_job_status(job_id, "analyzing", processed_commits=processed)
                continue

            # ── Phase 3: import-aware context ─────────────────────────────
            import_context = await context_builder.build(to_analyze)

            # ── Phase 4: semantic context from FAISS ──────────────────────
            semantic_chunks: list[dict] = []
            for fd in to_analyze[:2]:
                chunks = await embedding_store.search_by_diff(fd.get("diff", ""), top_k=2)
                for chunk in chunks:
                    semantic_chunks.append({
                        "path": f"[similar] {chunk['path']}:{chunk['start_line']}-{chunk['end_line']}",
                        "content": chunk["text"],
                    })

            # ── Phase 5: enrich with adaptive profile ─────────────────────
            # complexity.context_file_limit will be applied inside evaluate_diff
            context_files = enrich_context_files(
                import_context + semantic_chunks, base_profile
            )

            # Wrap evaluate_file_diff to pass complexity
            async def evaluate_file_diff_with_complexity(fd: dict, ctx: list):
                raw = fd["diff"] or ""
                if len(raw) > BATCH_MAX_DIFF_CHARS:
                    raw = raw[:BATCH_MAX_DIFF_CHARS] + "\n... [diff truncated for batch speed]\n"
                async with sem:
                    return await llm.evaluate_diff(
                        diff=raw,
                        file_path=fd["path"],
                        language=fd.get("language", "unknown"),
                        context_files=ctx,
                        complexity=complexity,
                    )

            # Run LLM analysis on selected files in parallel
            commit_findings = []
            commit_score = 0.0
            commit_tokens = 0
            file_count = 0

            try:
                results = await asyncio.gather(
                    *[evaluate_file_diff_with_complexity(fd, context_files) for fd in to_analyze],
                    return_exceptions=True,
                )
                for fd, res in zip(to_analyze, results):
                    sha7 = commit['sha'][:7]
                    if isinstance(res, Exception):
                        print(f"[BATCH] LLM exception {sha7} {fd['path']}: {res}")
                        continue
                    if res is None:
                        print(f"[BATCH] LLM returned None (parse/API failure) {sha7} {fd['path']}")
                        continue
                    print(
                        f"[BATCH] LLM ok {sha7} {fd['path']} "
                        f"score={res.overall_score} findings={len(res.findings)} "
                        f"model={res.llm_model}"
                    )
                    commit_findings.extend(res.findings)
                    commit_score += res.overall_score
                    commit_tokens += res.tokens_used
                    file_count += 1
                    for f in res.findings:
                        for s in f.skills_affected:
                            skills_detected.add(s)
            except Exception as llm_err:
                print(f"[BATCH] LLM error for {commit['sha'][:7]}: {llm_err}")

            if file_count:
                overall_score = commit_score / file_count
            else:
                overall_score = None
                print(
                    f"[BATCH] No successful LLM results for {commit['sha'][:7]} "
                    f"({len(to_analyze)} file(s) attempted); storing score=null"
                )
            findings_count += len(commit_findings)
            active_model = llm.model_for_complexity(complexity.level)

            # ── Phase 4: index the files we just processed ────────────────
            files_to_index = []
            for fd in to_analyze:
                content = await context_builder._read_file(fd["path"])
                if content:
                    files_to_index.append({"path": fd["path"], "content": content})
            if files_to_index:
                await embedding_store.index_files(files_to_index)

            # Store evaluation in Django
            try:
                await django_client_shared.create_evaluation({
                    "project_id": eval_project,
                    "batch_job_id": job_id,
                    "commit_sha": commit["sha"],
                    "commit_message": commit["message"],
                    "branch": bname,
                    "author_name": commit["author_name"],
                    "author_email": commit["author_email"],
                    "files_changed": files_changed,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "overall_score": overall_score,
                    "llm_model": active_model if file_count else "none",
                    "llm_tokens_used": commit_tokens,
                    "processing_ms": 0,
                    "findings": [f.model_dump() for f in commit_findings],
                    "commit_complexity": complexity.level,
                    "complexity_score": complexity.score,
                    "sender_login": sender_login,
                })
            except Exception as store_err:
                print(f"[BATCH] Store error for {commit['sha'][:7]}: {store_err}")

            processed += 1

            # Frequent progress for small jobs so the UI does not look stuck
            if total_commits <= 20 or processed % 5 == 0 or processed == total_commits:
                await update_job_status(job_id, "analyzing", processed_commits=processed)

        # Step 4: Build developer profile summary
        await update_job_status(job_id, "building_profile", processed_commits=processed)

        # Mark complete
        await update_job_status(
            job_id, "completed",
            processed_commits=processed,
            findings_count=findings_count,
            skills_detected=list(skills_detected),
            patterns_detected=list(patterns_detected)
        )
        
    except Exception as e:
        await update_job_status(job_id, "failed", error_message=str(e))
    finally:
        active_jobs.pop(job_id, None)


@router.post("/start")
async def start_batch_job(request: BatchStartRequest, background_tasks: BackgroundTasks):
    """
    Start a batch analysis job.
    Called by Django when a job is created.
    """
    if request.job_id in active_jobs:
        raise HTTPException(status_code=400, detail="Job already running")
    
    # Add to background tasks
    background_tasks.add_task(process_batch_job, request.job_id, request)
    
    return {
        "status": "started",
        "job_id": request.job_id,
        "message": "Batch analysis started in background"
    }


@router.post("/cancel")
async def cancel_batch_job(request: BatchCancelRequest):
    """
    Cancel a running batch job.
    """
    if request.job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found or not running")
    
    active_jobs[request.job_id]["cancelled"] = True
    
    return {
        "status": "cancelling",
        "job_id": request.job_id,
        "message": "Cancellation requested"
    }


@router.get("/status/{job_id}")
async def get_job_status(job_id: int):
    """
    Get current status of a batch job.
    """
    if job_id in active_jobs:
        return {
            "job_id": job_id,
            "status": active_jobs[job_id].get("status", "unknown"),
            "running": True
        }
    return {
        "job_id": job_id,
        "status": "not_running",
        "running": False
    }


def _parse_diff_into_files(diff_text: str) -> list:
    """Parse a unified diff into per-file chunks."""
    import re

    files = []
    current = None
    additions = 0
    deletions = 0

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            if current:
                current["additions"] = additions
                current["deletions"] = deletions
                files.append(current)
            match = re.search(r"b/(.+)$", line)
            path = match.group(1) if match else "unknown"
            ext = path.rsplit(".", 1)[-1] if "." in path else "unknown"
            lang_map = {
                "py": "python", "js": "javascript", "ts": "typescript",
                "vue": "vue", "jsx": "javascript", "tsx": "typescript",
                "java": "java", "rb": "ruby", "go": "go", "rs": "rust",
                "css": "css", "html": "html", "sql": "sql",
            }
            current = {"path": path, "diff": "", "language": lang_map.get(ext, ext)}
            additions = 0
            deletions = 0
        elif current:
            current["diff"] += line + "\n"
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1

    if current:
        current["additions"] = additions
        current["deletions"] = deletions
        files.append(current)

    return files
