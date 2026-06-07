"""RAG HTTP routes.

The current RAG API only does context preview, making it easy for the frontend
to debug the input the Agent will see, without triggering a real LLM.
"""

from fastapi import APIRouter

from app.schemas import RagContextRequest, RagContextResponse
from app.services.rag_service import build_rag_context


router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/context", response_model=RagContextResponse)
async def read_rag_context(payload: RagContextRequest) -> RagContextResponse:
    """Build the Hybrid RAG context and Inspiration Agent prompt for the current node."""
    return build_rag_context(payload)
