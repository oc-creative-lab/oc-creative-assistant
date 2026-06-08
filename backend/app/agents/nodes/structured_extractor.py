"""Background structured extraction node (Agent B part one, first_revision decision 5 + rework 1).

Runs after persistence_hub: extracts entities / relations from the user's recent
free-form conversation, converts them into staging (reusing AgentStagingORM),
optionally [auto-persists] (accept_all) when ``auto_apply_staging`` is true
(workspace flow), pushing "added/updated" card info to the frontend so the user
can expand to edit or discard. When ``auto_apply_staging`` is false (Chat
module), items stay pending for the right-hand staging panel.

Two key points of rework 1:
1. Auto-persist (workspace only): when ``auto_apply_staging`` is set, immediately
   accept_all after writing staging (still going through AgentStagingORM +
   canvas_apply); the frontend renders inline cards via the extraction_applied event.
2. Dedup by name: if a same-named entity already exists on the canvas **or is
   already pending in staging** (e.g. structure_agent proposed it this turn),
   skip create_node; merge attributes via update_node only when a real node exists.
   Relations connect using real node_ids or same-batch pending_ids.

Works only when ``extraction_enabled`` is true; when off it is a no-op and the
legacy chat flow is unaffected.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.memory import format_current_nodes
from app.agents.prompts import load_prompt
from app.agents.structured_call import call_structured
from app.agents.schemas import StructuredExtractionOutput
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import AgentStagingORM, ChatSessionORM, NodeORM
from app.llm.factory import get_llm_provider
from app.schemas import AgentStagingCreateItem
from app.services.chat_repository import insert_staging_batch, list_staging_by_batch


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("structured_extractor")

# Entity type -> canvas node_type (aligned with sub-graph partitioning).
_NODE_TYPE_BY_ENTITY: dict[str, str] = {
    "character": "character",
    "world": "worldbuilding",
    "plot": "plot",
}

# Relation label -> relation_type (drives the canvas edge visuals; used at persistence time).
_RELATION_BY_LABEL: dict[str, str] = {
    "belongs to": "belongs_to",
    "participates in": "belongs_to",
    "mentorship": "belongs_to",
    "nemesis": "conflicts_with",
    "opposes": "conflicts_with",
    "causes": "causes",
    "triggers": "causes",
    "develops into": "develops_into",
}


def _entity_key(node_type: str, title: str) -> tuple[str, str]:
    return (node_type, title.strip().lower())


def _pending_create_refs(db: Session, project_id: str) -> dict[tuple[str, str], str]:
    """Map (node_type, title) -> pending_id for pending create_node staging rows."""
    refs: dict[tuple[str, str], str] = {}
    rows = db.scalars(
        select(AgentStagingORM).where(
            AgentStagingORM.project_id == project_id,
            AgentStagingORM.status == "pending",
            AgentStagingORM.change_type == "create_node",
        )
    )
    for record in rows:
        payload = record.payload_edited or record.payload or {}
        title = str(payload.get("title") or "").strip()
        if not title:
            continue
        node_type = str(payload.get("node_type") or "character")
        refs[_entity_key(node_type, title)] = record.pending_id or record.id
    return refs


def _merge_content(existing: str, attributes: dict[str, str]) -> str:
    """Merge newly extracted attributes into the existing node's content, without re-appending key-values already present."""
    lines = [line.strip() for line in (existing or "").splitlines() if line.strip()]
    seen = set(lines)
    for key, value in attributes.items():
        entry = f"{key}: {value}".strip()
        if entry and entry not in seen:
            lines.append(entry)
            seen.add(entry)
    return "\n".join(lines)


def _emit_applied(items: list[dict[str, Any]]) -> None:
    """Push the "persisted cards" to the frontend via the LangGraph custom stream (silent under non-streaming calls)."""
    if not items:
        return
    try:
        writer = get_stream_writer()
    except Exception:
        return
    try:
        writer({"type": "extraction_applied", "items": items})
    except Exception:
        pass


