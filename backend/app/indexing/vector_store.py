"""ChromaDB 向量库与阿里 embedding 封装。

本模块只负责 ChromaDB collection 初始化、项目隔离 id/metadata 规范、节点文档
upsert/delete/query，以及通过 DashScope OpenAI-compatible API 计算语义向量。
当 .env 未配置真实 embedding 服务、或 SDK 初始化失败时，会降级到本地
hash provider，保证 RAG 链路在离线/CI 场景下仍然可用。
索引同步时机由 `app.indexing.sync` 决定。
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any

from app.core.settings import get_embedding_settings, get_indexing_settings
from app.db.models import NodeORM
from app.indexing.config import (
    CHROMA_PATH,
    COLLECTION_BY_NODE_TYPE,
    DEFAULT_COLLECTION_NAME,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    INDEXING_DEBUG_LOG,
)
from app.indexing.document_loader import node_to_document


logger = logging.getLogger(__name__)


def _log(message: str) -> None:
    """打印向量写入和 embedding API 调用信息，便于 PoC 阶段观察真实执行路径。"""
    if INDEXING_DEBUG_LOG:
        print(f"[vector-store] {message}", flush=True)


class HashEmbeddingProvider:
    """PoC 占位 embedding 提供者。

    当真实 embedding 服务（DashScope）未配置、依赖缺失或 SDK 初始化失败时，
    作为本地降级方案使用，保证 ChromaDB 写入与查询不会因网络/配置问题中断。
    属性命名与 `DashScopeEmbeddingProvider` 保持一致，以便 `app.indexing.sync`
    在不区分 provider 类型的情况下读取 `name`/`model`/`dimension`。
    """

    name = "hash"
    base_url = ""
    model = "hash"

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        """允许在测试或降级路径下显式覆盖向量维度，默认跟随全局 EMBEDDING_DIMENSION。"""
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        """将单条文本转换为固定维度向量。"""
        return self._embed_single(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转换为固定维度向量；与真实 provider 接口保持一致。"""
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        """对单条文本做 token hash → 归一化向量。

        Args:
            text: 待向量化的文本。
        Returns:
            归一化后的固定维度向量；空文本返回全零向量。
        """
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            # hash 到固定维度可以保证同一 token 稳定落位，便于 PoC 做可复现检索。
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))

        if norm == 0:
            return vector

        return [value / norm for value in vector]

    def _tokenize(self, text: str) -> list[str]:
        """生成用于 hash embedding 的 token。

        Args:
            text: 原始文本。
        Returns:
            英文/数字词、中文单字和字符 bigram 的组合 token 列表。
        """
        lowered = text.lower()
        words = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        char_bigrams = [text[index : index + 2] for index in range(max(len(text) - 1, 0))]
        return words + chinese_chars + char_bigrams


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


def _build_embedding_provider() -> Any:
    """根据 .env 配置选择真实 provider 或本地 hash 占位 provider。

    优先使用配置好的 DashScope；配置缺失或 SDK 初始化失败时降级到 hash provider，
    保证 RAG 链路始终可用，便于离线开发和 CI。
    """
    settings = get_embedding_settings()
    indexing = get_indexing_settings()

    if not settings.is_configured:
        if indexing.debug_log:
            logger.warning("OC_EMBEDDING_* 未配置，使用本地 hash embedding 占位")
        return HashEmbeddingProvider(EMBEDDING_DIMENSION)

    try:
        provider = DashScopeEmbeddingProvider(
            settings.api_key or EMBEDDING_API_KEY,
            settings.base_url or EMBEDDING_BASE_URL,
            settings.model or EMBEDDING_MODEL,
            settings.dimension,
        )
        if indexing.debug_log:
            logger.info(
                "已启用 DashScope embedding: model=%s dim=%d",
                settings.model,
                settings.dimension,
            )
        return provider
    except Exception as error:  # noqa: BLE001
        logger.warning("DashScope embedding 初始化失败，降级到 hash 占位: %s", error)
        return HashEmbeddingProvider(EMBEDDING_DIMENSION)


embedding_provider = _build_embedding_provider()


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


def _resolve_collection_name(node_type: str) -> str:
    """根据 node_type 路由到目标 collection 名称, 未命中时走兜底集合。"""
    return COLLECTION_BY_NODE_TYPE.get(node_type, DEFAULT_COLLECTION_NAME)


def _all_collection_names() -> tuple[str, ...]:
    """返回需要管理的全部 collection 名称, 含兜底集合。"""
    return (*COLLECTION_BY_NODE_TYPE.values(), DEFAULT_COLLECTION_NAME)


