"""RAG 文档抽取与 DTO 转换。

当前数据源来自画布节点：这里负责把 ORM 节点整理成可检索文本，
并把节点转换为 RAG 响应中需要的轻量 DTO。
"""

from __future__ import annotations

from typing import Any

from models import NodeORM
from schemas import RagCurrentNodePayload, RagVectorContextItem


def _node_to_current_payload(node: NodeORM) -> RagCurrentNodePayload:
    """ORM node -> 当前节点 RAG DTO；只暴露 prompt 需要的字段。"""
    return RagCurrentNodePayload(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=node.content,
        tags=_db_tags_to_api(node.meta),
    )


def _node_to_vector_item(node: NodeORM, score: float) -> RagVectorContextItem:
    """ORM node -> 向量检索结果 DTO；score 会四舍五入便于前端展示。"""
    return RagVectorContextItem(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=node.content,
        score=round(score, 4),
    )


def _node_to_document(node: NodeORM) -> str:
    """把节点拼成可检索文档；标题、类型、标签和正文共同参与 embedding。"""
    tags = ", ".join(_db_tags_to_api(node.meta))
    return f"""Title: {node.title}
Type: {node.node_type}
Tags: {tags}
Content:
{node.content}"""


def _db_tags_to_api(meta: Any) -> list[str]:
    """从节点 meta JSON 中读取 tags；兼容旧数据和异常类型。"""
    if isinstance(meta, dict):
        tags = meta.get("tags", [])
        # 过滤非字符串标签，避免检索文档中混入不可预期类型。
        return [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    return []
