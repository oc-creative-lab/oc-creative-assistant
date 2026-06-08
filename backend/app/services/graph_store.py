"""Graph application service.

This module is the service-layer orchestration entry point, responsible for
maintaining the transaction boundary of the project graph and synchronizing the
rebuildable vector index after SQLite commits. It does not directly handle HTTP
requests, nor does it decide the RAG prompt or retrieval strategy.
"""

import re

from fastapi import HTTPException

from app.db.database import SessionLocal, _ensure_subgraph_backfill
from app.db.models import EdgeORM, NodeORM, ProjectORM
from app.indexing.vector_store import delete_node as delete_node_vectors
from app.indexing.sync import (
    IndexingSyncResult,
    build_node_fingerprint,
    safe_sync_node_index,
    safe_sync_project_index_incremental,
)
from app.schemas import (
    EdgePayload,
    GraphPayload,
    IndexingStatusPayload,
    NodePayload,
    ProjectPayload,
    SaveGraphRequest,
    UpdateNodeRequest,
)
from app.services.graph_mappers import (
    api_meta_to_db,
    db_meta_to_api,
    db_status_to_api,
    db_tags_to_api,
    edge_to_orm,
    edge_to_payload,
    node_to_orm,
    node_to_payload,
    project_to_payload,
)
from app.services.graph_repository import (
    read_intra_graph_edges,
    read_ordered_edges,
    read_ordered_nodes,
    read_ordered_nodes_by_graph,
    read_project_node,
    read_project_nodes,
    replace_graph,
    replace_subgraph,
    require_graph,
    require_project,
)
from app.services.graph_seed import (
    DEFAULT_EDGES,
    DEFAULT_NODES,
    DEFAULT_PROJECT_DESCRIPTION,
    DEFAULT_PROJECT_ID,
    DEFAULT_PROJECT_NAME,
)
from app.services.graph_validation import validate_edge_endpoints_in_project


_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_LEGACY_DEFAULT_PROJECT_NAMES = frozenset(
    {
        "《咒术回战》涉谷站线",
        "咒术回战：涉谷站线",
        "Jujutsu Kaisen: The Shibuya Station Line",
        "Jujutsu Kaisen - Shibuya Station Line",
    }
)
_LEGACY_DEMO_NODE_IDS = frozenset(
    {
        "char-yuji-ticket",
        "char-gojo-stationmaster",
        "char-nobara-lostfound",
        "world-cursed-station",
        "world-ticket-curse",
        "world-announcement",
        "plot-last-train",
        "plot-ticket-awakening",
        "plot-final-transfer",
    }
)
_DEFAULT_SEED_NODE_IDS = frozenset(node.id for node in DEFAULT_NODES)
_DEFAULT_SEED_NODES_BY_ID = {node.id: node for node in DEFAULT_NODES}
_DEFAULT_SEED_EDGES_BY_ID = {edge.id: edge for edge in DEFAULT_EDGES}


def _contains_han(text: str | None) -> bool:
    return bool(text and _HAN_RE.search(text))


def _node_needs_locale_resync(node: NodeORM) -> bool:
    if _contains_han(node.title) or _contains_han(node.content) or _contains_han(node.type_label):
        return True
    return any(_contains_han(tag) for tag in db_tags_to_api(node.meta))


def _should_resync_default_locale(session, project_id: str) -> bool:
    """Re-seed the built-in demo graph when it still uses the old Chinese locale."""
    project = session.get(ProjectORM, project_id)
    if project is not None and project.name in _LEGACY_DEFAULT_PROJECT_NAMES:
        return True

    nodes = read_ordered_nodes(session, project_id)
    if not nodes:
        return False

    if project is not None and _contains_han(project.name):
        return True

    for node in nodes:
        if node.id in _DEFAULT_SEED_NODE_IDS and _node_needs_locale_resync(node):
            return True

    for edge in read_ordered_edges(session, project_id):
        if edge.id in _DEFAULT_SEED_EDGES_BY_ID and _contains_han(edge.label):
            return True

    return False


