"""Inspiration Agent prompt 适配。

LangGraph 节点持有按 node_type 分组的向量上下文 (dict[str, list]), 这里
打平后喂给现有 RAG prompt 模板, 避免在两个地方重复维护文案。
"""

from __future__ import annotations

from app.rag.prompts import build_inspiration_prompt as _build_legacy_prompt
from app.schemas import (
    RagCurrentNodePayload,
    RagGraphContextItem,
    RagVectorContextItem,
)


def build_inspiration_prompt(
    current_node: RagCurrentNodePayload,
    graph_context: list[RagGraphContextItem],
    vector_context: dict[str, list[RagVectorContextItem]],
    user_query: str,
    top_k: int = 5,
) -> str:
    """适配 dict 形式的 vector_context 到既有 prompt 模板。

    Args:
        current_node: 当前节点 DTO。
        graph_context: 一跳图关系上下文。
        vector_context: 按 node_type 分组的向量上下文。
        user_query: 用户输入或兜底 query。
        top_k: 打平后保留的最大向量条数, 控制 prompt 长度。

    Returns:
        给 LLM 使用的 prompt 文本。
    """
    flat_vector = sorted(
        (item for items in vector_context.values() for item in items),
        key=lambda item: item.score,
        reverse=True,
    )[:top_k]

    return _build_legacy_prompt(current_node, graph_context, flat_vector, user_query)