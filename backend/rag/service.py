"""RAG 对外服务入口。

该模块负责读取当前节点所在项目的 graph 快照，协调图关系检索、向量检索和
prompt 拼接，并返回 API 层需要的 RagContextResponse。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select

from database import SessionLocal
from models import EdgeORM, NodeORM
from schemas import RagContextRequest, RagContextResponse, RagDebugPayload

from rag.config import MAX_TOP_K
from rag.document_loader import _node_to_current_payload
from rag.prompts import build_inspiration_prompt
from rag.retrieval import _build_graph_context, _build_vector_context, _merge_context


def build_rag_context(request: RagContextRequest) -> RagContextResponse:
    """构建 Hybrid RAG 上下文预览；这里只返回 prompt，不调用 LLM。"""
    # 入参 request 来自 RAG API 请求体；返回当前节点、图关系上下文、向量上下文和 prompt。
    # 只读业务数据库；向量索引同步已前移到保存阶段，查询阶段不再全量 upsert。
    if request.agent_type != "inspiration":
        # 当前只开放 inspiration，避免前端误传未实现 agent 后得到不完整 prompt。
        raise HTTPException(status_code=400, detail="Only inspiration agent is supported in this PoC")

    # 限制 top_k，防止一次请求把过多节点注入 prompt，影响调试可读性和后续 LLM 成本。
    top_k = max(1, min(request.top_k, MAX_TOP_K))

    with SessionLocal() as session:
        current_node = session.get(NodeORM, request.node_id)

        if current_node is None:
            # 找不到当前节点时无法推断项目范围，因此直接返回 404。
            raise HTTPException(status_code=404, detail="Node not found")

        project_id = current_node.project_id
        nodes = session.scalars(
            select(NodeORM).where(NodeORM.project_id == project_id).order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()
        edges = session.scalars(
            select(EdgeORM).where(EdgeORM.project_id == project_id).order_by(EdgeORM.sort_order, EdgeORM.created_at)
        ).all()

    current_payload = _node_to_current_payload(current_node)
    # 用户没有输入问题时，用当前节点自身内容作为检索 query，保证预览仍有上下文。
    query_used = request.query.strip() or f"{current_node.title}\n{current_node.content}".strip()
    graph_context = _build_graph_context(current_node.id, nodes, edges)
    vector_context, vector_store, vector_error = _build_vector_context(project_id, current_node.id, nodes, query_used, top_k)
    merged_context = _merge_context(graph_context, vector_context)
    prompt = build_inspiration_prompt(current_payload, graph_context, vector_context, query_used)

    return RagContextResponse(
        current_node=current_payload,
        graph_context=graph_context,
        vector_context=vector_context,
        merged_context=merged_context,
        prompt=prompt,
        debug=RagDebugPayload(
            query_used=query_used,
            top_k=top_k,
            vector_store=vector_store,
            llm_called=False,
            vector_error=vector_error,
        ),
    )