def _patch_legacy_seed_content(session, project_id: str) -> bool:
    """Upgrade known demo nodes/edges to the current English seed without wiping user additions."""
    changed = False
    project = session.get(ProjectORM, project_id)
    if project is not None and (
        project.name in _LEGACY_DEFAULT_PROJECT_NAMES or _contains_han(project.name)
    ):
        project.name = DEFAULT_PROJECT_NAME
        project.description = DEFAULT_PROJECT_DESCRIPTION
        changed = True

    for node in read_ordered_nodes(session, project_id):
        seed = _DEFAULT_SEED_NODES_BY_ID.get(node.id)
        if seed is None or not _node_needs_locale_resync(node):
            continue
        node.title = seed.title
        node.content = seed.content
        node.node_type = seed.nodeType or seed.type
        node.type_label = seed.typeLabel
        node.meta = api_meta_to_db(
            seed.meta,
            seed.tags,
            seed.status,
            existing_meta=node.meta,
        )
        changed = True

    for edge in read_ordered_edges(session, project_id):
        seed = _DEFAULT_SEED_EDGES_BY_ID.get(edge.id)
        if seed is None or not _contains_han(edge.label):
            continue
        edge.label = seed.label or "related"
        edge.relation_type = seed.relationType
        changed = True

    return changed


def _indexing_result_to_payload(result: IndexingSyncResult | None) -> IndexingStatusPayload:
    """Convert an index synchronization result into an API DTO.

    The main result of the save endpoint is still the graph; the indexing field is
    only responsible for telling the frontend whether embedding/ChromaDB is
    working.
    """
    if result is None:
        return IndexingStatusPayload()

    return IndexingStatusPayload(
        status=result.status,
        message=result.message,
        provider=result.provider,
        model=result.model,
        dimension=result.dimension,
        expected_nodes=result.expected_nodes,
        indexed_nodes=result.indexed_nodes,
        missing_node_ids=result.missing_node_ids,
        error=result.error,
    )


def ensure_default_project() -> ProjectPayload:
    """Ensure the default project exists.

    On first startup it writes the default project and the example graph; if only
    a project record exists but no nodes, it also backfills the example graph,
    repairing a half-initialized state.

    Returns:
        The default project DTO.
    """
    with SessionLocal.begin() as session:
        project = session.get(ProjectORM, DEFAULT_PROJECT_ID)

        if project is None:
            project = ProjectORM(
                id=DEFAULT_PROJECT_ID,
                name=DEFAULT_PROJECT_NAME,
                description=DEFAULT_PROJECT_DESCRIPTION,
            )
            session.add(project)
            session.flush()
            replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)
            payload = project_to_payload(project)
        else:
            has_nodes = read_ordered_nodes(session, DEFAULT_PROJECT_ID)
            node_ids = {node.id for node in has_nodes}
            if not has_nodes or node_ids == _LEGACY_DEMO_NODE_IDS:
                project.name = DEFAULT_PROJECT_NAME
                project.description = DEFAULT_PROJECT_DESCRIPTION
                replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)
            elif node_ids == _DEFAULT_SEED_NODE_IDS and _should_resync_default_locale(
                session, DEFAULT_PROJECT_ID
            ):
                project.name = DEFAULT_PROJECT_NAME
                project.description = DEFAULT_PROJECT_DESCRIPTION
                replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)
            elif _patch_legacy_seed_content(session, DEFAULT_PROJECT_ID):
                pass
            payload = project_to_payload(project)

    # The default project's example nodes are written by replace_graph without a graph_id; here we reuse the migration backfill
    # to create three sub-graphs for them and assign them by type, ensuring a fresh install's default project also conforms to the multi-sub-graph architecture.
    _ensure_subgraph_backfill()
    return payload


