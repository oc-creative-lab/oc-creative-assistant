"""SQLite 到 ChromaDB 的索引同步策略。

SQLite 是主数据源，ChromaDB 是可重建的检索索引。本模块负责在 SQLite
事务提交后，根据检索文档 fingerprint 做项目级或节点级增量同步。
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.db.models import NodeORM
from app.indexing.document_loader import node_to_document
from app.indexing.vector_store import delete_nodes, get_chroma_collection, upsert_node


def _read_index_fingerprints(collection: Any, project_id: str) -> dict[str, str]:
    """读取当前项目已写入 ChromaDB 的 fingerprint。

    Args:
        collection: ChromaDB collection 对象。
        project_id: 需要读取索引状态的项目 ID。

    Returns:
        原始 node_id 到 fingerprint 的映射。
    """
    records = collection.get(where={"project_id": project_id}, include=["metadatas"])
    fingerprints: dict[str, str] = {}

    for metadata in records.get("metadatas", []) or []:
        if not isinstance(metadata, dict):
            continue

        node_id = metadata.get("node_id")
        fingerprint = metadata.get("fingerprint")

        if isinstance(node_id, str) and isinstance(fingerprint, str):
            fingerprints[node_id] = fingerprint

    return fingerprints


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


def sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> None:
    """按项目增量同步 ChromaDB 索引。

    该函数用于前端保存完整 graph 快照后。它会对比保存前后的节点指纹：
    新增或检索文档变化的节点执行 upsert，已删除的节点执行 delete。

    Args:
        project_id: 需要同步索引的项目 ID。
        old_nodes: 保存前的项目节点快照。
        new_nodes: SQLite 提交后的最新项目节点快照。
    """
    collection = get_chroma_collection()
    index_fingerprints = _read_index_fingerprints(collection, project_id)
    old_fingerprints = {node.id: build_node_fingerprint(node) for node in old_nodes}
    new_fingerprints = {node.id: build_node_fingerprint(node) for node in new_nodes}

    deleted_node_ids = sorted(set(old_fingerprints) - set(new_fingerprints))
    # 整图保存会重写 SQLite 行，但 ChromaDB 只删除真正从 payload 消失的节点。
    delete_nodes(collection, project_id, deleted_node_ids)

    for node in new_nodes:
        new_fingerprint = new_fingerprints[node.id]
        old_fingerprint = old_fingerprints.get(node.id)
        indexed_fingerprint = index_fingerprints.get(node.id)

        if old_fingerprint == new_fingerprint and indexed_fingerprint == new_fingerprint:
            # 坐标或排序变化不影响检索文档；索引已有相同 fingerprint 时跳过 embedding 更新。
            continue

        upsert_node(collection, node, new_fingerprint)


def sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> None:
    """同步单个节点到 ChromaDB。

    Args:
        node: SQLite 提交后的最新节点。
        old_fingerprint: 更新前的检索文档指纹；相同则可跳过写入。
    """
    new_fingerprint = build_node_fingerprint(node)
    collection = get_chroma_collection()

    if old_fingerprint == new_fingerprint:
        indexed_fingerprint = _read_index_fingerprints(collection, node.project_id).get(node.id)

        if indexed_fingerprint == new_fingerprint:
            return

        # 检索字段没变但索引记录缺失时，通常是用户清空了 ChromaDB 目录，需要按 SQLite 补写。

    upsert_node(collection, node, new_fingerprint)


def safe_sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> None:
    """安全同步项目索引。

    ChromaDB 同步失败时吞掉异常，避免可重建索引影响 SQLite 主数据保存。

    Args:
        project_id: 需要同步索引的项目 ID。
        old_nodes: 保存前的项目节点快照。
        new_nodes: SQLite 提交后的最新项目节点快照。
    """
    try:
        sync_project_index_incremental(project_id, old_nodes, new_nodes)
    except Exception:  # noqa: BLE001
        # SQLite 是主数据源，ChromaDB 失败最多导致本次向量结果为空或降级，不能回滚保存。
        return


def safe_sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> None:
    """安全同步单节点索引。

    Args:
        node: SQLite 提交后的最新节点。
        old_fingerprint: 更新前的检索文档指纹；相同则可跳过写入。
    """
    try:
        sync_node_index(node, old_fingerprint)
    except Exception:  # noqa: BLE001
        # 索引可从 SQLite 重建，因此这里保持失败隔离，保护用户创作数据。
        return
