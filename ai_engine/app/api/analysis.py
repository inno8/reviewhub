"""
Manual analysis endpoints (for testing and direct API usage).
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.schemas import DiffAnalysisRequest, DiffAnalysisResponse, EvaluationResult
from app.services.llm_adapter import LLMAdapter


class UnderstandingRequest(BaseModel):
    category: str
    finding_titles: list[str]
    finding_descriptions: list[str]
    suggested_fixes: list[str]
    developer_explanation: str
    developer_level: str = "junior"


class UnderstandingResponse(BaseModel):
    level: str  # got_it / partial / not_yet
    feedback: str
    deeper_explanation: str = ""

router = APIRouter()


@router.post("/diff", response_model=DiffAnalysisResponse)
async def analyze_diff(request: DiffAnalysisRequest):
    """
    Analyze a code diff directly.
    
    Used for:
    - Testing the LLM evaluation
    - Manual/on-demand analysis
    - Integration from other tools
    """
    try:
        # Initialize LLM adapter (with optional user API key)
        llm_adapter = LLMAdapter(
            api_key=request.user_api_key
        )
        
        # Run evaluation
        result = await llm_adapter.evaluate_diff(
            diff=request.diff,
            file_path=request.file_path,
            language=request.language,
            context_files=request.context_files
        )
        
        return DiffAnalysisResponse(
            success=True,
            evaluation=result
        )
        
    except Exception as e:
        return DiffAnalysisResponse(
            success=False,
            error=str(e)
        )


@router.post("/test")
async def test_llm():
    """
    Test LLM connection with a simple example.
    """
    test_diff = '''
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,5 +1,8 @@
 def process_user(user_input):
-    eval(user_input)  # dangerous!
+    # Validate input first
+    if not isinstance(user_input, str):
+        raise ValueError("Input must be a string")
+    return user_input.strip()
'''
    
    try:
        llm_adapter = LLMAdapter()
        result = await llm_adapter.evaluate_diff(
            diff=test_diff,
            file_path="example.py",
            language="python"
        )
        
        return {
            "success": True,
            "llm_provider": llm_adapter.provider,
            "llm_model": llm_adapter.model_name,
            "result": result.model_dump() if result else None
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@router.post("/understand", response_model=UnderstandingResponse)
async def evaluate_understanding(request: UnderstandingRequest):
    """
    Fix & Learn: evaluate if a developer understands a code issue.
    Returns understanding level (got_it/partial/not_yet) with feedback.
    """
    try:
        llm_adapter = LLMAdapter()
        result = await llm_adapter.evaluate_understanding(
            category=request.category,
            finding_titles=request.finding_titles,
            finding_descriptions=request.finding_descriptions,
            suggested_fixes=request.suggested_fixes,
            developer_explanation=request.developer_explanation,
            developer_level=request.developer_level,
        )
        return result
    except Exception as e:
        return UnderstandingResponse(
            level="partial",
            feedback=f"Could not evaluate: {str(e)}",
            deeper_explanation="",
        )
