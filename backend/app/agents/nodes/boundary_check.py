"""Boundary check node.

Runs before chat_assembler, performing deterministic validation on the
proposed_changes produced by this turn's agent. It filters out non-compliant
items and records the reasons in ``boundary_warnings`` for downstream use, so
chat_assembler can faithfully explain in the reply why items were skipped,
preventing users from accepting empty staging.

Validation runs only hard rules, no LLM calls:
- create_node: title / content length, node_type whitelist
- create_edge: source / target must be a pending_id within the same batch or a
  real node_id within the project; self-loops are forbidden
- update_node: target_id must match an existing node, payload must contain at
  least one updatable field
- whole batch: pending_id must not repeat, changes per batch <= the limit

This works hand in hand with canvas_apply's "defensive skip": canvas_apply is
the last fallback before persisting, while this is the earliest gate, letting
users immediately see in the reply "which item failed and why".
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import ProposedChange
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import NodeORM


# Only agents of these intents produce proposed_changes; simulation is
# physically isolated and does not participate.
_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
}

_VALID_NODE_TYPES = {
    "character", "worldbuilding", "plot",
    "idea", "research", "structure",
}
_UPDATABLE_FIELDS = {"title", "content", "node_type"}
_TITLE_MAX = 100
_CONTENT_MAX = 2000
_MAX_CHANGES_PER_BATCH = 15
_AGENTS_WITH_CHANGES = {"inspiration", "research", "structure"}


def boundary_check_node(state: AgentState) -> dict[str, Any]:
    """Run boundary validation on the proposed_changes of the agent matching the current intent.

    Runs hard rules to filter out non-compliant items and records the reasons
    in ``boundary_warnings`` for downstream chat_assembler to reference, letting
    users immediately see in the reply "which item was skipped and why".
    """
    intent = state.get("intent")
    if intent is None or intent.primary not in _AGENTS_WITH_CHANGES:
        return {}

    output_key = f"{intent.primary}_output"
    output = state.get(output_key)
    if output is None:
        return {}

    changes = list(getattr(output, "proposed_changes", []) or [])
    if not changes:
        return {}

    accepted, warnings = _filter_changes(changes, state.get("project_id", ""))
    if not warnings and len(accepted) == len(changes):
        return {}

    updates: dict[str, Any] = {"boundary_warnings": warnings}
    if len(accepted) != len(changes):
        updates[output_key] = output.model_copy(update={"proposed_changes": accepted})
    return updates


def _filter_changes(
    changes: list[ProposedChange],
    project_id: str,
) -> tuple[list[ProposedChange], list[str]]:
    """Run all rules and return (accepted changes, list of warning descriptions).

    Dedup dimensions: create_node by pending_id, create_edge by the (source,
    target, relation_type) triple, update_node by the (target_id, key payload
    fields) combination. The LLM occasionally copies "one well-thought-out
    item" N times into the list; this dedup layer hard-removes them within the
    batch.
    """
    warnings: list[str] = []

    if len(changes) > _MAX_CHANGES_PER_BATCH:
        warnings.append(
            f"The agent proposed {len(changes)} changes at once, exceeding the "
            f"per-turn limit of {_MAX_CHANGES_PER_BATCH}; only the first "
            f"{_MAX_CHANGES_PER_BATCH} are kept."
        )
        changes = changes[:_MAX_CHANGES_PER_BATCH]

    pending_ids: set[str] = set()
    seen_signatures: set[tuple] = set()
    duplicate_indices: set[int] = set()

    for idx, change in enumerate(changes):
        if change.change_type == "create_node" and change.pending_id:
            if change.pending_id in pending_ids:
                duplicate_indices.add(idx)
                warnings.append(
                    f"create_node #{idx + 1} has pending_id="
                    f"{change.pending_id!r} that duplicates an existing item in "
                    f"the same batch; skipped."
                )
            else:
                pending_ids.add(change.pending_id)

        signature = _signature_of(change)
        if signature is None:
            continue
        if signature in seen_signatures:
            duplicate_indices.add(idx)
            warnings.append(
                f"{change.change_type} #{idx + 1} is identical in content to an "
                f"existing item in the same batch; skipped."
            )
        else:
            seen_signatures.add(signature)

    accepted: list[ProposedChange] = []
    with SessionLocal() as db:
        for idx, change in enumerate(changes):
            if idx in duplicate_indices:
                continue
            problem = _check_one(change, db, project_id, pending_ids)
            if problem is None:
                accepted.append(change)
            else:
                warnings.append(f"{change.change_type} #{idx + 1}: {problem}")

    return accepted, warnings


def _signature_of(change: ProposedChange) -> tuple | None:
    """Extract a change's "content fingerprint" for cross-item dedup; returns None to skip dedup when no fingerprint can be formed."""
    payload = change.payload or {}

    if change.change_type == "create_node":
        return (
            "create_node",
            (str(payload.get("title") or "")).strip().lower(),
            payload.get("node_type"),
        )

    if change.change_type == "create_edge":
        source = payload.get("source")
        target = payload.get("target")
        relation = payload.get("relation_type") or payload.get("label") or ""
        if not source or not target:
            return None
        return ("create_edge", source, target, relation)

    if change.change_type == "update_node":
        return (
            "update_node",
            change.target_id,
            (str(payload.get("title") or "")).strip().lower(),
            (str(payload.get("content") or "")).strip().lower(),
            payload.get("node_type"),
        )

    if change.change_type == "delete_node":
        return ("delete_node", change.target_id)

    if change.change_type == "delete_edge":
        return (
            "delete_edge",
            change.target_id,
            payload.get("source"),
            payload.get("target"),
            payload.get("relation_type") or payload.get("label") or "",
        )
    return None


