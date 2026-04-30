"""RAG 向量库与 embedding 封装。

本模块只负责 Chroma collection 初始化、项目隔离 id/metadata 规范、
节点文档 upsert/delete/query，以及 PoC 阶段的 hash embedding。
索引“什么时候同步、同步哪些节点”由 rag.index_sync 决定。
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from models import NodeORM

from rag.config import CHROMA_COLLECTION_NAME, CHROMA_PATH, EMBEDDING_DIMENSION
from rag.document_loader import _node_to_document


class HashEmbeddingProvider:
    """PoC 占位 embedding，后续可替换为 OpenAI / DeepSeek / BGE 等真实语义向量。"""

    dimension = EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        """把文本转换为固定维度向量；只做本地计算，不访问外部 API。"""
        tokens = self._tokenize(text)
        vector = [0.0] * self.dimension

        for token in tokens:
            # hash 到固定维度能保证同一 token 稳定落在同一位置，便于 PoC 做可复现检索。
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))

        if norm == 0:
            return vector

        return [value / norm for value in vector]

    def _tokenize(self, text: str) -> list[str]:
        """生成用于 hash embedding 的 token；不修改外部状态。"""
        lowered = text.lower()
        words = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        char_bigrams = [text[index : index + 2] for index in range(max(len(text) - 1, 0))]
        return words + chinese_chars + char_bigrams


embedding_provider = HashEmbeddingProvider()


def build_chroma_id(project_id: str, node_id: str) -> str:
    """返回 Chroma 记录 id。

    project_id 和 node_id 组合后，不同项目里相同 node_id 不会互相覆盖。
    """
    return f"{project_id}:{node_id}"


def get_chroma_collection() -> Any:
    """初始化并返回本地 Chroma collection；会确保 backend/data/chroma 目录存在。"""
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
    """把单个 ORM 节点写入 Chroma。

    入参 collection 是 Chroma collection，node 是已提交到 SQLite 的最新节点；
    fingerprint 是检索文档指纹，None 时按当前文档计算。该函数会修改 Chroma。
    """
    document = _node_to_document(node)
    node_fingerprint = fingerprint or hashlib.sha256(f"ID: {node.id}\n{document}".encode("utf-8")).hexdigest()

    collection.upsert(
        ids=[build_chroma_id(node.project_id, node.id)],
        documents=[document],
        embeddings=[embedding_provider.embed(document)],
        metadatas=[
            {
                # project_id 既写入 id，也写入 metadata：id 防覆盖，metadata 负责查询过滤。
                "project_id": node.project_id,
                "node_id": node.id,
                "node_type": node.node_type,
                "title": node.title,
                "fingerprint": node_fingerprint,
            }
        ],
    )


def upsert_nodes(collection: Any, nodes: list[NodeORM]) -> None:
    """批量写入节点到 Chroma；仅供同步阶段调用，会修改 Chroma。"""
    for node in nodes:
        upsert_node(collection, node)


def delete_node(collection: Any, project_id: str, node_id: str) -> None:
    """从 Chroma 删除单个项目节点；不会修改 SQLite。"""
    collection.delete(ids=[build_chroma_id(project_id, node_id)])


def delete_nodes(collection: Any, project_id: str, node_ids: list[str]) -> None:
    """从 Chroma 批量删除项目节点；空列表时不做任何事。"""
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
    """查询当前项目的 Chroma 记录。

    返回值依次是 Chroma ids、metadata 列表和 distance 列表。查询必须按 project_id
    过滤，因为所有项目共享一个 collection，不能让其它项目节点进入当前 prompt。
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
