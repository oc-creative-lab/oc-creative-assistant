"""RAG configuration compatibility module.

RAG shares part of its retrieval configuration with the vector index; the real
configuration source lives in `app.indexing.config`. This module is kept so that
imports within RAG carry clearer semantics.
"""

from app.indexing.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PATH,
    DEFAULT_NODE_STATUS,
    DEFAULT_RELATION_LABEL,
    DEFAULT_RELATION_TYPE,
    EMBEDDING_DIMENSION,
    MAX_TOP_K,
)

__all__ = [
    "CHROMA_COLLECTION_NAME",
    "CHROMA_PATH",
    "DEFAULT_NODE_STATUS",
    "DEFAULT_RELATION_LABEL",
    "DEFAULT_RELATION_TYPE",
    "EMBEDDING_DIMENSION",
    "MAX_TOP_K",
]
