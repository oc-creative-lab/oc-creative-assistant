"""Graph DTO <-> ORM conversion.

This module is the data-mapping boundary of the service layer, responsible for
converting between API payloads and SQLAlchemy ORM, and for maintaining the
compatibility rules of the node meta JSON. It does not access the database, nor
does it trigger index sync.
"""

from __future__ import annotations

from typing import Any

from app.db.models import EdgeORM, NodeORM, ProjectORM
from app.indexing.config import DEFAULT_NODE_STATUS
from app.schemas import (
    EdgePayload,
    EdgeWaypointPayload,
    NodePayload,
    PositionPayload,
    ProjectPayload,
)


META_TEXT_KEY = "text"
META_TAGS_KEY = "tags"
META_STATUS_KEY = "status"
# first_revision decision 2: reserved key for storing a character card's "free
# fields" into the node.meta JSON, without polluting the existing text / tags /
# status.
META_FIELDS_KEY = "fields"
META_PARENT_ID_KEY = "parentId"
META_SORT_ORDER_KEY = "sortOrder"


def db_fields_to_api(meta: Any) -> dict[str, str]:
    """Read free fields from the database meta (key -> value, all strings)."""
    if isinstance(meta, dict):
        fields = meta.get(META_FIELDS_KEY, {})
        if isinstance(fields, dict):
            return {str(k): str(v) for k, v in fields.items()}
    return {}


def merge_fields_into_meta(meta: Any, fields: dict[str, str]) -> dict[str, Any]:
    """Write the free fields back into the meta JSON as a whole, preserving other reserved keys."""
    stored_meta: dict[str, Any] = meta if isinstance(meta, dict) else {}
    next_meta = dict(stored_meta)
    next_meta[META_FIELDS_KEY] = {str(k): str(v) for k, v in fields.items()}
    return next_meta


def project_to_payload(project: ProjectORM) -> ProjectPayload:
    """Convert a project ORM into an API payload.

    Args:
        project: The project record in the database.

    Returns:
        The project DTO used by the frontend interface.
    """
    return ProjectPayload(id=project.id, name=project.name)


def node_to_payload(node: NodeORM) -> NodePayload:
    """Convert a node ORM into an API payload.

    This function is compatible with both the legacy string meta and the current
    JSON meta, ensuring the frontend still receives stable `meta`, `tags`, and
    `status` fields.

    Args:
        node: The node record in the database.

    Returns:
        The node DTO used by the frontend interface.
    """
    return NodePayload(
        id=node.id,
        type=node.node_type,
        nodeType=node.node_type,
        title=node.title,
        content=node.content,
        meta=db_meta_to_api(node.meta),
        typeLabel=node.type_label,
        tags=db_tags_to_api(node.meta),
        status=db_status_to_api(node.meta),
        parentId=db_parent_id_to_api(node.meta),
        sortOrder=db_sort_order_to_api(node.meta),
        position=PositionPayload(x=node.position_x, y=node.position_y),
    )


def edge_to_payload(edge: EdgeORM) -> EdgePayload:
    """Convert an edge ORM into an API payload."""
    waypoint = (
        EdgeWaypointPayload.model_validate(edge.waypoint) if edge.waypoint else None
    )
    return EdgePayload(
        id=edge.id,
        source=edge.source,
        target=edge.target,
        label=edge.label or "related",
        relationType=edge.relation_type or "relates_to",
        sourceHandle=edge.source_handle,
        targetHandle=edge.target_handle,
        type=edge.edge_type,
        animated=edge.animated,
        waypoint=waypoint,
    )


def node_to_orm(
    project_id: str,
    node: NodePayload,
    sort_order: int,
    graph_id: str | None = None,
) -> NodeORM:
    """Convert a node payload into an ORM.

    Args:
        project_id: The ID of the project the node belongs to.
        node: The node DTO submitted by the frontend.
        sort_order: The node's order within the current graph snapshot.
        graph_id: The sub-graph the node belongs to; None when saving at the
            project level, passed in by the caller when saving at the sub-graph
            level (first_revision decision 1).

    Returns:
        A node ORM object ready to be written to the database.
    """
    return NodeORM(
        id=node.id,
        project_id=project_id,
        graph_id=graph_id,
        node_type=node.nodeType or node.type,
        title=node.title,
        content=node.content,
        meta=api_meta_to_db(
            node.meta,
            node.tags,
            node.status,
            parent_id=node.parentId,
            sort_order=node.sortOrder,
        ),
        type_label=node.typeLabel,
        position_x=node.position.x,
        position_y=node.position.y,
        sort_order=sort_order,
    )


