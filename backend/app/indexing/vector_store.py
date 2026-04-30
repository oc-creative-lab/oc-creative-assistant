"""ChromaDB 向量库与 embedding 封装。

本模块只负责 ChromaDB collection 初始化、项目隔离 id/metadata 规范、
节点文档 upsert/delete/query，以及 PoC 阶段的本地 hash embedding。
索引同步时机由 `app.indexing.sync` 决定。
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from app.db.models import NodeORM
from app.indexing.config import CHROMA_COLLECTION_NAME, CHROMA_PATH, EMBEDDING_DIMENSION
from app.indexing.document_loader import node_to_document


class HashEmbeddingProvider:
    """PoC 占位 embedding 提供者。

    当前实现只做本地 hash 向量化，后续可替换为 OpenAI、DeepSeek、BGE 等真实语义向量。
    """

    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        """将文本转换为固定维度向量。

        Args:
            text: 需要向量化的文本。

        Returns:
            归一化后的固定维度向量；空文本会返回全零向量。
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


embedding_provider = HashEmbeddingProvider()


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
        RuntimeError: 当 ChromaDB 未安装时抛出，调用方可选择降级。
    """
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("ChromaDB 未安装，已使用本地 hash embedding 降级检索。") from error

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

    collection.upsert(
        ids=[build_chroma_id(node.project_id, node.id)],
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
            }
        ],
    )


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
        return [], [], []

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
