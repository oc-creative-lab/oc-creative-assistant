from fastapi import APIRouter

from rag_service import build_rag_context
from schemas import RagContextRequest, RagContextResponse


# RAG API 只做上下文预览，方便前端调试“AI 将看到什么”，不触发真实 LLM。
router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/context", response_model=RagContextResponse)
async def read_rag_context(payload: RagContextRequest) -> RagContextResponse:
    """构建当前节点的 Hybrid RAG 上下文和 Inspiration Agent prompt。"""
    # payload 来自请求体；服务层负责校验 agent_type、节点是否存在以及检索降级。
    # 响应中的 prompt/debug 主要给前端预览和调试，不代表已经调用真实 LLM。
    return build_rag_context(payload)