def edge_to_orm(project_id: str, edge: EdgePayload, sort_order: int) -> EdgeORM:
    """Convert an edge payload into an ORM."""
    return EdgeORM(
        id=edge.id,
        project_id=project_id,
        source=edge.source,
        target=edge.target,
        label=edge.label or "related",
        source_handle=edge.sourceHandle,
        target_handle=edge.targetHandle,
        edge_type=edge.type,
        relation_type=edge.relationType,
        animated=edge.animated,
        waypoint=edge.waypoint.model_dump() if edge.waypoint else None,
        sort_order=sort_order,
    )


def api_meta_to_db(
    meta: str,
    tags: list[str] | None = None,
    status: str | None = None,
    existing_meta: Any | None = None,
    parent_id: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    """Merge API meta fields into the database JSON.

    The API still keeps the string `meta` field; the database uses JSON to store
    the body, tags, and sync status together, avoiding extending the table schema
    at the current PoC stage.

    Args:
        meta: The string meta submitted by the frontend.
        tags: Optional tag list; when None, keeps existing tags or writes a
            default empty list.
        status: Optional sync status; when None, keeps the existing status or
            writes the default status.
        existing_meta: The existing database meta when updating a node.

    Returns:
        A JSON dict ready to be written to NodeORM.meta.
    """
    stored_meta: dict[str, Any] = existing_meta if isinstance(existing_meta, dict) else {}
    next_meta = dict(stored_meta)

    if meta:
        next_meta[META_TEXT_KEY] = meta
    else:
        next_meta.pop(META_TEXT_KEY, None)

    if tags is not None:
        next_meta[META_TAGS_KEY] = [tag for tag in tags if isinstance(tag, str)]
    elif META_TAGS_KEY not in next_meta:
        next_meta[META_TAGS_KEY] = []

    if status is not None:
        next_meta[META_STATUS_KEY] = status
    elif META_STATUS_KEY not in next_meta:
        next_meta[META_STATUS_KEY] = DEFAULT_NODE_STATUS

    if parent_id:
        next_meta[META_PARENT_ID_KEY] = parent_id
    else:
        next_meta.pop(META_PARENT_ID_KEY, None)

    if sort_order is not None:
        next_meta[META_SORT_ORDER_KEY] = sort_order

    return next_meta


def db_meta_to_api(meta: Any) -> str:
    """Read the API string meta from the database meta."""
    if isinstance(meta, dict):
        value = meta.get(META_TEXT_KEY, "")
        return value if isinstance(value, str) else ""

    if isinstance(meta, str):
        return meta

    return ""


def db_tags_to_api(meta: Any) -> list[str]:
    """Read the API tags from the database meta."""
    if isinstance(meta, dict):
        tags = meta.get(META_TAGS_KEY, [])
        return [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    return []


def db_status_to_api(meta: Any) -> str:
    """Read the API status from the database meta."""
    if isinstance(meta, dict):
        status = meta.get(META_STATUS_KEY, DEFAULT_NODE_STATUS)
        return status if isinstance(status, str) else DEFAULT_NODE_STATUS

    return DEFAULT_NODE_STATUS


def db_parent_id_to_api(meta: Any) -> str | None:
    """Read the world folder parent id from the database meta."""
    if isinstance(meta, dict):
        parent_id = meta.get(META_PARENT_ID_KEY)
        return parent_id if isinstance(parent_id, str) and parent_id else None

    return None


def db_sort_order_to_api(meta: Any) -> int:
    """Read the world folder sibling order from the database meta."""
    if isinstance(meta, dict):
        sort_order = meta.get(META_SORT_ORDER_KEY, 0)
        return sort_order if isinstance(sort_order, int) else 0

    return 0
