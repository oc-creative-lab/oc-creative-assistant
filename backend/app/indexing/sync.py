"""Index synchronization strategy from SQLite to ChromaDB.

SQLite is the primary data source; ChromaDB is a rebuildable retrieval index.
This module is responsible for performing project-level or node-level incremental
synchronization based on retrieval document fingerprints after a SQLite
transaction commits.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.db.models import NodeORM
from app.indexing.config import INDEXING_DEBUG_LOG
from app.indexing.document_loader import node_to_document
from app.indexing.vector_store import (
    delete_nodes,
    get_all_chroma_collections,
    get_embedding_signature,
    upsert_node,
)


def _log(message: str) -> None:
    """Print index synchronization debug info.
    """
    if INDEXING_DEBUG_LOG:
        print(f"[index-sync] {message}", flush=True)


@dataclass
class IndexingSyncResult:
    """Vector index synchronization result.

    Saving to SQLite is the main flow; this result only describes whether
    ChromaDB/embedding synchronized successfully, for the API to return as a hint to the frontend.
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
    """Build a unified index status, centrally filling in the current embedding configuration."""
    from app.indexing.embedding_provider import embedding_provider

    return IndexingSyncResult(
        status=status,
        message=message,
        provider=embedding_provider.name,
        model=embedding_provider.model,
        dimension=embedding_provider.dimension,
        expected_nodes=expected_nodes,
        error=error,
    )


def _read_index_state(project_id: str) -> dict[str, dict[str, str]]:
    """Read the fingerprints already written for the current project across all collections.

    Merged across collections into a single dict, because under Plan A the same
    node_id always belongs to only one collection (guaranteed by upsert_node's
    self-heal), so there are no duplicate keys.

    Args:
        project_id: The project ID whose index state should be read.

    Returns:
        A mapping from node_id to fingerprint / embedding_signature.
    """
    index_state: dict[str, dict[str, str]] = {}

    for collection in get_all_chroma_collections().values():
        records = collection.get(where={"project_id": project_id}, include=["metadatas"])

        for metadata in records.get("metadatas", []) or []:
            if not isinstance(metadata, dict):
                continue

            node_id = metadata.get("node_id")
            fingerprint = metadata.get("fingerprint")
            embedding_signature = metadata.get("embedding_signature")

            if isinstance(node_id, str) and isinstance(fingerprint, str):
                index_state[node_id] = {
                    "fingerprint": fingerprint,
                    "embedding_signature": embedding_signature if isinstance(embedding_signature, str) else "",
                }

    return index_state


def build_node_fingerprint(node: NodeORM) -> str:
    """Compute the retrieval document fingerprint of a node.

    The fingerprint is based only on information that goes into the retrieval
    document; it does not include position, sort_order, created_at, or updated_at,
    so dragging a node does not trigger an embedding update.

    Args:
        node: The ORM node whose fingerprint should be computed.

    Returns:
        A sha256 hexadecimal string.
    """
    # node.id does not necessarily go into the display document, but it must participate in the fingerprint to avoid different nodes with identical content being mistaken for the same record.
    document = f"ID: {node.id}\n{node_to_document(node)}"
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


