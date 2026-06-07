"""Apply resolved staging records to the canvas.

The caller is responsible for transitioning staging status to ``accepted`` /
``edited``; this module only translates the payload into NodeORM/EdgeORM and
flushes it to SQLite within the same transaction.

Supported change types:
- ``create_node``: writes a NodeORM, tags it as AI-sourced; pending_ids within
  the same batch are accumulated into ``pending_id_map`` by the caller on
  return; the generated node_id is also written back to ``record.target_id`` so
  that a single-record accept of create_edge across HTTP requests can look it up
  from the DB
- ``create_edge``: writes an EdgeORM; source / target can be either a real
  node_id or the pending_id of a create_node within the same batch; silently
  skipped when an endpoint is invalid or fabricated by the LLM, to avoid
  blowing up the transaction on a SQLite foreign key constraint

ChromaDB sync must happen after the transaction commits, so this module only
returns the newly written node_ids; the caller triggers
``safe_sync_node_index`` for each one after the transaction closes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.database import _SECTION_BY_NODE_TYPE, _DEFAULT_SECTION
from app.db.models import AgentStagingORM, EdgeORM, NodeORM, ProjectORM

logger = logging.getLogger(__name__)


_ACCEPTED_STATUSES = {"accepted", "edited"}

# section -> the corresponding graph_id attribute name on ProjectORM.
_GRAPH_ID_ATTR_BY_SECTION = {
    "plot": "plot_graph_id",
    "character": "character_graph_id",
    "world": "world_graph_id",
}


def _resolve_graph_id(db: Session, project_id: str, node_type: str) -> str | None:
    """Find the sub-graph id this node should belong to based on node_type (first_revision decision 1).

    Returns None if the project has not yet migrated to sub-graphs (which should
    not happen in theory), in which case the node degrades to having no graph_id.
    """
    project = db.get(ProjectORM, project_id)
    if project is None:
        return None
    section = _SECTION_BY_NODE_TYPE.get(node_type, _DEFAULT_SECTION)
    return getattr(project, _GRAPH_ID_ATTR_BY_SECTION[section], None)


def apply_staging_record(
    db: Session,
    record: AgentStagingORM,
    pending_id_map: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """Apply a single staging record to the canvas.

    Returns:
        An (upserted_node_id, deleted_node_id) tuple:
        - upserted_node_id: the real id after create_node / update_node is
          persisted, used by the caller to trigger ChromaDB re-embedding after
          the transaction closes;
        - deleted_node_id: the real id matched by delete_node, used by the caller
          to remove the corresponding vector from ChromaDB after the transaction
          closes, avoiding leftovers.
        All other change_types return (None, None).
    """
    if record.status not in _ACCEPTED_STATUSES:
        return None, None

    payload = record.payload_edited or record.payload

    if record.change_type == "create_node":
        new_id = _apply_create_node(db, record, payload)
        if pending_id_map is not None and record.pending_id:
            pending_id_map[record.pending_id] = new_id
        return new_id, None

    if record.change_type == "create_edge":
        _apply_create_edge(db, record, payload, pending_id_map or {})
        return None, None

    if record.change_type == "update_node":
        return _apply_update_node(db, record, payload), None

    if record.change_type == "delete_node":
        return None, _apply_delete_node(db, record)

    if record.change_type == "delete_edge":
        _apply_delete_edge(db, record, payload)
        return None, None

    return None, None


def _apply_create_node(db: Session, record: AgentStagingORM, payload: dict[str, Any]) -> str:
    """Translate staging.payload into a new node.

    Writes the generated node_id back to record.target_id so that a later
    "single-record accept of create_edge" can look up pending_id -> real node_id
    from the DB (reusing the mapping across HTTP requests). target_id is empty by
    definition in create_node semantics, so reusing this field does not break
    anything.
    """
    node_id = uuid.uuid4().hex

    title = str(payload.get("title") or "AI suggested node")
    content = str(payload.get("content") or "")
    node_type = str(payload.get("node_type") or "character")

    db.add(
        NodeORM(
            id=node_id,
            project_id=record.project_id,
            graph_id=_resolve_graph_id(db, record.project_id, node_type),
            node_type=node_type,
            title=title,
            content=content,
            meta={"tags": ["AI suggestion"], "status": "synced"},
            position_x=120.0,
            position_y=120.0,
            sort_order=9999,
        )
    )
    record.target_id = node_id
    db.flush()
    return node_id


def _resolve_endpoint(
    db: Session,
    project_id: str,
    raw_id: str | None,
    pending_id_map: dict[str, str],
) -> str | None:
    """Translate the source / target in the payload into a real node_id on the canvas.

    Prefers matching the pending_id of a node newly created in the same batch;
    otherwise looks up NodeORM by real id and verifies project ownership; returns
    None if any step fails, letting the caller decide how to degrade (this module
    chooses to silently skip).
    """
    if not raw_id:
        return None

    if raw_id in pending_id_map:
        raw_id = pending_id_map[raw_id]

    node = db.get(NodeORM, raw_id)
    if node is None or node.project_id != project_id:
        return None
    return node.id


def _apply_create_edge(
    db: Session,
    record: AgentStagingORM,
    payload: dict[str, Any],
    pending_id_map: dict[str, str],
) -> None:
    """Translate staging.payload into a new edge; logs a warning and skips when endpoint resolution fails."""
    src_raw = payload.get("source")
    tgt_raw = payload.get("target")
    source = _resolve_endpoint(db, record.project_id, src_raw, pending_id_map)
    target = _resolve_endpoint(db, record.project_id, tgt_raw, pending_id_map)

    if source is None or target is None:
        logger.warning(
            "create_edge skipped: staging=%s project=%s source=%r->%r target=%r->%r",
            record.id, record.project_id, src_raw, source, tgt_raw, target,
        )
        return

    relation_type = str(payload.get("relation_type") or "relates_to")
    label = str(payload.get("label") or relation_type)

    db.add(
        EdgeORM(
            id=uuid.uuid4().hex,
            project_id=record.project_id,
            source=source,
            target=target,
            label=label,
            relation_type=relation_type,
            edge_type=str(payload.get("edge_type") or "smoothstep"),
            sort_order=9999,
        )
    )
    db.flush()

_UPDATABLE_NODE_FIELDS = {"title", "content", "node_type"}


def _apply_update_node(
    db: Session,
    record: AgentStagingORM,
    payload: dict[str, Any],
) -> str | None:
    """Merge staging.payload into an existing node; silently skips if the target node does not exist or is out of scope.

    The LLM often uses update_node to flesh out settings for an existing node;
    the payload may only overwrite whitelisted fields. Other fields (id /
    project_id / position, etc.) must be edited by the user in the frontend, to
    prevent the AI from accidentally changing canvas coordinates or ownership.
    """
    target_id = record.target_id
    if not target_id:
        return None

    node = db.get(NodeORM, target_id)
    if node is None or node.project_id != record.project_id:
        return None

    for field in _UPDATABLE_NODE_FIELDS:
        if field in payload and payload[field] is not None:
            setattr(node, field, str(payload[field]))

    db.flush()
    return target_id


def _apply_delete_node(db: Session, record: AgentStagingORM) -> str | None:
    """Delete a node; returns the deleted node_id for the caller to sync ChromaDB, or None on failure/out-of-scope.

    The DB is already configured with ondelete=CASCADE + PRAGMA foreign_keys=ON,
    so edges are cascaded automatically; manually deleting edges here is a
    belt-and-suspenders safeguard against "the environment forgetting to enable
    the PRAGMA", guaranteeing no orphan edges pointing at a deleted node remain
    on the canvas even without foreign keys.
    """
    target_id = record.target_id
    if not target_id:
        logger.warning("delete_node skipped: staging=%s has no target_id", record.id)
        return None

    node = db.get(NodeORM, target_id)
    if node is None or node.project_id != record.project_id:
        logger.warning(
            "delete_node skipped: staging=%s node %s is not in project %s",
            record.id, target_id, record.project_id,
        )
        return None

    db.query(EdgeORM).filter(
        EdgeORM.project_id == record.project_id,
        (EdgeORM.source == target_id) | (EdgeORM.target == target_id),
    ).delete(synchronize_session=False)
    db.delete(node)
    db.flush()
    return target_id


def _apply_delete_edge(
    db: Session,
    record: AgentStagingORM,
    payload: dict[str, Any],
) -> None:
    """Delete a single edge.

    Prefers using record.target_id for an exact lookup (written by the staging
    flow on a single-record frontend accept); fallback strategy: match the first
    edge within the project by payload.(source, target, relation_type). Silently
    skips when nothing matches, to avoid the LLM fabricating a nonexistent
    edge_id and triggering a 500.
    """
    edge = None
    if record.target_id:
        edge = db.get(EdgeORM, record.target_id)
        if edge is not None and edge.project_id != record.project_id:
            edge = None

    if edge is None:
        source = payload.get("source")
        target = payload.get("target")
        if source and target:
            query = db.query(EdgeORM).filter(
                EdgeORM.project_id == record.project_id,
                EdgeORM.source == source,
                EdgeORM.target == target,
            )
            relation = payload.get("relation_type")
            if relation:
                query = query.filter(EdgeORM.relation_type == relation)
            edge = query.first()

    if edge is None:
        logger.warning(
            "delete_edge skipped: staging=%s could not locate target edge target_id=%r payload=%s",
            record.id, record.target_id, payload,
        )
        return

    db.delete(edge)
    db.flush()