def structured_extractor_node(state: AgentState) -> dict[str, Any]:
    if not state.get("extraction_enabled"):
        return {}

    session_id = state.get("session_id", "")
    project_id = state.get("project_id", "")
    assistant_message_id = state.get("assistant_message_id", "")
    if not (session_id and assistant_message_id):
        return {}

    recent = state.get("recent_messages") or []
    history = "\n".join(f"{m['role']}: {m['content']}" for m in recent[-6:]) or "(none)"
    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"[Quoted nodes from canvas]\n{format_current_nodes(state.get('current_nodes') or [])}\n\n"
            f"[Recent conversation]\n{history}\n\n[User's latest message]\n{state.get('user_message', '')}"
        ),
    ]

    out = call_structured(
        get_llm_provider(),
        messages,
        StructuredExtractionOutput,
        label="structured_extractor",
    )
    if out is None:
        return {}

    deferred = [d.model_dump() for d in out.deferred_fields]

    if not out.entities:
        return {"deferred_fields": deferred, "extraction_count": 0}

    items: list[AgentStagingCreateItem] = []
    # Entity name -> the id referenced at persistence time (existing = real node_id, new = pending_id).
    ref_by_name: dict[str, str] = {}
    # Entity name -> node_type, used to keep only plot↔plot relations.
    type_by_name: dict[str, str] = {}

    # Dedup: canvas nodes always; pending staging only in Chat confirm mode (auto_apply off).
    # In workspace auto-apply mode, structure_agent staging is accepted before this node runs;
    # skipping pending rows here avoids duplicate cards in Chat, but must not block a failed auto_apply.
    chat_confirm_mode = not state.get("auto_apply_staging")
    with SessionLocal() as db:
        pending_create_refs = _pending_create_refs(db, project_id) if chat_confirm_mode else {}
        pending_seq = 0
        for entity in out.entities:
            node_type = _NODE_TYPE_BY_ENTITY.get(entity.type, "character")
            type_by_name[entity.name] = node_type
            key = _entity_key(node_type, entity.name)
            existing = (
                db.query(NodeORM)
                .filter(
                    NodeORM.project_id == project_id,
                    NodeORM.node_type == node_type,
                    NodeORM.title == entity.name,
                )
                .first()
            )
            if existing is not None:
                # A same-named card already exists -> update (merge new attributes into content), don't create a new one.
                ref_by_name[entity.name] = existing.id
                if entity.attributes:
                    items.append(
                        AgentStagingCreateItem(
                            change_type="update_node",
                            target_id=existing.id,
                            payload={
                                "title": entity.name,
                                "node_type": node_type,
                                "content": _merge_content(existing.content, entity.attributes),
                            },
                            reasoning="Supplemented an existing card from the conversation in the background",
                        )
                    )
            elif key in pending_create_refs:
                # structure_agent (or an earlier pending batch) already proposed this card.
                ref_by_name[entity.name] = pending_create_refs[key]
            else:
                pending_seq += 1
                pending_id = f"pending-{pending_seq}"
                ref_by_name[entity.name] = pending_id
                content = "; ".join(f"{k}: {v}" for k, v in entity.attributes.items())
                items.append(
                    AgentStagingCreateItem(
                        change_type="create_node",
                        pending_id=pending_id,
                        payload={"title": entity.name, "content": content, "node_type": node_type},
                        reasoning="Extracted from the conversation in the background",
                    )
                )

    for relation in out.relations:
        source = ref_by_name.get(relation.source_name)
        target = ref_by_name.get(relation.target_name)
        if not (source and target):
            continue
        if type_by_name.get(relation.source_name) != "plot" \
           or type_by_name.get(relation.target_name) != "plot":
            continue
        relation_type = _RELATION_BY_LABEL.get(relation.label, "relates_to")
        items.append(
            AgentStagingCreateItem(
                change_type="create_edge",
                payload={
                    "source": source,
                    "target": target,
                    "relation_type": relation_type,
                    "label": relation.label or "related",
                },
                reasoning="Extracted from the conversation in the background",
            )
        )

    if not items:
        return {"deferred_fields": deferred, "extraction_count": 0}

    with SessionLocal.begin() as db:
        if db.get(ChatSessionORM, session_id) is None:
            return {"deferred_fields": deferred, "extraction_count": 0}
        batch_id, _ = insert_staging_batch(
            db,
            session_id=session_id,
            message_id=assistant_message_id,
            project_id=project_id,
            agent_type="structured_extractor",
            items=items,
        )

    applied: list[dict[str, Any]] = []
    if state.get("auto_apply_staging"):
        applied = _auto_apply(batch_id)
        _emit_applied(applied)

    return {
        "extraction_batch_id": batch_id,
        "extraction_count": len(items),
        "extraction_applied": applied,
        "deferred_fields": deferred,
    }


def _applied_cards_from_batch(batch_id: str) -> list[dict[str, Any]]:
    """Build inline-card payloads from persisted staging rows (reads DB after accept_all)."""
    with SessionLocal() as db:
        records = list_staging_by_batch(db, batch_id)

    applied: list[dict[str, Any]] = []
    for record in records:
        if record.status not in ("accepted", "edited"):
            continue
        if record.change_type not in ("create_node", "update_node"):
            continue
        if not record.target_id:
            continue
        payload = record.payload_edited or record.payload or {}
        applied.append(
            {
                "node_id": record.target_id,
                "title": str(payload.get("title") or "Untitled"),
                "node_type": str(payload.get("node_type") or "character"),
                "content": str(payload.get("content") or ""),
                "change_type": record.change_type,
            }
        )
    return applied


def _auto_apply(batch_id: str) -> list[dict[str, Any]]:
    """Auto-accept the whole staging batch and persist it, returning a summary of the "added/updated" cards.

    Lazily imports chat_service to avoid a circular dependency with the agents
    package (chat_service -> graph -> this node).
    """
    from app.schemas import AgentStagingBatchActionRequest
    from app.services.chat_service import resolve_staging_batch

    try:
        resolve_staging_batch(
            batch_id, AgentStagingBatchActionRequest(action="accept_all")
        )
    except Exception as exc:
        logger.warning("auto_apply failed for batch %s: %s", batch_id, exc)
        return []

    return _applied_cards_from_batch(batch_id)
