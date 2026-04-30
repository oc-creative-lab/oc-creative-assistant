"""RAG 子包入口。

该包按职责拆分上下文构建、检索、向量库和 prompt 拼接逻辑；
外部仍优先通过 rag.service 或兼容层 rag_service 调用。
"""

from rag.service import build_rag_context

__all__ = ["build_rag_context"]
