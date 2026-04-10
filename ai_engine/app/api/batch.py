"""
Batch Processing API - Phase 6
Handles repository analysis for building developer profiles.
"""
import os
import asyncio
import subprocess
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx

from app.core.config import settings
from app.services.diff_extractor import DiffExtractor
from app.services.llm_adapter import LLMAdapter
from app.services.django_client import DjangoClient

router = APIRouter()

# In-memory job tracking (for simplicity; use Redis in production)
active_jobs: dict = {}


class BatchStartRequest(BaseModel):
    job_id: int
    repo_url: str
    branch: str = "main"
    target_email: Optional[str] = None
    max_commits: int = 500
    since_date: Optional[str] = None
    project_id: Optional[int] = None


class BatchCancelRequest(BaseModel):
    job_id: int


async def update_job_status(job_id: int, status: str, **kwargs):
    """Update job status in Django backend."""
    try:
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"{settings.BACKEND_API_URL}/batch/jobs/{job_id}/internal/",
                json={"status": status, **kwargs},
                timeout=10
            )
    except Exception as e:
        print(f"Failed to update job {job_id}: {e}")


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
        
        if repo_path.exists():
            # Fetch latest
            result = subprocess.run(
                ["git", "fetch", "--all"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
        else:
            # Clone
            result = subprocess.run(
                ["git", "clone", request.repo_url, str(repo_path)],
                capture_output=True,
                text=True
            )
        
        if result.returncode != 0:
            raise Exception(f"Git error: {result.stderr}")
        
        # Checkout branch
        subprocess.run(
            ["git", "checkout", request.branch],
            cwd=repo_path,
            capture_output=True
        )
        
        # Check if cancelled
        if active_jobs.get(job_id, {}).get("cancelled"):
            await update_job_status(job_id, "cancelled")
            return
        
        # Step 2: Get commit history
        await update_job_status(job_id, "analyzing")
        
        git_log_cmd = [
            "git", "log",
            f"--max-count={request.max_commits}",
            "--format=%H|%an|%ae|%ad|%s",
            "--date=iso"
        ]
        
        if request.target_email:
            git_log_cmd.extend(["--author", request.target_email])
        
        if request.since_date:
            git_log_cmd.extend(["--since", request.since_date])
        
        result = subprocess.run(
            git_log_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 4)
            if len(parts) == 5:
                commits.append({
                    "sha": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "date": parts[3],
                    "message": parts[4]
                })
        
        total_commits = len(commits)
        await update_job_status(job_id, "analyzing", total_commits=total_commits)
        
        # Step 3: Analyze each commit with LLM
        processed = 0
        skipped = 0
        findings_count = 0
        skills_detected = set()
        patterns_detected = set()

        diff_extractor = DiffExtractor()
        llm_adapter = LLMAdapter()
        django_client = DjangoClient()

        for commit in commits:
            # Check if cancelled
            if active_jobs.get(job_id, {}).get("cancelled"):
                await update_job_status(job_id, "cancelled")
                return

            start_time = time.time()

            try:
                # Extract diff using DiffExtractor (reuses cached bare repo)
                diff_data = await diff_extractor.extract_commit_diff(
                    repo_url=request.repo_url,
                    commit_sha=commit["sha"]
                )

                if not diff_data or not diff_data.get("files"):
                    skipped += 1
                    processed += 1
                    continue

                # Analyze each changed file with LLM
                all_findings = []
                total_score = 0
                file_count = 0
                total_tokens = 0

                for file_diff in diff_data["files"]:
                    result = await llm_adapter.evaluate_diff(
                        diff=file_diff["diff"],
                        file_path=file_diff["path"],
                        language=file_diff.get("language", "unknown")
                    )

                    if result:
                        all_findings.extend(result.findings)
                        total_score += result.overall_score
                        total_tokens += result.tokens_used
                        file_count += 1

                overall_score = total_score / file_count if file_count > 0 else 100
                processing_ms = int((time.time() - start_time) * 1000)

                # Create evaluation in Django (triggers SkillMetric updates)
                if request.project_id:
                    eval_result = await django_client.create_evaluation({
                        "project_id": request.project_id,
                        "commit_sha": commit["sha"],
                        "commit_message": commit["message"],
                        "commit_timestamp": commit["date"],
                        "branch": request.branch,
                        "author_name": commit["author_name"],
                        "author_email": commit["author_email"],
                        "files_changed": len(diff_data["files"]),
                        "lines_added": diff_data.get("lines_added", 0),
                        "lines_removed": diff_data.get("lines_removed", 0),
                        "overall_score": overall_score,
                        "llm_model": llm_adapter.model_name,
                        "llm_tokens_used": total_tokens,
                        "processing_ms": processing_ms,
                        "findings": [f.model_dump() for f in all_findings],
                        "batch_job_id": job_id,
                    })

                    if eval_result:
                        findings_count += len(all_findings)
                        for f in all_findings:
                            for skill in f.skills_affected:
                                skills_detected.add(skill)

                print(f"[BATCH {job_id}] Commit {commit['sha'][:7]}: {len(all_findings)} findings, score {overall_score:.1f}")

            except Exception as e:
                print(f"[BATCH {job_id}] Error on commit {commit['sha'][:7]}: {e}")
                skipped += 1

            processed += 1

            # Report progress every 5 commits
            if processed % 5 == 0 or processed == total_commits:
                await update_job_status(
                    job_id, "analyzing",
                    processed_commits=processed,
                    skipped_commits=skipped,
                    findings_count=findings_count,
                )

            # Yield control to event loop
            await asyncio.sleep(0.01)

        # Step 4: Build developer profile
        await update_job_status(job_id, "building_profile", processed_commits=processed)

        # Mark complete — Django will build the profile on status change
        await update_job_status(
            job_id, "completed",
            processed_commits=processed,
            skipped_commits=skipped,
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
