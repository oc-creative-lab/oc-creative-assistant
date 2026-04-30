"""RAG 服务兼容入口。

RAG 逻辑已拆分到 backend/rag/ 子包；保留本文件是为了兼容既有
`from rag_service import ...` 导入方式，避免路由层和外部调用方跟随重构改动。
"""

from rag.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PATH,
    DEFAULT_NODE_STATUS,
    DEFAULT_RELATION_LABEL,
    DEFAULT_RELATION_TYPE,
    EMBEDDING_DIMENSION,
)
from rag.document_loader import _db_tags_to_api, _node_to_current_payload, _node_to_document, _node_to_vector_item
from rag.prompts import _format_graph_context, _format_vector_context, build_inspiration_prompt
from rag.retrieval import (
    _build_graph_context,
    _build_vector_context,
    _cosine_similarity,
    _merge_context,
    _query_chroma_context,
    _query_in_memory_context,
)
from rag.service import build_rag_context
from rag.vector_store import HashEmbeddingProvider, embedding_provider

__all__ = [
    "CHROMA_COLLECTION_NAME",
    "CHROMA_PATH",
    "DEFAULT_NODE_STATUS",
    "DEFAULT_RELATION_LABEL",
    "DEFAULT_RELATION_TYPE",
    "EMBEDDING_DIMENSION",
    "HashEmbeddingProvider",
    "build_inspiration_prompt",
    "build_rag_context",
    "embedding_provider",
]
