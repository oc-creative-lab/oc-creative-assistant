"""Embedding 提供者。

把"如何把文本转成向量"封装在一个独立模块里, 让 vector_store 只关心 ChromaDB
collection 与文档读写。线上优先用 DashScope 真实模型, 配置缺失或 SDK 初始化
失败时降级到本地 hash 占位 provider, 保证 RAG 链路在离线 / CI 场景下仍可用。

进程级单例 ``embedding_provider`` 在模块导入时确定, 索引同步与查询都共用它,
避免不同路径用不同模型造成向量空间不一致。
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache
from typing import Any

from app.core.settings import get_embedding_settings, get_indexing_settings
from app.indexing.config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    INDEXING_DEBUG_LOG,
)


logger = logging.getLogger(__name__)


def _log(message: str) -> None:
    """打印 embedding API 调用信息, 便于观察真实执行路径; 与 vector_store._log 同源。"""
    if INDEXING_DEBUG_LOG:
        print(f"[embedding] {message}", flush=True)


class HashEmbeddingProvider:
    """PoC 占位 embedding 提供者。

    当真实 embedding 服务(DashScope)未配置、依赖缺失或 SDK 初始化失败时,
    作为本地降级方案使用, 保证 ChromaDB 写入与查询不会因网络/配置问题中断。
    属性命名与 ``DashScopeEmbeddingProvider`` 保持一致, 以便 ``app.indexing.sync``
    在不区分 provider 类型的情况下读取 ``name``/``model``/``dimension``。
    """

    name = "hash"
    base_url = ""
    model = "hash"

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        """允许在测试或降级路径下显式覆盖向量维度, 默认跟随全局 EMBEDDING_DIMENSION。"""
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        """将单条文本转换为固定维度向量。"""
        return self._embed_single(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转换为固定维度向量; 与真实 provider 接口保持一致。"""
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        """对单条文本做 token hash → 归一化向量。

        Args:
            text: 待向量化的文本。
        Returns:
            归一化后的固定维度向量; 空文本返回全零向量。
        """
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            # hash 到固定维度可以保证同一 token 稳定落位, 便于 PoC 做可复现检索。
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

    DashScope 提供 OpenAI-compatible 接口, 因此这里复用 openai SDK, 避免新增依赖。
    该 provider 在写入 ChromaDB 和查询 ChromaDB 时使用同一套向量模型, 保证向量
    空间一致。
    """

    name = "dashscope"

    def __init__(self, api_key: str, base_url: str, model: str, dimension: int) -> None:
        """保存 embedding API 配置; 真正创建 client 延迟到首次调用, 避免无关 import 影响启动。"""
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimension = dimension
        self._client: Any | None = None

    def embed(self, text: str) -> list[float]:
        """将单条文本转换为语义向量。"""
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """批量调用阿里 embedding API。"""
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
        """延迟初始化 OpenAI-compatible client, 避免启动时暴露 API key 配置问题。"""
        if not self.api_key:
            raise RuntimeError("未设置 OC_EMBEDDING_API_KEY 或 DASHSCOPE_API_KEY, 无法调用阿里 embedding API")

        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError("openai 依赖未安装, 无法调用阿里 embedding API") from error

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        return self._client


def _build_embedding_provider() -> Any:
    """根据 .env 配置选择真实 provider 或本地 hash 占位 provider。

    优先使用配置好的 DashScope; 配置缺失或 SDK 初始化失败时降级到 hash provider,
    保证 RAG 链路始终可用, 便于离线开发和 CI。
    """
    settings = get_embedding_settings()
    indexing = get_indexing_settings()

    if not settings.is_configured:
        if indexing.debug_log:
            logger.warning("OC_EMBEDDING_* 未配置, 使用本地 hash embedding 占位")
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
        logger.warning("DashScope embedding 初始化失败, 降级到 hash 占位: %s", error)
        return HashEmbeddingProvider(EMBEDDING_DIMENSION)


embedding_provider = _build_embedding_provider()


@lru_cache(maxsize=2048)
def _cached_query_embedding(text: str) -> tuple[float, ...]:
    """进程级 query embedding 缓存; 用 tuple 是为了 lru_cache 可 hash, 调用方再 list 化。

    仅用于"查询路径"; 写入路径 (upsert document embedding) 不能缓存, 因为每个
    文档内容不同, 没有命中可言。
    """
    return tuple(embedding_provider.embed(text))


def embed_query(text: str) -> list[float]:
    """带 LRU 缓存的 query embedding 入口; tool_loop / RAG / parallel_retrieval 都走它。"""
    return list(_cached_query_embedding(text))


def get_embedding_signature() -> str:
    """返回当前 embedding 配置签名。

    ChromaDB 中保存该签名, 用于判断模型、base_url 或维度变化后是否需要重写向量。
    """
    return (
        f"{embedding_provider.name}:"
        f"{getattr(embedding_provider, 'base_url', '')}:"
        f"{embedding_provider.model}:"
        f"{embedding_provider.dimension}"
    )