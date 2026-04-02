"""
Manual analysis endpoints (for testing and direct API usage).
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import DiffAnalysisRequest, DiffAnalysisResponse, EvaluationResult
from app.services.llm_adapter import LLMAdapter

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
