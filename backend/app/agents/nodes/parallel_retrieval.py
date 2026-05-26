"""并行向量检索节点。

复用 retrieval 模块的项目级检索能力, 跨 ChromaDB 三集合合并 top-k 命中。
当前节点存在时同时跑图关系检索, 与向量结果合并去重。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM
from app.indexing.config import MAX_TOP_K
from app.rag.retrieval import (
    _build_graph_context,
    _merge_context,
    build_project_vector_context,
)


DEFAULT_TOP_K = 5


def parallel_retrieval_node(state: AgentState) -> dict[str, Any]:
    """图关系上下文 + 向量上下文一次取齐, 写回合并视图供后续节点使用。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()
    current_node = state.get("current_node")

    if not project_id or not user_message:
        return {"graph_context": [], "vector_context": [], "merged_context": []}

    with SessionLocal() as db:
        nodes = list(
            db.scalars(
                select(NodeORM)
                .where(NodeORM.project_id == project_id)
                .order_by(NodeORM.sort_order, NodeORM.created_at)
            )
        )
        edges = list(
            db.scalars(
                select(EdgeORM)
                .where(EdgeORM.project_id == project_id)
                .order_by(EdgeORM.sort_order, EdgeORM.created_at)
            )
        )

    graph_context = []
    if current_node is not None:
        graph_context = _build_graph_context(current_node.id, nodes, edges)

    top_k = min(DEFAULT_TOP_K, MAX_TOP_K)
    vector_context, _, _ = build_project_vector_context(project_id, nodes, user_message, top_k + 1)
    if current_node is not None:
        vector_context = [item for item in vector_context if item.id != current_node.id]
    vector_context = vector_context[:top_k]

    merged = _merge_context(graph_context, vector_context)

    return {
        "graph_context": graph_context,
        "vector_context": vector_context,
        "merged_context": merged,
    }