def _build_chroma_client() -> Any:
    """初始化 ChromaDB PersistentClient。

    Raises:
        RuntimeError: 当 ChromaDB 未安装时抛出。
    """
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("ChromaDB 未安装, 无法写入或查询向量索引。") from error

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def get_chroma_collection_by_name(name: str) -> Any:
    """按名称获取 collection, 不存在时按 cosine 距离自动创建。"""
    client = _build_chroma_client()
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def get_chroma_collection_for_node(node_type: str) -> Any:
    """按 node_type 路由到对应 collection, 调用方不需要关心命名。"""
    return get_chroma_collection_by_name(_resolve_collection_name(node_type))


def get_all_chroma_collections() -> dict[str, Any]:
    """返回所有 collection, 用于跨集合扫描 (sync 状态读取 / 全量 Lore Memory 检索)。"""
    return {name: get_chroma_collection_by_name(name) for name in _all_collection_names()}


def upsert_node(node: NodeORM, fingerprint: str | None = None) -> None:
    """按 node_type 路由到对应 collection 写入。

    采用 self-heal 模式: 在写入目标 collection 前先从其它 collection 删除同 chroma_id,
    保证节点 type 变化时不会同时存在于多个集合中, 调用方不需要追踪 old_node_type。

    Args:
        node: 已提交到 SQLite 的最新节点。
        fingerprint: 检索文档指纹; 为 None 时按当前文档计算。
    """
    document = node_to_document(node)
    node_fingerprint = fingerprint or hashlib.sha256(f"ID: {node.id}\n{document}".encode("utf-8")).hexdigest()
    chroma_id = build_chroma_id(node.project_id, node.id)
    target_name = _resolve_collection_name(node.node_type)

    # Self-heal: 把同 chroma_id 从非目标 collection 中清除, 处理节点类型变化的迁移
    for name in _all_collection_names():
        if name == target_name:
            continue
        get_chroma_collection_by_name(name).delete(ids=[chroma_id])

    _log(f"upsert vector collection={target_name} chroma_id={chroma_id} node_id={node.id} title={node.title!r}")
    target_collection = get_chroma_collection_by_name(target_name)
    target_collection.upsert(
        ids=[chroma_id],
        documents=[document],
        embeddings=[embedding_provider.embed(document)],
        metadatas=[
            {
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


def upsert_nodes(nodes: list[NodeORM]) -> None:
    """批量写入节点; 不再传 collection, 内部按 node_type 路由。"""
    for node in nodes:
        upsert_node(node)


def delete_node(project_id: str, node_id: str) -> None:
    """从所有 collection 中删除指定 chroma_id, 不需要预先知道节点类型。"""
    chroma_id = build_chroma_id(project_id, node_id)
    for name in _all_collection_names():
        get_chroma_collection_by_name(name).delete(ids=[chroma_id])


def delete_nodes(project_id: str, node_ids: list[str]) -> None:
    """批量从所有 collection 中删除指定 chroma_id 列表。"""
    if not node_ids:
        return

    _log(f"delete vectors project_id={project_id} node_ids={node_ids}")
    chroma_ids = [build_chroma_id(project_id, node_id) for node_id in node_ids]
    for name in _all_collection_names():
        get_chroma_collection_by_name(name).delete(ids=chroma_ids)

def query_collection(
    collection: Any,
    project_id: str,
    query: str,
    top_k: int,
) -> tuple[list[str], list[dict], list[float]]:
    """在指定 collection 内做项目级查询。

    collection 已按 node_type 物理隔离, 不再需要 node_type metadata filter;
    project_id 过滤仍然保留, 避免跨项目数据泄漏到当前 prompt。

    Args:
        collection: 已经按 node_type 路由过的具体 collection。
        project_id: 当前项目 ID。
        query: 检索 query。
        top_k: 期望返回的最多上下文数量。

    Returns:
        ChromaDB ID 列表、metadata 列表和 distance 列表。
    """
    total = collection.count()
    if total == 0:
        _log(f"query skipped collection={collection.name} reason=empty_collection")
        return [], [], []

    _log(f"query vectors collection={collection.name} project_id={project_id} top_k={top_k} total={total}")
    result = collection.query(
        query_embeddings=[embedding_provider.embed(query)],
        # +1 是给当前节点自身留位置, 后续在调用方按需过滤; clamp 到 total 避免 Chroma 报参数越界
        n_results=min(top_k + 1, total),
        where={"project_id": project_id},
        include=["metadatas", "distances"],
    )
    return (
        result.get("ids", [[]])[0],
        result.get("metadatas", [[]])[0],
        result.get("distances", [[]])[0],
    )
