"""Graph database operation helpers.

This module is the persistence boundary between the service layer and the ORM,
responsible for reading and writing projects, nodes, and edges in the database.
It does not handle HTTP requests, nor does it trigger ChromaDB synchronization;
external side effects are executed by the service orchestration layer after the
transaction commits.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import EdgeORM, GraphORM, NodeORM, ProjectORM
from app.schemas import EdgePayload, NodePayload
from app.services.graph_mappers import edge_to_orm, node_to_orm
from app.services.graph_validation import validate_edges_against_payload_nodes


def require_project(session: Session, project_id: str) -> ProjectORM:
    """Read a project and ensure it exists.

    Args:
        session: The current database session.
        project_id: The project ID.

    Returns:
        The matching project ORM object.

    Raises:
        HTTPException: Raised when the project does not exist.
    """
    project = session.get(ProjectORM, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


def read_ordered_nodes(session: Session, project_id: str) -> list[NodeORM]:
    """Read project nodes ordered by the canvas save order.

    Args:
        session: The current database session.
        project_id: The project ID.

    Returns:
        The list of node ORM objects for the current project.
    """
    return session.scalars(
        select(NodeORM)
        .where(NodeORM.project_id == project_id)
        .order_by(NodeORM.sort_order, NodeORM.created_at)
    ).all()


def read_ordered_edges(session: Session, project_id: str) -> list[EdgeORM]:
    """Read project edges ordered by the canvas save order.

    Args:
        session: The current database session.
        project_id: The project ID.

    Returns:
        The list of edge ORM objects for the current project.
    """
    return session.scalars(
        select(EdgeORM)
        .where(EdgeORM.project_id == project_id)
        .order_by(EdgeORM.sort_order, EdgeORM.created_at)
    ).all()


def read_project_nodes(project_id: str) -> list[NodeORM]:
    """Read a snapshot of the project nodes.

    This function opens an independent session so the service layer can compare
    vector index fingerprints outside the SQLite transaction.

    Args:
        project_id: The project ID.

    Returns:
        The list of node ORM objects for the current project.
    """
    with SessionLocal() as session:
        return read_ordered_nodes(session, project_id)


def read_project_node(project_id: str, node_id: str) -> NodeORM | None:
    """Read a snapshot of a single node.

    This function re-reads the node after the transaction commits, ensuring that
    index synchronization uses the state already persisted in SQLite.

    Args:
        project_id: The project ID.
        node_id: The node ID.

    Returns:
        The matching node ORM; returns None when the node does not exist or does
        not belong to the project.
    """
    with SessionLocal() as session:
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            return None

        return node


def replace_graph(
    session: Session,
    project_id: str,
    nodes: list[NodePayload],
    edges: list[EdgePayload],
) -> None:
    """Replace the entire project graph within the current transaction.

    The save strategy is based on a complete snapshot: first validate that edge
    endpoints only reference nodes from this submission, then delete the old edges
    and old nodes, and finally write the new nodes and new edges in submission
    order.

    Args:
        session: The current database transaction session.
        project_id: The project ID.
        nodes: The complete list of nodes to save this time.
        edges: The complete list of edges to save this time.

    Raises:
        HTTPException: Raised when an edge references a node outside the current
            graph.
    """
    validate_edges_against_payload_nodes(nodes, edges)
    # The SQLite foreign key constraint prevents deleting nodes still referenced by edges, so edges must be deleted first during replacement.
    session.query(EdgeORM).filter(EdgeORM.project_id == project_id).delete(synchronize_session=False)
    session.query(NodeORM).filter(NodeORM.project_id == project_id).delete(synchronize_session=False)

    for index, node in enumerate(nodes):
        session.add(node_to_orm(project_id, node, index))

    for index, edge in enumerate(edges):
        session.add(edge_to_orm(project_id, edge, index))


# --- sub-graph level operations (first_revision decision 1) ---


def require_graph(session: Session, graph_id: str) -> GraphORM:
    """Read a sub-graph and ensure it exists.

    Raises:
        HTTPException: Raises 404 when the sub-graph does not exist.
    """
    graph = session.get(GraphORM, graph_id)

    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")

    return graph


def read_ordered_nodes_by_graph(session: Session, graph_id: str) -> list[NodeORM]:
    """Read the nodes of a sub-graph, ordered by the canvas save order."""
    return session.scalars(
        select(NodeORM)
        .where(NodeORM.graph_id == graph_id)
        .order_by(NodeORM.sort_order, NodeORM.created_at)
    ).all()


def read_intra_graph_edges(session: Session, graph_id: str) -> list[EdgeORM]:
    """Read edges whose both endpoints fall within this sub-graph.

    Phase 1 only handles intra-sub-graph edges; cross-sub-graph edges are
    introduced in phase 6.
    """
    node_ids = {
        node_id
        for (node_id,) in session.execute(
            select(NodeORM.id).where(NodeORM.graph_id == graph_id)
        ).all()
    }
    if not node_ids:
        return []

    return session.scalars(
        select(EdgeORM)
        .where(EdgeORM.source.in_(node_ids), EdgeORM.target.in_(node_ids))
        .order_by(EdgeORM.sort_order, EdgeORM.created_at)
    ).all()


def read_graph_nodes(graph_id: str) -> list[NodeORM]:
    """Read a sub-graph node snapshot in an independent session, for comparing index fingerprints outside the transaction."""
    with SessionLocal() as session:
        return read_ordered_nodes_by_graph(session, graph_id)


def replace_subgraph(
    session: Session,
    graph: GraphORM,
    nodes: list[NodePayload],
    edges: list[EdgePayload],
) -> None:
    """Replace the nodes and intra-graph edges of a sub-graph as a whole.

    Structurally identical to ``replace_graph``, but the scope is narrowed to a
    single sub-graph: it only deletes/writes nodes belonging to this sub-graph and
    edges whose both endpoints fall within this sub-graph, without affecting other
    sub-graphs under the project.
    """
    validate_edges_against_payload_nodes(nodes, edges)

    old_node_ids = {
        node_id
        for (node_id,) in session.execute(
            select(NodeORM.id).where(NodeORM.graph_id == graph.id)
        ).all()
    }
    # Delete intra-graph edges first (the foreign key constraint prevents deleting nodes still referenced by edges), then delete nodes.
    if old_node_ids:
        session.query(EdgeORM).filter(
            EdgeORM.source.in_(old_node_ids), EdgeORM.target.in_(old_node_ids)
        ).delete(synchronize_session=False)
    session.query(NodeORM).filter(NodeORM.graph_id == graph.id).delete(
        synchronize_session=False
    )

    for index, node in enumerate(nodes):
        session.add(node_to_orm(graph.project_id, node, index, graph_id=graph.id))

    for index, edge in enumerate(edges):
        session.add(edge_to_orm(graph.project_id, edge, index))