def _check_one(
    change: ProposedChange,
    db: Session,
    project_id: str,
    pending_ids: set[str],
) -> str | None:
    """Run all rules on a single change; returns None if it passes, otherwise the rejection reason."""
    payload = change.payload or {}

    if change.change_type == "create_node":
        title = (str(payload.get("title") or "")).strip()
        if not title:
            return "Missing title."
        if len(title) > _TITLE_MAX:
            return f"title length {len(title)} exceeds the limit of {_TITLE_MAX}."
        content = str(payload.get("content") or "")
        if len(content) > _CONTENT_MAX:
            return f"content length {len(content)} exceeds the limit of {_CONTENT_MAX}."
        if payload.get("node_type") not in _VALID_NODE_TYPES:
            return (
                f"node_type={payload.get('node_type')!r} is not in the whitelist "
                f"{sorted(_VALID_NODE_TYPES)}."
            )
        return None

    if change.change_type == "create_edge":
        source = payload.get("source")
        target = payload.get("target")
        if not source or not target:
            return "source or target is empty."
        if source == target:
            return "source equals target; self-loop edge rejected."
        for label, raw in (("source", source), ("target", target)):
            if raw in pending_ids:
                continue
            node = db.get(NodeORM, raw)
            if node is None or node.project_id != project_id:
                return (
                    f"{label}={raw!r} is neither a pending_id in the same batch "
                    "nor a real node_id within the project."
                )
        return None

    if change.change_type == "update_node":
        if not change.target_id:
            return "Missing target_id."
        node = db.get(NodeORM, change.target_id)
        if node is None or node.project_id != project_id:
            return f"target_id={change.target_id!r} has no matching node within the project."
        if not any(field in payload for field in _UPDATABLE_FIELDS):
            return f"payload must contain at least one updatable field {sorted(_UPDATABLE_FIELDS)}."
        return None

    if change.change_type == "delete_node":
        if not change.target_id:
            return "Missing target_id."
        node = db.get(NodeORM, change.target_id)
        if node is None or node.project_id != project_id:
            return f"target_id={change.target_id!r} has no matching node within the project."
        return None

    if change.change_type == "delete_edge":
        if change.target_id:
            return None  # A real edge_id is validated for project ownership later when canvas_apply persists it
        payload_src = payload.get("source")
        payload_tgt = payload.get("target")
        if not payload_src or not payload_tgt:
            return "Missing target_id, or missing the payload.source / payload.target triple."
        return None

    return f"Unsupported change_type={change.change_type!r}."