def get_project(project_id: str) -> ProjectPayload:
    """Read the basic information of a project.

    Args:
        project_id: The project ID.

    Returns:
        The project DTO.

    Raises:
        HTTPException: Raises 404 when the project does not exist.
    """
    with SessionLocal() as session:
        return project_to_payload(require_project(session, project_id))


def get_project_graph(project_id: str, indexing: IndexingStatusPayload | None = None) -> GraphPayload:
    """Read the project graph and convert it into a frontend DTO.

    Args:
        project_id: The project ID.

    Returns:
        A complete snapshot of the project, nodes, and edges.

    Raises:
        HTTPException: Raises 404 when the project does not exist.
    """
    with SessionLocal() as session:
        project = require_project(session, project_id)
        nodes = read_ordered_nodes(session, project_id)
        edges = read_ordered_edges(session, project_id)

        return GraphPayload(
            project=project_to_payload(project),
            nodes=[node_to_payload(node) for node in nodes],
            edges=[edge_to_payload(edge) for edge in edges],
            indexing=indexing or IndexingStatusPayload(),
        )


def save_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """Replace the entire project graph and incrementally sync the vector index after the transaction commits.

    Args:
        project_id: The project ID.
        payload: The frontend's current complete nodes/edges snapshot.

    Returns:
        The graph snapshot after the final database save.

    Raises:
        HTTPException: Raised when the project does not exist or an edge references
            an invalid node.
    """
    old_nodes = read_project_nodes(project_id)

    with SessionLocal.begin() as session:
        require_project(session, project_id)
        replace_graph(session, project_id, payload.nodes, payload.edges)

    # ChromaDB depends on the committed SQLite state, so it must be incrementally synced by fingerprint after the transaction completes.
    new_nodes = read_project_nodes(project_id)
    indexing_result = safe_sync_project_index_incremental(project_id, old_nodes, new_nodes)

    return get_project_graph(project_id, _indexing_result_to_payload(indexing_result))


def get_subgraph(graph_id: str, indexing: IndexingStatusPayload | None = None) -> GraphPayload:
    """Read a snapshot of a single sub-graph (nodes + intra-graph edges) and convert it into a frontend DTO.

    Reuses the GraphPayload structure: the project field holds the project this
    sub-graph belongs to, nodes contains only this sub-graph's nodes, and edges
    contains only edges whose both endpoints fall within this sub-graph.

    Raises:
        HTTPException: Raises 404 when the sub-graph does not exist.
    """
    with SessionLocal() as session:
        graph = require_graph(session, graph_id)
        project = require_project(session, graph.project_id)
        nodes = read_ordered_nodes_by_graph(session, graph_id)
        edges = read_intra_graph_edges(session, graph_id)

        return GraphPayload(
            project=project_to_payload(project),
            nodes=[node_to_payload(node) for node in nodes],
            edges=[edge_to_payload(edge) for edge in edges],
            indexing=indexing or IndexingStatusPayload(),
        )


