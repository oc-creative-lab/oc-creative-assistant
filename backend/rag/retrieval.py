"""RAG 检索与上下文合并。

该模块负责从画布 graph 中抽取一跳关系上下文，并通过 Chroma 或内存相似度
寻找语义相关节点，最后合并去重成前端和 prompt 可使用的上下文列表。
"""

from __future__ import annotations

from models import EdgeORM, NodeORM
from schemas import RagGraphContextItem, RagMergedContextItem, RagVectorContextItem

from rag.config import DEFAULT_RELATION_LABEL, DEFAULT_RELATION_TYPE
from rag.document_loader import _node_to_document, _node_to_vector_item
from rag.vector_store import embedding_provider, get_chroma_collection, query_collection


def _build_graph_context(
    node_id: str,
    nodes: list[NodeORM],
    edges: list[EdgeORM],
) -> list[RagGraphContextItem]:
    """画布连线是用户显式建立的创作关系，因此一跳图关系上下文优先级更高。"""
    # 入参 nodes/edges 是当前项目完整 graph 快照；函数只在内存中组装上下文。
    node_by_id = {node.id: node for node in nodes}
    context: list[RagGraphContextItem] = []

    for edge in edges:
        if edge.source == node_id:
            # 当前节点是 source，邻居是这条边指向的下游节点。
            neighbor = node_by_id.get(edge.target)
            direction = "outgoing"
        elif edge.target == node_id:
            # 当前节点是 target，邻居是指向它的上游节点。
            neighbor = node_by_id.get(edge.source)
            direction = "incoming"
        else:
            continue

        if neighbor is None:
            # 理论上保存层已校验端点；这里兜底跳过脏数据，避免 RAG 接口整体失败。
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
    """向量检索用于发现尚未连线但语义相关的节点；没有外部 API key 也能使用占位 embedding。"""
    # 返回值包含：相似节点列表、实际使用的向量库标识、可选错误信息。
    if len(nodes) <= 1:
        # 只有当前节点时没有可推荐对象，直接返回空上下文。
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
    """使用本地 Chroma 做持久化向量检索；只查询，不在 RAG 请求阶段写索引。"""
    collection = get_chroma_collection()

    result_ids, metadatas, distances = query_collection(collection, project_id, query, top_k, len(nodes))
    node_by_id = {node.id: node for node in nodes}
    context: list[RagVectorContextItem] = []

    for _chroma_id, metadata, distance in zip(result_ids, metadatas, distances, strict=False):
        # Chroma id 是 project_id:node_id，但 API 返回必须保持原始 node.id，因此从 metadata 映射。
        node_id = metadata.get("node_id") if isinstance(metadata, dict) else None

        if not isinstance(node_id, str):
            continue

        if node_id == current_node_id:
            # 当前节点本身通常最相似，但注入 prompt 没有增量信息，所以跳过。
            continue

        node = node_by_id.get(node_id)

        if node is None:
            # Chroma 中可能残留旧 id；以当前数据库快照为准。
            continue

        # Chroma cosine distance 越小越相似，这里转换为前端更直观的 0-1 score。
        context.append(_node_to_vector_item(node, score=max(0.0, 1.0 - float(distance))))

        if len(context) >= top_k:
            break

    return context, "chroma", None


def _query_in_memory_context(
    current_node_id: str,
    nodes: list[NodeORM],
    query: str,
    top_k: int,
) -> list[RagVectorContextItem]:
    """Chroma 不可用时的内存检索兜底；不写磁盘，只返回本次计算结果。"""
    query_embedding = embedding_provider.embed(query)
    scored_nodes: list[tuple[float, NodeORM]] = []

    for node in nodes:
        if node.id == current_node_id:
            # 当前节点不作为自己的相似上下文，避免 prompt 中重复当前内容。
            continue

        node_embedding = embedding_provider.embed(_node_to_document(node))
        scored_nodes.append((_cosine_similarity(query_embedding, node_embedding), node))

    # 按相似度降序取 top_k，让 prompt 优先看到最相关节点。
    scored_nodes.sort(key=lambda item: item[0], reverse=True)
    return [_node_to_vector_item(node, score=score) for score, node in scored_nodes[:top_k]]


def _merge_context(
    graph_context: list[RagGraphContextItem],
    vector_context: list[RagVectorContextItem],
) -> list[RagMergedContextItem]:
    """同一节点可能同时来自图关系和向量检索，需要去重，避免重复注入 prompt。"""
    # 返回顺序保留 graph 优先，再追加 vector；这体现用户手动连线的优先级。
    merged: dict[str, RagMergedContextItem] = {}

    for item in graph_context:
        # 图关系来自用户显式连线，先写入 merged，后续向量命中同节点时只升级来源。
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
            # 同时被图关系和向量检索命中时标记 both，前端可据此展示更高可信度。
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
    """计算两个已归一化向量的余弦相似度；空向量返回 0。"""
    if not left or not right:
        return 0.0

    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
