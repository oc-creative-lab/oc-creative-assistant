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
    build_graph_context,
    build_project_vector_context,
    merge_context,
)


DEFAULT_TOP_K = 5


def parallel_retrieval_node(state: AgentState) -> dict[str, Any]:
    """图关系上下文 + 向量上下文一次取齐, 写回合并视图供后续节点使用。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()
    current_nodes = state.get("current_nodes") or []

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

    graph_context: list = []
    seen_ids: set[str] = set()
    for current_node in current_nodes:
        for item in build_graph_context(current_node.id, nodes, edges):
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                graph_context.append(item)
    top_k = min(DEFAULT_TOP_K, MAX_TOP_K)
    vector_context, _, _ = build_project_vector_context(
        project_id, nodes, user_message, top_k + len(current_nodes)
    )
    current_node_ids = {n.id for n in current_nodes}
    vector_context = [item for item in vector_context if item.id not in current_node_ids]
    vector_context = vector_context[:top_k]

    merged = merge_context(graph_context, vector_context)

    return {
        "graph_context": graph_context,
        "vector_context": vector_context,
        "merged_context": merged,
    }