"""RAG 索引同步策略。

SQLite 是主数据源，Chroma 只是可重建的检索索引。本模块负责在 SQLite
事务提交后，根据检索文档 fingerprint 做项目级增量同步，避免每次 RAG 查询
都全量 upsert，也避免节点拖动这类非检索字段变化触发 embedding 更新。
"""

from __future__ import annotations

import hashlib

from models import NodeORM

from rag.document_loader import _node_to_document
from rag.vector_store import delete_nodes, get_chroma_collection, upsert_node


def _read_index_fingerprints(collection, project_id: str) -> dict[str, str]:
    """读取当前项目已经写入 Chroma 的 fingerprint。

    输入是 Chroma collection 和项目 id；返回原始 node_id 到 fingerprint 的映射。
    这里只读索引，不修改 Chroma，用来判断记录是否缺失或需要补写。
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

    入参 node 是 ORM 节点；返回 sha256 十六进制字符串。fingerprint 只基于
    node.id、node_type、title、content、tags 等会进入检索文档的信息，
    不包含 position、sort_order、created_at、updated_at。
    """
    # node.id 不一定进入 embedding 文档展示，但 fingerprint 必须包含它，避免同内容不同节点被误判为同一记录。
    document = f"ID: {node.id}\n{_node_to_document(node)}"
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> None:
    """按项目增量同步 Chroma 索引。

    old_nodes 是保存前的项目节点，new_nodes 是 SQLite 提交后的最新项目节点。
    该函数会修改 Chroma：新增/检索文档变化的节点 upsert，被删除的节点 delete。
    """
    collection = get_chroma_collection()
    index_fingerprints = _read_index_fingerprints(collection, project_id)
    old_fingerprints = {node.id: build_node_fingerprint(node) for node in old_nodes}
    new_fingerprints = {node.id: build_node_fingerprint(node) for node in new_nodes}

    deleted_node_ids = sorted(set(old_fingerprints) - set(new_fingerprints))
    # 整图保存会重写 SQLite 行，但不能无脑重建 Chroma；只删真正从 payload 消失的节点。
    delete_nodes(collection, project_id, deleted_node_ids)

    for node in new_nodes:
        new_fingerprint = new_fingerprints[node.id]
        old_fingerprint = old_fingerprints.get(node.id)
        indexed_fingerprint = index_fingerprints.get(node.id)

        if old_fingerprint == new_fingerprint and indexed_fingerprint == new_fingerprint:
            # 只移动节点或 sort_order 变化不会影响检索文档，跳过 embedding 更新。
            # 但如果用户手动删除了 chroma 目录，索引里没有对应 fingerprint，就必须补写。
            continue

        upsert_node(collection, node, new_fingerprint)


def sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> None:
    """同步单个节点到 Chroma。

    node 是 SQLite 提交后的最新节点；old_fingerprint 可选。若新旧 fingerprint
    相同，说明只改了位置等非检索字段，不更新 Chroma。
    """
    new_fingerprint = build_node_fingerprint(node)
    collection = get_chroma_collection()

    if old_fingerprint == new_fingerprint:
        indexed_fingerprint = _read_index_fingerprints(collection, node.project_id).get(node.id)

        if indexed_fingerprint == new_fingerprint:
            return

        # 检索字段没变但索引记录缺失时，通常是用户清空了 Chroma；此时需要按 SQLite 补写索引。

    upsert_node(collection, node, new_fingerprint)


def safe_sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> None:
    """安全同步项目索引。

    Chroma 同步失败时吞掉异常，避免可重建索引影响 SQLite 主数据保存。
    """
    try:
        sync_project_index_incremental(project_id, old_nodes, new_nodes)
    except Exception:  # noqa: BLE001
        # SQLite 是主数据源，Chroma 失败最多导致本次向量结果为空或降级，不能 rollback 保存。
        return


def safe_sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> None:
    """安全同步单节点索引；Chroma 失败不影响 SQLite 已提交数据。"""
    try:
        sync_node_index(node, old_fingerprint)
    except Exception:  # noqa: BLE001
        # 索引可从 SQLite 重建，因此这里保持失败隔离，保护用户创作数据。
        return