def save_subgraph(graph_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """Replace the nodes and intra-graph edges of a single sub-graph as a whole, and incrementally sync the index after the transaction commits.

    The index is still incrementally synced at the project level (ChromaDB
    collections are project-scoped), keeping it consistent with single-canvas
    saving.

    Raises:
        HTTPException: Raised when the sub-graph does not exist or an edge
            references an invalid node.
    """
    with SessionLocal() as session:
        graph = require_graph(session, graph_id)
        project_id = graph.project_id

    old_nodes = read_project_nodes(project_id)

    with SessionLocal.begin() as session:
        graph = require_graph(session, graph_id)
        replace_subgraph(session, graph, payload.nodes, payload.edges)

    new_nodes = read_project_nodes(project_id)
    indexing_result = safe_sync_project_index_incremental(project_id, old_nodes, new_nodes)

    return get_subgraph(graph_id, _indexing_result_to_payload(indexing_result))


def create_node(project_id: str, node: NodePayload) -> NodePayload:
    """Create or overwrite a single node, and sync the vector index after commit.

    Args:
        project_id: The ID of the project the node belongs to.
        node: The node DTO submitted by the frontend.

    Returns:
        The saved node DTO.

    Raises:
        HTTPException: Raised when the project does not exist.
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        session.merge(node_to_orm(project_id, node, sort_order=0))

    latest_node = read_project_node(project_id, node.id)

    if latest_node is not None:
        safe_sync_node_index(latest_node)

    return node


def update_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """Update a node's basic content or position, and sync the vector index when the retrieval document changes.

    Args:
        project_id: The ID of the project the node belongs to.
        node_id: The ID of the node to update.
        payload: Partial update fields; a field of None means no modification.

    Returns:
        The updated node DTO.

    Raises:
        HTTPException: Raised when the project or node does not exist.
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            raise HTTPException(status_code=404, detail="Node not found")

        old_fingerprint = build_node_fingerprint(node)

        if payload.title is not None:
            node.title = payload.title
        if payload.content is not None:
            node.content = payload.content
        if payload.meta is not None:
            node.meta = api_meta_to_db(
                payload.meta,
                payload.tags,
                payload.status,
                existing_meta=node.meta,
            )
        if payload.typeLabel is not None:
            node.type_label = payload.typeLabel
        if payload.nodeType is not None:
            node.node_type = payload.nodeType
        if payload.tags is not None:
            node.meta = api_meta_to_db(
                db_meta_to_api(node.meta),
                payload.tags,
                db_status_to_api(node.meta),
            )
        if payload.status is not None:
            node.meta = api_meta_to_db(
                db_meta_to_api(node.meta),
                db_tags_to_api(node.meta),
                payload.status,
            )
        if payload.position is not None:
            node.position_x = payload.position.x
            node.position_y = payload.position.y

        updated = node_to_payload(node)

    # Index synchronization must use the committed state, to avoid ChromaDB and SQLite diverging on a failed rollback.
    latest_node = read_project_node(project_id, node_id)
    if latest_node is not None:
        safe_sync_node_index(latest_node, old_fingerprint)

    return updated


def delete_node(project_id: str, node_id: str) -> None:
    """Delete a single node and its related edges, and clean up the vector index (revision 1: inline chat card "undo/reject").

    Raises:
        HTTPException: Raises 404 when the project or node does not exist.
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        node = session.get(NodeORM, node_id)
        if node is None or node.project_id != project_id:
            raise HTTPException(status_code=404, detail="Node not found")

        session.query(EdgeORM).filter(
            EdgeORM.project_id == project_id,
            (EdgeORM.source == node_id) | (EdgeORM.target == node_id),
        ).delete(synchronize_session=False)
        session.delete(node)

    # Index cleanup is performed after the transaction commits, consistent with the existing _sync_deletions semantics.
    try:
        delete_node_vectors(project_id, node_id)
    except Exception:  # noqa: BLE001 - index cleanup failure should not block deletion
        pass


def create_edge(project_id: str, edge: EdgePayload) -> EdgePayload:
    """Create or overwrite a single edge, and validate that both endpoint nodes belong to the same project.

    Args:
        project_id: The ID of the project the edge belongs to.
        edge: The edge DTO submitted by the frontend.

    Returns:
        The saved edge DTO.

    Raises:
        HTTPException: Raised when the project does not exist or the edge endpoints
            do not belong to the same project.
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        validate_edge_endpoints_in_project(session, project_id, edge.source, edge.target)
        session.merge(edge_to_orm(project_id, edge, sort_order=0))

    return edge


def delete_edge(project_id: str, edge_id: str) -> None:
    """Delete a single edge by id within a project."""
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        edge = session.get(EdgeORM, edge_id)
        if edge is None or edge.project_id != project_id:
            raise HTTPException(status_code=404, detail="Edge not found")
        session.delete(edge)
