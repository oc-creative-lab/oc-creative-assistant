"""ChromaDB 向量库与阿里 embedding 封装。

本模块只负责 ChromaDB collection 初始化、项目隔离 id/metadata 规范、节点文档
upsert/delete/query，以及通过 DashScope OpenAI-compatible API 计算语义向量。
索引同步时机由 `app.indexing.sync` 决定。
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.db.models import NodeORM
from app.indexing.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PATH,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    INDEXING_DEBUG_LOG,
)
from app.indexing.document_loader import node_to_document


def _log(message: str) -> None:
    """打印向量写入和 embedding API 调用信息，便于 PoC 阶段观察真实执行路径。"""
    if INDEXING_DEBUG_LOG:
        print(f"[vector-store] {message}", flush=True)


class DashScopeEmbeddingProvider:
    """阿里 DashScope embedding 提供者。

    DashScope 提供 OpenAI-compatible 接口，因此这里复用 openai SDK，避免新增依赖。
    该 provider 会在写入 ChromaDB 和查询 ChromaDB 时使用同一套向量模型，保证向量空间一致。
    """

    name = "dashscope"

    def __init__(self, api_key: str, base_url: str, model: str, dimension: int) -> None:
        """保存 embedding API 配置；真正创建 client 延迟到首次调用，避免无关 import 影响启动。"""
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimension = dimension
        self._client: Any | None = None

    def embed(self, text: str) -> list[float]:
        """将单条文本转换为语义向量。"""
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """批量调用阿里 embedding API。

        Args:
            texts: 待向量化的检索文档列表。
        Returns:
            与输入顺序一致的 float 向量列表。
        """
        if not texts:
            return []

        _log(f"call embedding api model={self.model} dimension={self.dimension} batch_size={len(texts)}")
        response = self._get_client().embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimension,
            encoding_format="float",
        )
        vectors_by_index: dict[int, list[float]] = {}

        for offset, item in enumerate(response.data):
            index = getattr(item, "index", offset)
            vector = list(item.embedding)

            if len(vector) != self.dimension:
                raise RuntimeError(
                    f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}"
                )

            vectors_by_index[int(index)] = vector

        vectors = [vectors_by_index[index] for index in range(len(texts))]
        _log(f"embedding api success model={self.model} vectors={len(vectors)} dimension={self.dimension}")
        return vectors

    def _get_client(self) -> Any:
        """延迟初始化 OpenAI-compatible client，避免启动时暴露 API key 配置问题。"""
        if not self.api_key:
            raise RuntimeError("未设置 OC_EMBEDDING_API_KEY 或 DASHSCOPE_API_KEY，无法调用阿里 embedding API")

        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError("openai 依赖未安装，无法调用阿里 embedding API") from error

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        return self._client


embedding_provider = DashScopeEmbeddingProvider(
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
)


def get_embedding_signature() -> str:
    """返回当前 embedding 配置签名。

    ChromaDB 中保存该签名，用于判断模型、base_url 或维度变化后是否需要重写向量。
    """
    return (
        f"{embedding_provider.name}:"
        f"{getattr(embedding_provider, 'base_url', '')}:"
        f"{embedding_provider.model}:"
        f"{embedding_provider.dimension}"
    )


def build_chroma_id(project_id: str, node_id: str) -> str:
    """构造 ChromaDB 记录 ID。

    Args:
        project_id: 节点所属项目 ID。
        node_id: 节点 ID。

    Returns:
        由项目和节点组成的稳定记录 ID，避免不同项目的同名节点互相覆盖。
    """
    return f"{project_id}:{node_id}"


def get_chroma_collection() -> Any:
    """初始化并返回本地 ChromaDB collection。

    Returns:
        ChromaDB collection 对象。

    Raises:
        RuntimeError: 当 ChromaDB 未安装时抛出，调用方应把索引失败状态返回给前端。
    """
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("ChromaDB 未安装，无法写入或查询向量索引。") from error

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_node(collection: Any, node: NodeORM, fingerprint: str | None = None) -> None:
    """将单个节点写入 ChromaDB。

    该函数会根据 ORM 节点构造检索文档和 embedding，并写入当前 collection。
    如果同一 ChromaDB ID 已存在，则执行覆盖更新。

    Args:
        collection: ChromaDB collection 对象。
        node: 已提交到 SQLite 的最新节点。
        fingerprint: 检索文档指纹；为 None 时按当前文档计算。
    """
    document = node_to_document(node)
    node_fingerprint = fingerprint or hashlib.sha256(f"ID: {node.id}\n{document}".encode("utf-8")).hexdigest()
    chroma_id = build_chroma_id(node.project_id, node.id)
    _log(f"upsert vector chroma_id={chroma_id} node_id={node.id} title={node.title!r}")

    collection.upsert(
        ids=[chroma_id],
        documents=[document],
        embeddings=[embedding_provider.embed(document)],
        metadatas=[
            {
                # project_id 同时写入 id 与 metadata：id 防覆盖，metadata 负责查询过滤。
                "project_id": node.project_id,
                "node_id": node.id,
                "node_type": node.node_type,
                "title": node.title,
                "fingerprint": node_fingerprint,
                "embedding_signature": get_embedding_signature(),
            }
        ],
    )
    _log(f"upsert vector success chroma_id={chroma_id}")


def upsert_nodes(collection: Any, nodes: list[NodeORM]) -> None:
    """批量写入节点到 ChromaDB。

    Args:
        collection: ChromaDB collection 对象。
        nodes: 需要写入的 ORM 节点列表。
    """
    for node in nodes:
        upsert_node(collection, node)


def delete_node(collection: Any, project_id: str, node_id: str) -> None:
    """从 ChromaDB 删除单个项目节点。

    Args:
        collection: ChromaDB collection 对象。
        project_id: 节点所属项目 ID。
        node_id: 需要删除的节点 ID。
    """
    collection.delete(ids=[build_chroma_id(project_id, node_id)])


def delete_nodes(collection: Any, project_id: str, node_ids: list[str]) -> None:
    """从 ChromaDB 批量删除项目节点。

    Args:
        collection: ChromaDB collection 对象。
        project_id: 节点所属项目 ID。
        node_ids: 需要删除的节点 ID 列表。
    """
    if not node_ids:
        return

    _log(f"delete vectors project_id={project_id} node_ids={node_ids}")
    collection.delete(ids=[build_chroma_id(project_id, node_id) for node_id in node_ids])


def query_collection(
    collection: Any,
    project_id: str,
    query: str,
    top_k: int,
    node_count: int,
) -> tuple[list[str], list[dict], list[float]]:
    """查询当前项目的 ChromaDB 记录。

    所有项目共享一个 collection，因此必须通过 metadata 中的 project_id 过滤，
    防止其它项目节点进入当前 prompt。

    Args:
        collection: ChromaDB collection 对象。
        project_id: 当前项目 ID。
        query: 用户输入或当前节点内容构造的检索问题。
        top_k: 期望返回的最多上下文数量。
        node_count: 当前项目节点总数，用于限制 ChromaDB 查询规模。

    Returns:
        依次返回 ChromaDB ID 列表、metadata 列表和 distance 列表。
    """
    if collection.count() == 0:
        _log(f"query skipped project_id={project_id} reason=empty_collection")
        return [], [], []

    _log(f"query vectors project_id={project_id} top_k={top_k} node_count={node_count}")
    result = collection.query(
        query_embeddings=[embedding_provider.embed(query)],
        n_results=min(top_k + 1, node_count),
        where={"project_id": project_id},
        include=["metadatas", "distances"],
    )
    return (
        result.get("ids", [[]])[0],
        result.get("metadatas", [[]])[0],
        result.get("distances", [[]])[0],
    )
