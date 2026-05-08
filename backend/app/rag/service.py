"""RAG 对外服务入口。

通过 LangGraph StateGraph 执行 Agent 流程, 协调当前节点加载、图关系检索、
向量检索、上下文压缩与 LLM 调用, 对应 proposal 4.1.2 的非线性 Agent 执行。
项目级 Lore Memory 检索保持原状, 不进入 Agent 流程。
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select

from app.agents.graph import agent_graph
from app.agents.prompts.inspiration import build_inspiration_prompt
from app.agents.schemas import InspirationOutput, ResearchOutput, StructureOutput
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import NodeORM, ProjectORM
from app.indexing.config import MAX_TOP_K
from app.rag.retrieval import build_project_vector_context
from app.schemas import (
    MemorySearchItem,
    MemorySearchRequest,
    MemorySearchResponse,
    RagContextRequest,
    RagContextResponse,
    RagDebugPayload,
)
from app.services.graph_mappers import db_status_to_api, db_tags_to_api

logger = logging.getLogger(__name__)
def build_rag_context(request: RagContextRequest) -> RagContextResponse:
    """通过 LangGraph StateGraph 执行 Agent 流程。

    Args:
        request: RAG API 请求体。

    Returns:
        当前节点、图关系上下文、向量上下文、合并上下文、prompt、Agent 输出与调试信息。

    Raises:
        HTTPException: 当 agent_type 未知或当前节点不存在时抛出。
    """
    if request.agent_type not in ("inspiration", "research", "structure"):
        raise HTTPException(
            status_code=400,
            detail=f"未知 agent_type: {request.agent_type}",
        )

    # 限制 top_k, 防止一次请求把过多节点注入 prompt, 影响调试可读性和 LLM 成本。
    top_k = max(1, min(request.top_k, MAX_TOP_K))

    initial_state: AgentState = {
        "node_id": request.node_id,
        "node_ids": request.node_ids,
        "user_query": request.query,
        "agent_type": request.agent_type,
        "top_k": top_k,
    }

    final_state = agent_graph.invoke(initial_state)

    if final_state.get("current_node") is None:
        # 加载阶段失败 (节点不存在 / 缺少 ID), 直接 404
        raise HTTPException(
            status_code=404,
            detail=final_state.get("error") or "当前节点不存在",
        )

    return _build_rag_response(request, final_state)


def _build_rag_response(request: RagContextRequest, state: AgentState) -> RagContextResponse:
    """把 LangGraph 终态映射到既有 RagContextResponse 形态。

    保留原响应字段, 前端 RAG 调试面板无需改动;
    Agent 结构化输出序列化为 JSON 字符串放入 answer, 与重构前行为一致。
    """
    current = state["current_node"]
    grouped_vector = state.get("vector_context") or {}
    top_k = state.get("top_k", request.top_k)

    flat_vector = sorted(
        (item for items in grouped_vector.values() for item in items),
        key=lambda item: item.score,
        reverse=True,
    )[:top_k]

    query_used = (request.query or f"{current.title}\n{current.content}").strip()
    prompt = build_inspiration_prompt(
        current,
        state.get("graph_context", []),
        grouped_vector,
        query_used,
        top_k=top_k,
    )

    final_output = state.get("final_output")
    error = state.get("error")

    return RagContextResponse(
        current_node=current,
        graph_context=state.get("graph_context", []),
        vector_context=flat_vector,
        merged_context=state.get("merged_context", []),
        prompt=prompt,
        inspiration_output=final_output if isinstance(final_output, InspirationOutput) else None,
        research_output=final_output if isinstance(final_output, ResearchOutput) else None,
        structure_output=final_output if isinstance(final_output, StructureOutput) else None,
        debug=RagDebugPayload(
            query_used=query_used,
            top_k=top_k,
            vector_store="chroma" if grouped_vector else "chroma_unavailable",
            llm_called=final_output is not None,
            vector_error=error if final_output is None else None,
        ),
    )


def search_project_memory(project_id: str, request: MemorySearchRequest) -> MemorySearchResponse:
    """搜索当前项目的 Lore Memory。

    该函数只做项目内向量检索并返回记忆卡片，不构造 prompt，也不调用 LLM。

    Args:
        project_id: 当前项目 ID。
        request: 项目级搜索条件。

    Returns:
        当前项目内语义相关的记忆条目和调试状态。

    Raises:
        HTTPException: 当项目不存在时抛出。
    """
    top_k = max(1, min(request.top_k, MAX_TOP_K))
    query_used = request.query.strip()

    with SessionLocal() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        nodes = session.scalars(
            select(NodeORM).where(NodeORM.project_id == project_id).order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()

    vector_context, vector_store, vector_error = build_project_vector_context(
        project_id,
        nodes,
        query_used,
        top_k,
        request.node_type,
    )
    node_by_id = {node.id: node for node in nodes}
    items: list[MemorySearchItem] = []

    for item in vector_context:
        node = node_by_id.get(item.id)

        if node is None:
            continue

        items.append(
            MemorySearchItem(
                id=node.id,
                type=node.node_type,
                title=node.title,
                content=node.content,
                tags=db_tags_to_api(node.meta),
                status=db_status_to_api(node.meta),
                score=item.score,
            )
        )

    return MemorySearchResponse(
        items=items,
        debug=RagDebugPayload(
            query_used=query_used,
            top_k=top_k,
            vector_store=vector_store,
            llm_called=False,
            vector_error=vector_error,
        ),
    )
