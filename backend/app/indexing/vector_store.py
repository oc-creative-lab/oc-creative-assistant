"""ChromaDB vector store wrapper.

Responsible only for ChromaDB collection initialization, project-isolation
id/metadata conventions, and node document upsert/delete/query. Embedding
computation and provider selection are handled by
``app.indexing.embedding_provider``; index synchronization timing is decided by
``app.indexing.sync``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db.models import NodeORM
from app.indexing.config import (
    CHROMA_PATH,
    COLLECTION_BY_NODE_TYPE,
    DEFAULT_COLLECTION_NAME,
    INDEXING_DEBUG_LOG,
)
from app.indexing.document_loader import node_to_document
from app.indexing.embedding_provider import (
    embed_query,
    embedding_provider,
    get_embedding_signature,
)


logger = logging.getLogger(__name__)


def _log(message: str) -> None:
    """Print vector write info to make the real execution path observable during the PoC phase."""
    if INDEXING_DEBUG_LOG:
        print(f"[vector-store] {message}", flush=True)


def build_chroma_id(project_id: str, node_id: str) -> str:
    """Build a ChromaDB record ID.

    Args:
        project_id: The ID of the project the node belongs to.
        node_id: The node ID.

    Returns:
        A stable record ID composed of project and node, preventing same-named nodes from different projects from overwriting each other.
    """
    return f"{project_id}:{node_id}"


def _resolve_collection_name(node_type: str) -> str:
    """Route to the target collection name based on node_type, falling back to the default collection on a miss."""
    return COLLECTION_BY_NODE_TYPE.get(node_type, DEFAULT_COLLECTION_NAME)


def _all_collection_names() -> tuple[str, ...]:
    """Return all collection names that need to be managed, including the default collection."""
    return (*COLLECTION_BY_NODE_TYPE.values(), DEFAULT_COLLECTION_NAME)


def _build_chroma_client() -> Any:
    """Initialize the ChromaDB PersistentClient.

    Raises:
        RuntimeError: Raised when ChromaDB is not installed.
    """
    try:
        import chromadb
    except ImportError as error:
        raise RuntimeError("ChromaDB is not installed; cannot write to or query the vector index.") from error

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


_chroma_client_singleton: Any | None = None


def _get_chroma_client() -> Any:
    """Process-level singleton.
    """
    global _chroma_client_singleton
    if _chroma_client_singleton is None:
        _chroma_client_singleton = _build_chroma_client()
    return _chroma_client_singleton


def get_chroma_collection_by_name(name: str) -> Any:
    """Get a collection by name, auto-creating it with cosine distance if it does not exist."""
    client = _get_chroma_client()
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})


def get_chroma_collection_for_node(node_type: str) -> Any:
    """Route to the corresponding collection by node_type; the caller does not need to worry about naming."""
    return get_chroma_collection_by_name(_resolve_collection_name(node_type))


def get_all_chroma_collections() -> dict[str, Any]:
    """Return all collections, used for cross-collection scans (sync status reads / full Lore Memory retrieval)."""
    return {name: get_chroma_collection_by_name(name) for name in _all_collection_names()}


def upsert_node(node: NodeORM, fingerprint: str | None = None) -> None:
    """Write by routing to the corresponding collection based on node_type.

    Uses a self-heal pattern: before writing to the target collection, delete the
    same chroma_id from other collections, ensuring that when a node's type changes
    it does not exist in multiple collections simultaneously; the caller does not
    need to track old_node_type.

    Args:
        node: The latest node committed to SQLite.
        fingerprint: The retrieval document fingerprint; computed from the current document when None.
    """
    document = node_to_document(node)
    node_fingerprint = fingerprint or hashlib.sha256(f"ID: {node.id}\n{document}".encode("utf-8")).hexdigest()
    chroma_id = build_chroma_id(node.project_id, node.id)
    target_name = _resolve_collection_name(node.node_type)

    # Self-heal: remove the same chroma_id from non-target collections to handle migration when the node type changes
    for name in _all_collection_names():
        if name == target_name:
            continue
        get_chroma_collection_by_name(name).delete(ids=[chroma_id])

    _log(f"upsert vector collection={target_name} chroma_id={chroma_id} node_id={node.id} title={node.title!r}")
    target_collection = get_chroma_collection_by_name(target_name)
    target_collection.upsert(
        ids=[chroma_id],
        documents=[document],
        embeddings=[embedding_provider.embed(document)],
        metadatas=[
            {
                "project_id": node.project_id,
                "node_id": node.id,
                "node_type": node.node_type,
                "title": node.title,
                "fingerprint": node_fingerprint,
                "embedding_signature": get_embedding_signature(),
            }
        ],
    )
    _log(f"upsert vector success chroma_id={chroma_id}")


def upsert_nodes(nodes: list[NodeORM]) -> None:
    """Batch-write nodes; no longer passes collection, routing internally by node_type."""
    for node in nodes:
        upsert_node(node)


def delete_node(project_id: str, node_id: str) -> None:
    """Delete the specified chroma_id from all collections, without needing to know the node type in advance."""
    chroma_id = build_chroma_id(project_id, node_id)
    for name in _all_collection_names():
        get_chroma_collection_by_name(name).delete(ids=[chroma_id])


def delete_nodes(project_id: str, node_ids: list[str]) -> None:
    """Batch-delete the specified list of chroma_ids from all collections."""
    if not node_ids:
        return

    _log(f"delete vectors project_id={project_id} node_ids={node_ids}")
    chroma_ids = [build_chroma_id(project_id, node_id) for node_id in node_ids]
    for name in _all_collection_names():
        get_chroma_collection_by_name(name).delete(ids=chroma_ids)

def query_collection(
    collection: Any,
    project_id: str,
    query: str,
    top_k: int,
    query_embedding: list[float] | None = None,
) -> tuple[list[str], list[dict], list[float]]:
    """Perform a project-level query within the specified collection.

    Collections are already physically isolated by node_type, so a node_type
    metadata filter is no longer needed; the project_id filter is still kept to
    prevent cross-project data from leaking into the current prompt.

    When the same query is used across multiple collections, the caller should
    precompute query_embedding once with ``embedding_provider.embed`` and pass it
    in, avoiding recomputing the same vector for each collection and cutting the
    embedding API calls from N down to 1.

    Args:
        collection: The specific collection already routed by node_type.
        project_id: The current project ID.
        query: The retrieval query, used for embedding only when query_embedding is not provided.
        top_k: The maximum number of contexts expected to be returned.
        query_embedding: A precomputed query vector; if not passed, it is embedded once internally.

    Returns:
        A list of ChromaDB IDs, a list of metadata, and a list of distances.
    """
    total = collection.count()
    if total == 0:
        _log(f"query skipped collection={collection.name} reason=empty_collection")
        return [], [], []

    _log(f"query vectors collection={collection.name} project_id={project_id} top_k={top_k} total={total}")
    embedding = query_embedding if query_embedding is not None else embed_query(query)
    result = collection.query(
        query_embeddings=[embedding],
        # +1 leaves room for the current node itself, to be filtered by the caller as needed; clamp to total to avoid Chroma raising an out-of-range parameter error
        n_results=min(top_k + 1, total),
        where={"project_id": project_id},
        include=["metadatas", "distances"],
    )
    return (
        result.get("ids", [[]])[0],
        result.get("metadatas", [[]])[0],
        result.get("distances", [[]])[0],
    )
