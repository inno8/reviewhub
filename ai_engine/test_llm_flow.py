"""
Test the LLM evaluation flow with a mock diff.
This bypasses GitHub webhook and diff extraction.
"""
import asyncio
from app.services.llm_adapter import LLMAdapter
from app.services.django_client import DjangoClient


SAMPLE_DIFF = """
@@ -10,7 +10,7 @@ def login(request):
     if request.method == 'POST':
         username = request.POST.get('username')
-        password = request.POST.get('password')
+        password = request.POST['password']
         user = authenticate(username=username, password=password)
         if user:
             login(user)
"""


async def test_llm_evaluation():
    """Test LLM evaluation with a sample diff."""
    print("[TEST] Testing LLM evaluation flow...\n")
    
    # Initialize adapter
    adapter = LLMAdapter()
    print(f"[OK] LLM Adapter initialized: {adapter.provider} / {adapter.model_name}\n")
    
    # Evaluate diff
    print("[->] Sending diff to LLM...")
    result = await adapter.evaluate_diff(
        diff=SAMPLE_DIFF,
        file_path="app/views.py",
        language="python"
    )
    
    if result:
        print("[OK] LLM evaluation complete!\n")
        print(f"Overall Score: {result.overall_score}/100")
        print(f"Findings: {len(result.findings)}")
        print(f"Skill Scores: {len(result.skill_scores)}")
        print(f"Tokens Used: {result.tokens_used}")
        print(f"Processing Time: {result.processing_ms}ms\n")
        
        if result.findings:
            print("[FINDINGS] List:")
            for i, finding in enumerate(result.findings[:3], 1):
                print(f"\n{i}. {finding.title}")
                print(f"   Severity: {finding.severity}")
                print(f"   Skills: {', '.join(finding.skills_affected)}")
                print(f"   Description: {finding.description[:100]}...")
        
        # Store in backend
        print("\n[->] Storing evaluation in backend...")
        django_client = DjangoClient()
        stored = await django_client.create_evaluation({
            "project_id": 1,
            "commit_sha": "test123abc",
            "commit_message": "Test commit",
            "commit_timestamp": "2026-03-27T10:00:00Z",
            "branch": "test",
            "author_name": "Test User",
            "author_email": "test@example.com",
            "files_changed": 1,
            "lines_added": 1,
            "lines_removed": 1,
            "overall_score": result.overall_score,
            "llm_model": result.llm_model,
            "llm_tokens_used": result.tokens_used,
            "processing_ms": result.processing_ms,
            "findings": [f.model_dump() for f in result.findings]
        })
        
        if stored:
            print(f"[OK] Evaluation stored! Review ID: {stored['id']}")
        else:
            print("[ERROR] Failed to store evaluation")
    
    else:
        print("[ERROR] LLM evaluation failed")


if __name__ == "__main__":
    asyncio.run(test_llm_evaluation())
