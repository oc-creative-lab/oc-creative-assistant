from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from database import SessionLocal
from models import EdgeORM, NodeORM
from schemas import (
    RagContextRequest,
    RagContextResponse,
    RagCurrentNodePayload,
    RagDebugPayload,
    RagGraphContextItem,
    RagMergedContextItem,
    RagVectorContextItem,
)


CHROMA_PATH = Path(__file__).resolve().parent / "data" / "chroma"
CHROMA_COLLECTION_NAME = "oc_lore_nodes"
DEFAULT_RELATION_LABEL = "关联"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"
EMBEDDING_DIMENSION = 64


class HashEmbeddingProvider:
    """PoC 占位 embedding，后续可替换为 OpenAI / DeepSeek / BGE 等真实语义向量。"""

    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))

        if norm == 0:
            return vector

        return [value / norm for value in vector]

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        words = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        char_bigrams = [text[index : index + 2] for index in range(max(len(text) - 1, 0))]
        return words + chinese_chars + char_bigrams


embedding_provider = HashEmbeddingProvider()


def build_rag_context(request: RagContextRequest) -> RagContextResponse:
    """构建 Hybrid RAG 上下文预览；这里只返回 prompt，不调用 LLM。"""
    if request.agent_type != "inspiration":
        raise HTTPException(status_code=400, detail="Only inspiration agent is supported in this PoC")

    top_k = max(1, min(request.top_k, 20))

    with SessionLocal() as session:
        current_node = session.get(NodeORM, request.node_id)

        if current_node is None:
            raise HTTPException(status_code=404, detail="Node not found")

        project_id = current_node.project_id
        nodes = session.scalars(
            select(NodeORM).where(NodeORM.project_id == project_id).order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()
        edges = session.scalars(
            select(EdgeORM).where(EdgeORM.project_id == project_id).order_by(EdgeORM.sort_order, EdgeORM.created_at)
        ).all()

    current_payload = _node_to_current_payload(current_node)
    query_used = request.query.strip() or f"{current_node.title}\n{current_node.content}".strip()
    graph_context = _build_graph_context(current_node.id, nodes, edges)
    vector_context, vector_store, vector_error = _build_vector_context(current_node.id, nodes, query_used, top_k)
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


def _build_graph_context(
    node_id: str,
    nodes: list[NodeORM],
    edges: list[EdgeORM],
) -> list[RagGraphContextItem]:
    """画布连线是用户显式建立的创作关系，因此一跳图关系上下文优先级更高。"""
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
    current_node_id: str,
    nodes: list[NodeORM],
    query: str,
    top_k: int,
) -> tuple[list[RagVectorContextItem], str, str | None]:
    """向量检索用于发现尚未连线但语义相关的节点；没有外部 API key 也能使用占位 embedding。"""
    if len(nodes) <= 1:
        return [], "hash_placeholder", None

    try:
        return _query_chroma_context(current_node_id, nodes, query, top_k)
    except Exception as error:  # noqa: BLE001
        # ChromaDB 不可用时降级到内存相似度，保证图关系上下文和 prompt 仍能调试。
        fallback_context = _query_in_memory_context(current_node_id, nodes, query, top_k)
        return fallback_context, "hash_memory_fallback", str(error)


def _query_chroma_context(
    current_node_id: str,
    nodes: list[NodeORM],
    query: str,
    top_k: int,
) -> tuple[list[RagVectorContextItem], str, str | None]:
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("ChromaDB 未安装，已使用本地 hash embedding 降级检索。") from error

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    documents = [_node_to_document(node) for node in nodes]
    ids = [node.id for node in nodes]
    embeddings = [embedding_provider.embed(document) for document in documents]
    metadatas = [
        {
            "node_id": node.id,
            "node_type": node.node_type,
            "title": node.title,
        }
        for node in nodes
    ]

    # PoC 阶段节点数量很少，每次请求前 upsert 全量节点，后续可替换为增量索引。
    collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    result = collection.query(
        query_embeddings=[embedding_provider.embed(query)],
        n_results=min(top_k + 1, len(nodes)),
        include=["metadatas", "distances"],
    )
    result_ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]
    node_by_id = {node.id: node for node in nodes}
    context: list[RagVectorContextItem] = []

    for node_id, distance in zip(result_ids, distances, strict=False):
        if node_id == current_node_id:
            continue

        node = node_by_id.get(node_id)

        if node is None:
            continue

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
    query_embedding = embedding_provider.embed(query)
    scored_nodes: list[tuple[float, NodeORM]] = []

    for node in nodes:
        if node.id == current_node_id:
            continue

        node_embedding = embedding_provider.embed(_node_to_document(node))
        scored_nodes.append((_cosine_similarity(query_embedding, node_embedding), node))

    scored_nodes.sort(key=lambda item: item[0], reverse=True)
    return [_node_to_vector_item(node, score=score) for score, node in scored_nodes[:top_k]]


