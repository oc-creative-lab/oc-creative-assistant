"""SQLite 到 ChromaDB 的索引同步策略。

SQLite 是主数据源，ChromaDB 是可重建的检索索引。本模块负责在 SQLite
事务提交后，根据检索文档 fingerprint 做项目级或节点级增量同步。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.db.models import NodeORM
from app.indexing.document_loader import node_to_document
from app.indexing.vector_store import (
    delete_nodes,
    get_chroma_collection,
    get_embedding_signature,
    upsert_node,
)


@dataclass
class IndexingSyncResult:
    """向量索引同步结果。

    SQLite 保存是主流程；这个结果只描述 ChromaDB/embedding 是否同步成功，供 API 返回给前端提示。
    """

    status: str
    message: str
    provider: str
    model: str
    dimension: int
    expected_nodes: int = 0
    indexed_nodes: int = 0
    missing_node_ids: list[str] = field(default_factory=list)
    error: str | None = None


def _base_result(status: str, message: str, expected_nodes: int = 0, error: str | None = None) -> IndexingSyncResult:
    """构造统一的索引状态，集中填充当前 embedding 配置。"""
    from app.indexing.vector_store import embedding_provider

    return IndexingSyncResult(
        status=status,
        message=message,
        provider=embedding_provider.name,
        model=embedding_provider.model,
        dimension=embedding_provider.dimension,
        expected_nodes=expected_nodes,
        error=error,
    )


def _read_index_state(collection: Any, project_id: str) -> dict[str, dict[str, str]]:
    """读取当前项目已写入 ChromaDB 的 fingerprint。

    Args:
        collection: ChromaDB collection 对象。
        project_id: 需要读取索引状态的项目 ID。

    Returns:
        原始 node_id 到 fingerprint 的映射。
    """
    records = collection.get(where={"project_id": project_id}, include=["metadatas"])
    index_state: dict[str, dict[str, str]] = {}

    for metadata in records.get("metadatas", []) or []:
        if not isinstance(metadata, dict):
            continue

        node_id = metadata.get("node_id")
        fingerprint = metadata.get("fingerprint")
        embedding_signature = metadata.get("embedding_signature")

        if isinstance(node_id, str) and isinstance(fingerprint, str):
            # embedding_signature 用于感知 base_url / model / dimension 变化，避免沿用旧模型写出的向量。
            index_state[node_id] = {
                "fingerprint": fingerprint,
                "embedding_signature": embedding_signature if isinstance(embedding_signature, str) else "",
            }

    return index_state


def build_node_fingerprint(node: NodeORM) -> str:
    """计算节点检索文档 fingerprint。

    fingerprint 只基于会进入检索文档的信息，不包含 position、sort_order、
    created_at 或 updated_at，因此拖动节点不会触发 embedding 更新。

    Args:
        node: 需要计算指纹的 ORM 节点。

    Returns:
        sha256 十六进制字符串。
    """
    # node.id 不一定进入展示文档，但必须参与 fingerprint，避免同内容不同节点被误判为同一记录。
    document = f"ID: {node.id}\n{node_to_document(node)}"
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def verify_project_index(project_id: str, nodes: list[NodeORM], collection: Any | None = None) -> IndexingSyncResult:
    """检查当前项目节点是否都已经写入当前 embedding 配置对应的向量。

    Args:
        project_id: 当前项目 ID。
        nodes: SQLite 提交后的最新节点快照。
        collection: 可选 ChromaDB collection，复用调用方已有连接。
    Returns:
        描述已索引数量、缺失节点和当前 embedding 配置的同步结果。
    """
    active_collection = collection or get_chroma_collection()
    index_state = _read_index_state(active_collection, project_id)
    embedding_signature = get_embedding_signature()
    missing_node_ids: list[str] = []

    for node in nodes:
        indexed_node = index_state.get(node.id, {})

        if (
            indexed_node.get("fingerprint") != build_node_fingerprint(node)
            or indexed_node.get("embedding_signature") != embedding_signature
        ):
            # fingerprint 或 embedding 配置签名不一致，说明该节点还没有可用于当前语义检索的向量。
            missing_node_ids.append(node.id)

    result = _base_result(
        status="synced" if not missing_node_ids else "partial",
        message="向量索引已同步" if not missing_node_ids else "部分节点尚未成功写入向量索引",
        expected_nodes=len(nodes),
    )
    result.indexed_nodes = len(nodes) - len(missing_node_ids)
    result.missing_node_ids = missing_node_ids
    return result


def sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> IndexingSyncResult:
    """按项目增量同步 ChromaDB 索引。

    该函数用于前端保存完整 graph 快照后。它会对比保存前后的节点指纹：
    新增或检索文档变化的节点执行 upsert，已删除的节点执行 delete。

    Args:
        project_id: 需要同步索引的项目 ID。
        old_nodes: 保存前的项目节点快照。
        new_nodes: SQLite 提交后的最新项目节点快照。
    """
    collection = get_chroma_collection()
    index_state = _read_index_state(collection, project_id)
    embedding_signature = get_embedding_signature()
    old_fingerprints = {node.id: build_node_fingerprint(node) for node in old_nodes}
    new_fingerprints = {node.id: build_node_fingerprint(node) for node in new_nodes}

    deleted_node_ids = sorted(set(old_fingerprints) - set(new_fingerprints))
    # 整图保存会重写 SQLite 行，但 ChromaDB 只删除真正从 payload 消失的节点。
    delete_nodes(collection, project_id, deleted_node_ids)

    for node in new_nodes:
        new_fingerprint = new_fingerprints[node.id]
        old_fingerprint = old_fingerprints.get(node.id)
        indexed_node = index_state.get(node.id, {})
        indexed_fingerprint = indexed_node.get("fingerprint")
        indexed_embedding_signature = indexed_node.get("embedding_signature")

        # 文档 fingerprint 和 embedding 配置签名都一致时才跳过；换模型或维度后需要重写向量。
        if (
            old_fingerprint == new_fingerprint
            and indexed_fingerprint == new_fingerprint
            and indexed_embedding_signature == embedding_signature
        ):
            # 坐标或排序变化不影响检索文档；索引已有相同 fingerprint 时跳过 embedding 更新。
            continue

        upsert_node(collection, node, new_fingerprint)

    return verify_project_index(project_id, new_nodes, collection)


def sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> IndexingSyncResult:
    """同步单个节点到 ChromaDB。

    Args:
        node: SQLite 提交后的最新节点。
        old_fingerprint: 更新前的检索文档指纹；相同则可跳过写入。
    """
    new_fingerprint = build_node_fingerprint(node)
    collection = get_chroma_collection()

    if old_fingerprint == new_fingerprint:
        indexed_node = _read_index_state(collection, node.project_id).get(node.id, {})
        indexed_fingerprint = indexed_node.get("fingerprint")
        indexed_embedding_signature = indexed_node.get("embedding_signature")

        # 检索文档没变时，也要确认索引是当前 embedding 配置写出的，否则会混用旧模型向量。
        if indexed_fingerprint == new_fingerprint and indexed_embedding_signature == get_embedding_signature():
            result = _base_result("synced", "向量索引已同步", expected_nodes=1)
            result.indexed_nodes = 1
            return result

        # 检索字段没变但索引记录缺失时，通常是用户清空了 ChromaDB 目录，需要按 SQLite 补写。

    upsert_node(collection, node, new_fingerprint)
    return verify_project_index(node.project_id, [node], collection)


def safe_sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> IndexingSyncResult:
    """安全同步项目索引。

    ChromaDB 同步失败时吞掉异常，避免可重建索引影响 SQLite 主数据保存。

    Args:
        project_id: 需要同步索引的项目 ID。
        old_nodes: 保存前的项目节点快照。
        new_nodes: SQLite 提交后的最新项目节点快照。
    """
    try:
        return sync_project_index_incremental(project_id, old_nodes, new_nodes)
    except Exception as error:  # noqa: BLE001
        # SQLite 是主数据源，ChromaDB/embedding 失败不能回滚保存；错误会返回给前端提示用户修复配置。
        result = _base_result(
            status="failed",
            message="SQLite 已保存，但 embedding 向量索引写入失败",
            expected_nodes=len(new_nodes),
            error=str(error),
        )
        try:
            # 即使本次同步失败，也尽量读取 ChromaDB 现状，告诉前端哪些节点已经有可用向量。
            verified = verify_project_index(project_id, new_nodes)
            result.indexed_nodes = verified.indexed_nodes
            result.missing_node_ids = verified.missing_node_ids
        except Exception:  # noqa: BLE001
            result.missing_node_ids = [node.id for node in new_nodes]
        return result


def safe_sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> IndexingSyncResult:
    """安全同步单节点索引。

    Args:
        node: SQLite 提交后的最新节点。
        old_fingerprint: 更新前的检索文档指纹；相同则可跳过写入。
    """
    try:
        return sync_node_index(node, old_fingerprint)
    except Exception as error:  # noqa: BLE001
        # 索引可从 SQLite 重建，因此这里保持失败隔离，同时把错误返回给调用方。
        result = _base_result(
            status="failed",
            message="SQLite 已保存，但该节点 embedding 向量写入失败",
            expected_nodes=1,
            error=str(error),
        )
        try:
            verified = verify_project_index(node.project_id, [node])
            result.indexed_nodes = verified.indexed_nodes
            result.missing_node_ids = verified.missing_node_ids
        except Exception:  # noqa: BLE001
            result.missing_node_ids = [node.id]
        return result
