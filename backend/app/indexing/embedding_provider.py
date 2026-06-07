"""Embedding provider.

Encapsulates "how to turn text into vectors" in a separate module, so that
vector_store only cares about ChromaDB collections and document read/write. In
production the real DashScope model is preferred; when configuration is missing or
SDK initialization fails, it falls back to a local hash placeholder provider,
ensuring the RAG pipeline still works in offline / CI scenarios.

The process-level singleton ``embedding_provider`` is determined at module import
time and shared by both index synchronization and queries, to avoid vector-space
inconsistency caused by different paths using different models.
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
    """Print embedding API call info to make the real execution path observable; same source as vector_store._log."""
    if INDEXING_DEBUG_LOG:
        print(f"[embedding] {message}", flush=True)


class HashEmbeddingProvider:
    """PoC placeholder embedding provider.

    Used as a local fallback when the real embedding service (DashScope) is not
    configured, a dependency is missing, or SDK initialization fails, ensuring
    ChromaDB writes and queries are not interrupted by network/configuration issues.
    Its attribute naming matches ``DashScopeEmbeddingProvider`` so that
    ``app.indexing.sync`` can read ``name``/``model``/``dimension`` without
    distinguishing the provider type.
    """

    name = "hash"
    base_url = ""
    model = "hash"

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        """Allow explicitly overriding the vector dimension in tests or fallback paths; defaults to the global EMBEDDING_DIMENSION."""
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        """Convert a single piece of text into a fixed-dimension vector."""
        return self._embed_single(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Batch-convert texts into fixed-dimension vectors; matches the real provider interface."""
        return [self._embed_single(text) for text in texts]

    def _embed_single(self, text: str) -> list[float]:
        """Token-hash a single text into a normalized vector.

        Args:
            text: The text to vectorize.
        Returns:
            A normalized fixed-dimension vector; empty text returns an all-zero vector.
        """
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            # Hashing into a fixed dimension keeps the same token landing in a stable slot, enabling reproducible retrieval for the PoC.
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))

        if norm == 0:
            return vector

        return [value / norm for value in vector]

    def _tokenize(self, text: str) -> list[str]:
        """Generate tokens for hash embedding.

        Args:
            text: The raw text.
        Returns:
            A combined token list of English/numeric words, single Chinese characters, and character bigrams.
        """
        lowered = text.lower()
        words = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        char_bigrams = [text[index : index + 2] for index in range(max(len(text) - 1, 0))]
        return words + chinese_chars + char_bigrams


class DashScopeEmbeddingProvider:
    """Alibaba DashScope embedding provider.

    DashScope offers an OpenAI-compatible interface, so this reuses the openai SDK
    to avoid adding a new dependency. This provider uses the same vector model for
    both writing to ChromaDB and querying ChromaDB, ensuring vector-space consistency.
    """

    name = "dashscope"

    def __init__(self, api_key: str, base_url: str, model: str, dimension: int) -> None:
        """Store the embedding API config; actual client creation is deferred to the first call to avoid unrelated imports affecting startup."""
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimension = dimension
        self._client: Any | None = None

    def embed(self, text: str) -> list[float]:
        """Convert a single piece of text into a semantic vector."""
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Batch-call the Alibaba embedding API."""
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
        """Lazily initialize the OpenAI-compatible client to avoid exposing API key config issues at startup."""
        if not self.api_key:
            raise RuntimeError("OC_EMBEDDING_API_KEY or DASHSCOPE_API_KEY is not set; cannot call the Alibaba embedding API")

        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError("The openai dependency is not installed; cannot call the Alibaba embedding API") from error

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        return self._client


def _build_embedding_provider() -> Any:
    """Choose the real provider or the local hash placeholder provider based on .env config.

    Prefer a configured DashScope; when config is missing or SDK initialization
    fails, fall back to the hash provider, ensuring the RAG pipeline is always
    available, which helps offline development and CI.
    """
    settings = get_embedding_settings()
    indexing = get_indexing_settings()

    if not settings.is_configured:
        if indexing.debug_log:
            logger.warning("OC_EMBEDDING_* is not configured; using the local hash embedding placeholder")
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
                "DashScope embedding enabled: model=%s dim=%d",
                settings.model,
                settings.dimension,
            )
        return provider
    except Exception as error:  # noqa: BLE001
        logger.warning("DashScope embedding initialization failed; falling back to the hash placeholder: %s", error)
        return HashEmbeddingProvider(EMBEDDING_DIMENSION)


embedding_provider = _build_embedding_provider()


@lru_cache(maxsize=2048)
def _cached_query_embedding(text: str) -> tuple[float, ...]:
    """Process-level query embedding cache; a tuple is used so lru_cache can hash it, and callers convert back to a list.

    Used only for the "query path"; the write path (upsert document embedding)
    cannot be cached because each document's content differs, so there are no hits.
    """
    return tuple(embedding_provider.embed(text))


def embed_query(text: str) -> list[float]:
    """LRU-cached query embedding entry point; tool_loop / RAG / parallel_retrieval all go through it."""
    return list(_cached_query_embedding(text))


def get_embedding_signature() -> str:
    """Return the signature of the current embedding configuration.

    ChromaDB stores this signature to determine whether vectors need to be
    rewritten after the model, base_url, or dimension changes.
    """
    return (
        f"{embedding_provider.name}:"
        f"{getattr(embedding_provider, 'base_url', '')}:"
        f"{embedding_provider.model}:"
        f"{embedding_provider.dimension}"
    )