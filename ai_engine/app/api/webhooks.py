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
from app.core.config import settings

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
    
    # Queue background processing for each commit
    for commit in event.commits:
        background_tasks.add_task(
            process_commit,
            project_id=project_id,
            commit=commit.model_dump(),
            repo_url=event.repository.html_url,
            branch=branch,
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
):
    """
    Background task to process a single commit.
    
    1. Extract diff
    2. Analyze with LLM
    3. Store results in Django
    """
    import time
    from datetime import datetime
    
    start_time = time.time()
    
    try:
        # Initialize services
        diff_extractor = DiffExtractor()
        llm_adapter = LLMAdapter()
        django_client = DjangoClient()
        
        # Extract diff for commit
        diff_data = await diff_extractor.extract_commit_diff(
            repo_url=repo_url,
            commit_sha=commit["id"]
        )
        
        if not diff_data or not diff_data.get("files"):
            print(f"No diff data for commit {commit['id'][:7]}")
            return
        
        # Analyze each changed file
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
        
        # Calculate overall score
        overall_score = total_score / file_count if file_count > 0 else 100
        
        processing_ms = int((time.time() - start_time) * 1000)
        
        # Store in Django
        await django_client.create_evaluation({
            "project_id": project_id,
            "commit_sha": commit["id"],
            "commit_message": commit["message"],
            "commit_timestamp": commit.get("timestamp"),
            "branch": branch,
            "author_name": commit["author"].get("name", "Unknown"),
            "author_email": commit["author"].get("email", "unknown@example.com"),
            "files_changed": len(diff_data["files"]),
            "lines_added": diff_data.get("lines_added", 0),
            "lines_removed": diff_data.get("lines_removed", 0),
            "overall_score": overall_score,
            "llm_model": llm_adapter.model_name,
            "llm_tokens_used": total_tokens,
            "processing_ms": processing_ms,
            "findings": [f.model_dump() for f in all_findings]
        })
        
        print(f"✅ Processed commit {commit['id'][:7]}: {len(all_findings)} findings, score {overall_score:.1f}")
        
    except Exception as e:
        print(f"❌ Error processing commit {commit['id'][:7]}: {str(e)}")
        # TODO: Store error in Django


@router.post("/gitlab/{project_id}", response_model=WebhookResponse)
async def gitlab_webhook(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    x_gitlab_token: Optional[str] = Header(None),
):
    """Handle GitLab push webhook."""
    # TODO: Implement GitLab webhook
    return WebhookResponse(
        success=False,
        message="GitLab webhook not yet implemented",
        commits_processed=0
    )


@router.post("/bitbucket/{project_id}", response_model=WebhookResponse)
async def bitbucket_webhook(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handle Bitbucket push webhook."""
    # TODO: Implement Bitbucket webhook
    return WebhookResponse(
        success=False,
        message="Bitbucket webhook not yet implemented",
        commits_processed=0
    )