def _merge_context(
    graph_context: list[RagGraphContextItem],
    vector_context: list[RagVectorContextItem],
) -> list[RagMergedContextItem]:
    """同一节点可能同时来自图关系和向量检索，需要去重，避免重复注入 prompt。"""
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


def build_inspiration_prompt(
    current_node: RagCurrentNodePayload,
    graph_context: list[RagGraphContextItem],
    vector_context: list[RagVectorContextItem],
    user_query: str,
) -> str:
    """这里只构造 prompt，不调用 LLM，方便调试 AI 实际能看到的上下文。"""
    graph_context_text = _format_graph_context(graph_context)
    vector_context_text = _format_vector_context(vector_context)

    return f"""你是 OC Creative Assistant 中的「灵感引导 Agent」。

你的任务是辅助原创角色创作者进行思考，而不是替用户写正文。

你只能输出：
1. 引导性问题；
2. 设定补充建议；
3. 可能需要创建的新节点；
4. 与已有设定的潜在冲突提醒。

你不能输出：
1. 完整小说段落；
2. 完整剧情正文；
3. 替用户决定最终设定；
4. 直接续写用户作品。

请严格基于下面提供的项目上下文回答。

---

【当前节点】

节点类型：{current_node.type}
节点标题：{current_node.title}
节点内容：
{current_node.content}

---

【画布关系上下文】

以下内容来自用户在画布中手动建立的节点连接，优先级较高：

{graph_context_text}

---

【向量检索上下文】

以下内容来自 RAG 语义检索，可能与当前节点相关：

{vector_context_text}

---

【用户请求】

{user_query}

---

【输出要求】

请输出 JSON，不要输出 Markdown，不要输出完整剧情正文。

JSON 格式如下：

{{
  "agent": "inspiration",
  "summary": "一句话概括当前节点的创作状态",
  "questions": [
    "引导性问题1",
    "引导性问题2",
    "引导性问题3"
  ],
  "missing_parts": [
    "当前设定缺失点1",
    "当前设定缺失点2"
  ],
  "suggested_nodes": [
    {{
      "nodeType": "plot",
      "title": "建议新节点标题",
      "reason": "为什么建议创建这个节点"
    }}
  ],
  "boundary_notice": "提醒用户这些只是建议，最终设定由用户决定"
}}"""


def _format_graph_context(context: list[RagGraphContextItem]) -> str:
    if not context:
        return "暂无直接连接的相关节点"

    return "\n\n".join(
        [
            f"- 关系：{item.relation_label}（{item.relation_type}, {item.direction}）\n"
            f"  节点类型：{item.type}\n"
            f"  节点标题：{item.title}\n"
            f"  节点内容：{item.content}"
            for item in context
        ]
    )


def _format_vector_context(context: list[RagVectorContextItem]) -> str:
    if not context:
        return "暂无向量检索结果"

    return "\n\n".join(
        [
            f"- 相似度：{item.score:.2f}\n"
            f"  节点类型：{item.type}\n"
            f"  节点标题：{item.title}\n"
            f"  节点内容：{item.content}"
            for item in context
        ]
    )


def _node_to_current_payload(node: NodeORM) -> RagCurrentNodePayload:
    return RagCurrentNodePayload(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=node.content,
        tags=_db_tags_to_api(node.meta),
    )


def _node_to_vector_item(node: NodeORM, score: float) -> RagVectorContextItem:
    return RagVectorContextItem(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=node.content,
        score=round(score, 4),
    )


def _node_to_document(node: NodeORM) -> str:
    tags = ", ".join(_db_tags_to_api(node.meta))
    return f"""Title: {node.title}
Type: {node.node_type}
Tags: {tags}
Content:
{node.content}"""


def _db_tags_to_api(meta: Any) -> list[str]:
    if isinstance(meta, dict):
        tags = meta.get("tags", [])
        return [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    return []


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0

    return sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