def verify_project_index(project_id: str, nodes: list[NodeORM]) -> IndexingSyncResult:
    """Check whether all nodes of the current project have been written to their corresponding collection.

    Args:
        project_id: The current project ID.
        nodes: The latest node snapshot after the SQLite commit.

    Returns:
        A synchronization result describing the indexed count, missing nodes, and the current embedding configuration.
    """
    index_state = _read_index_state(project_id)
    embedding_signature = get_embedding_signature()
    missing_node_ids: list[str] = []

    for node in nodes:
        indexed_node = index_state.get(node.id, {})

        if (
            indexed_node.get("fingerprint") != build_node_fingerprint(node)
            or indexed_node.get("embedding_signature") != embedding_signature
        ):
            missing_node_ids.append(node.id)

    result = _base_result(
        status="synced" if not missing_node_ids else "partial",
        message="Vector index is synchronized" if not missing_node_ids else "Some nodes have not yet been successfully written to the vector index",
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
    """Incrementally synchronize the ChromaDB index per project.

    This function is used after the frontend saves a full graph snapshot. It
    compares node fingerprints before and after the save: nodes that are new or
    whose retrieval document changed are upserted, and deleted nodes are deleted.

    Args:
        project_id: The project ID whose index should be synchronized.
        old_nodes: The project node snapshot before saving.
        new_nodes: The latest project node snapshot after the SQLite commit.
    """
    index_state = _read_index_state(project_id)
    embedding_signature = get_embedding_signature()
    old_fingerprints = {node.id: build_node_fingerprint(node) for node in old_nodes}
    new_fingerprints = {node.id: build_node_fingerprint(node) for node in new_nodes}
    _log(
        "start project sync "
        f"project_id={project_id} old_nodes={len(old_nodes)} new_nodes={len(new_nodes)} "
        f"indexed_records={len(index_state)} signature={embedding_signature}"
    )

    deleted_node_ids = sorted(set(old_fingerprints) - set(new_fingerprints))
    # A full-graph save rewrites SQLite rows, but ChromaDB only deletes nodes that have actually disappeared from the payload.
    delete_nodes(project_id, deleted_node_ids)

    if deleted_node_ids:
        _log(f"delete stale vectors node_ids={deleted_node_ids}")

    for node in new_nodes:
        new_fingerprint = new_fingerprints[node.id]
        old_fingerprint = old_fingerprints.get(node.id)
        indexed_node = index_state.get(node.id, {})
        indexed_fingerprint = indexed_node.get("fingerprint")
        indexed_embedding_signature = indexed_node.get("embedding_signature")
        update_reasons: list[str] = []

        if old_fingerprint is None:
            update_reasons.append("new_node")
        elif old_fingerprint != new_fingerprint:
            update_reasons.append("document_changed")

        if indexed_fingerprint != new_fingerprint:
            update_reasons.append("missing_or_stale_vector")

        if indexed_embedding_signature != embedding_signature:
            update_reasons.append("embedding_signature_changed")

        # Skip only when both the document fingerprint and the embedding config signature match; after switching model or dimension, vectors need to be rewritten.
        if (
            old_fingerprint == new_fingerprint
            and indexed_fingerprint == new_fingerprint
            and indexed_embedding_signature == embedding_signature
        ):
            # Coordinate or ordering changes do not affect the retrieval document; skip the embedding update when the index already has the same fingerprint.
            _log(f"skip node_id={node.id} reason=fingerprint_and_embedding_signature_unchanged")
            continue

        _log(f"upsert node_id={node.id} reasons={','.join(update_reasons) or 'unknown'}")
        upsert_node(node, new_fingerprint)

    result = verify_project_index(project_id, new_nodes)
    _log(
        "finish project sync "
        f"status={result.status} indexed={result.indexed_nodes}/{result.expected_nodes} "
        f"missing={result.missing_node_ids}"
    )
    return result


def sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> IndexingSyncResult:
    """Synchronize a single node to ChromaDB.

    Args:
        node: The latest node after the SQLite commit.
        old_fingerprint: The retrieval document fingerprint before the update; if identical, the write can be skipped.
    """
    new_fingerprint = build_node_fingerprint(node)
    _log(f"start node sync project_id={node.project_id} node_id={node.id}")

    if old_fingerprint == new_fingerprint:
        indexed_node = _read_index_state(node.project_id).get(node.id, {})
        indexed_fingerprint = indexed_node.get("fingerprint")
        indexed_embedding_signature = indexed_node.get("embedding_signature")

        # When the retrieval document is unchanged, also confirm the index was written by the current embedding config; otherwise old-model vectors would get mixed in.
        if indexed_fingerprint == new_fingerprint and indexed_embedding_signature == get_embedding_signature():
            result = _base_result("synced", "Vector index is synchronized", expected_nodes=1)
            result.indexed_nodes = 1
            _log(f"skip node_id={node.id} reason=fingerprint_and_embedding_signature_unchanged")
            return result

        # When retrieval fields are unchanged but the index record is missing, the user usually cleared the ChromaDB directory, so it must be backfilled from SQLite.
        _log(f"upsert node_id={node.id} reason=vector_missing_or_embedding_signature_changed")
    else:
        _log(f"upsert node_id={node.id} reason=document_changed")

    upsert_node(node, new_fingerprint)
    result = verify_project_index(node.project_id, [node])
    _log(f"finish node sync node_id={node.id} status={result.status} indexed={result.indexed_nodes}/1")
    return result


def safe_sync_project_index_incremental(
    project_id: str,
    old_nodes: list[NodeORM],
    new_nodes: list[NodeORM],
) -> IndexingSyncResult:
    """Safely synchronize the project index.

    When ChromaDB synchronization fails, swallow the exception so that the
    rebuildable index does not affect saving the primary SQLite data.

    Args:
        project_id: The project ID whose index should be synchronized.
        old_nodes: The project node snapshot before saving.
        new_nodes: The latest project node snapshot after the SQLite commit.
    """
    try:
        return sync_project_index_incremental(project_id, old_nodes, new_nodes)
    except Exception as error:  # noqa: BLE001
        # SQLite is the primary data source; a ChromaDB/embedding failure must not roll back the save. The error is returned to the frontend to prompt the user to fix the config.
        _log(f"project sync failed project_id={project_id} error={error}")
        result = _base_result(
            status="failed",
            message="Saved to SQLite, but writing the embedding vector index failed",
            expected_nodes=len(new_nodes),
            error=str(error),
        )
        try:
            # Even if this sync failed, still try to read the current ChromaDB state to tell the frontend which nodes already have usable vectors.
            verified = verify_project_index(project_id, new_nodes)
            result.indexed_nodes = verified.indexed_nodes
            result.missing_node_ids = verified.missing_node_ids
        except Exception:  # noqa: BLE001
            result.missing_node_ids = [node.id for node in new_nodes]
        return result


def safe_sync_node_index(node: NodeORM, old_fingerprint: str | None = None) -> IndexingSyncResult:
    """Safely synchronize a single-node index.

    Args:
        node: The latest node after the SQLite commit.
        old_fingerprint: The retrieval document fingerprint before the update; if identical, the write can be skipped.
    """
    try:
        return sync_node_index(node, old_fingerprint)
    except Exception as error:  # noqa: BLE001
        # The index can be rebuilt from SQLite, so keep failure isolation here while returning the error to the caller.
        _log(f"node sync failed node_id={node.id} error={error}")
        result = _base_result(
            status="failed",
            message="Saved to SQLite, but writing this node's embedding vector failed",
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
