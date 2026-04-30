"""RAG 检索与上下文合并。

本模块负责从画布 graph 中抽取一跳关系上下文，并通过向量索引寻找语义相关节点，
最后合并去重成前端和 prompt 可使用的上下文列表。
"""

from __future__ import annotations

from app.db.models import EdgeORM, NodeORM
from app.indexing.config import DEFAULT_RELATION_LABEL, DEFAULT_RELATION_TYPE
from app.indexing.document_loader import node_to_document, node_to_vector_item
from app.indexing.vector_store import embedding_provider, get_chroma_collection, query_collection
from app.schemas import RagGraphContextItem, RagMergedContextItem, RagVectorContextItem


def _build_graph_context(
    node_id: str,
    nodes: list[NodeORM],
    edges: list[EdgeORM],
) -> list[RagGraphContextItem]:
    """构建一跳图关系上下文。

    画布连线是用户显式建立的创作关系，因此优先级高于语义相似度。

    Args:
        node_id: 当前节点 ID。
        nodes: 当前项目完整节点快照。
        edges: 当前项目完整边快照。

    Returns:
        与当前节点直接相连的图关系上下文。
    """
    node_by_id = {node.id: node for node in nodes}
    context: list[RagGraphContextItem] = []

    for edge in edges:
        if edge.source == node_id:
            neighbor = node_by_id.get(edge.target)
            direction = "outgoing"
        elif edge.target == node_id:
            neighbor = node_by_id.get(edge.source)
            direction = "incoming"
        else:
            continue

        if neighbor is None:
            # 保存层已校验端点；这里兜底跳过脏数据，避免 RAG 接口整体失败。
            continue

        context.append(
            RagGraphContextItem(
                id=neighbor.id,
                type=neighbor.node_type,
                title=neighbor.title,
                content=neighbor.content,
                relation_label=edge.label or DEFAULT_RELATION_LABEL,
                relation_type=edge.relation_type or DEFAULT_RELATION_TYPE,
                direction=direction,
            )
        )

    return context


def _build_vector_context(
    project_id: str,
    current_node_id: str,
    nodes: list[NodeORM],
    query: str,
    top_k: int,
) -> tuple[list[RagVectorContextItem], str, str | None]:
    """构建向量检索上下文。

    Args:
        project_id: 当前项目 ID。
        current_node_id: 当前节点 ID，用于排除自身。
        nodes: 当前项目完整节点快照。
        query: 检索问题。
        top_k: 最多返回的向量上下文数量。

    Returns:
        相似节点列表、实际使用的向量库标识和可选错误信息。
    """
    if len(nodes) <= 1:
        return [], "hash_placeholder", None

    try:
        return _query_chroma_context(project_id, current_node_id, nodes, query, top_k)
    except Exception as error:  # noqa: BLE001
        # ChromaDB 不可用时降级到内存相似度，保证图关系上下文和 prompt 仍能调试。
        fallback_context = _query_in_memory_context(current_node_id, nodes, query, top_k)
        return fallback_context, "hash_memory_fallback", str(error)


def _query_chroma_context(
    project_id: str,
    current_node_id: str,
    nodes: list[NodeORM],
    query: str,
    top_k: int,
) -> tuple[list[RagVectorContextItem], str, str | None]:
    """使用本地 ChromaDB 做持久化向量检索。

    RAG 请求阶段只查询，不写索引；索引写入由保存 graph 后的 `app.indexing.sync` 负责。
    """
    collection = get_chroma_collection()
    result_ids, metadatas, distances = query_collection(collection, project_id, query, top_k, len(nodes))
    node_by_id = {node.id: node for node in nodes}
    context: list[RagVectorContextItem] = []

    for _chroma_id, metadata, distance in zip(result_ids, metadatas, distances, strict=False):
        node_id = metadata.get("node_id") if isinstance(metadata, dict) else None

        if not isinstance(node_id, str):
            continue

        if node_id == current_node_id:
            # 当前节点本身通常最相似，但注入 prompt 没有增量信息，所以跳过。
            continue

        node = node_by_id.get(node_id)

        if node is None:
            # ChromaDB 中可能残留旧 id；RAG 响应以当前数据库快照为准。
            continue

        # ChromaDB cosine distance 越小越相似，这里转换为前端更直观的 0-1 score。
        context.append(node_to_vector_item(node, score=max(0.0, 1.0 - float(distance))))

        if len(context) >= top_k:
            break

    return context, "chroma", None


def _query_in_memory_context(
    current_node_id: str,
    nodes: list[NodeORM],
    query: str,
    top_k: int,
) -> list[RagVectorContextItem]:
    """在 ChromaDB 不可用时执行内存相似度兜底检索。"""
    query_embedding = embedding_provider.embed(query)
    scored_nodes: list[tuple[float, NodeORM]] = []

    for node in nodes:
        if node.id == current_node_id:
            continue

        node_embedding = embedding_provider.embed(node_to_document(node))
        scored_nodes.append((_cosine_similarity(query_embedding, node_embedding), node))

    scored_nodes.sort(key=lambda item: item[0], reverse=True)
    return [node_to_vector_item(node, score=score) for score, node in scored_nodes[:top_k]]


def _merge_context(
    graph_context: list[RagGraphContextItem],
    vector_context: list[RagVectorContextItem],
) -> list[RagMergedContextItem]:
    """合并图关系上下文和向量上下文。

    同一节点可能同时来自图关系和向量检索，需要去重，避免重复注入 prompt。
    """
    merged: dict[str, RagMergedContextItem] = {}

    for item in graph_context:
        merged[item.id] = RagMergedContextItem(
            id=item.id,
            source="graph",
            type=item.type,
            title=item.title,
            content=item.content,
        )

    for item in vector_context:
        if item.id in merged:
            existing_item = merged[item.id]
            merged[item.id] = RagMergedContextItem(
                id=existing_item.id,
                source="both",
                type=existing_item.type,
                title=existing_item.title,
                content=existing_item.content,
            )
            continue

        merged[item.id] = RagMergedContextItem(
            id=item.id,
            source="vector",
            type=item.type,
            title=item.title,
            content=item.content,
        )

    return list(merged.values())


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个已归一化向量的余弦相似度。"""
    if not left or not right:
        return 0.0

    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
