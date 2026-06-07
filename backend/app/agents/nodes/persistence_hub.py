"""Persistence hub node.

Each turn persists the following side effects in two independent transactions:
1. user_message is persisted independently (a separate transaction); even if the
   later chat_assembler fails, the user message is already committed, so next
   turn's recent_messages won't have a one-sided gap.
2. When assembler_output exists, the second transaction appends the
   assistant_message; if this turn's agent output contains proposed_changes,
   the same transaction writes AgentStaging records under the same batch_id,
   awaiting the user to accept / edit / reject them in the frontend staging panel.

When the session is missing, the whole node silently skips, letting graph.invoke
still return an in-memory assembler_output to the caller as a fallback.
"""

from __future__ import annotations

from typing import Any

from app.agents.schemas import ProposedChange
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import ChatSessionORM
from app.schemas import AgentStagingCreateItem
from app.services.chat_repository import append_message, insert_staging_batch


_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
}
"""Only these three agent types produce proposed_changes; simulation is physically isolated and does not participate."""


def _collect_proposed_changes(state: AgentState) -> tuple[list[ProposedChange], str]:
    """Take proposed_changes from the output of the agent matching the current intent; return an empty list if none.

    agent_type takes intent.primary, so the staging table can group its display
    by agent source.
    """
    intent = state.get("intent")
    primary = intent.primary if intent is not None else ""
    output_key = _OUTPUT_KEY_BY_INTENT.get(primary)
    if output_key is None:
        return [], primary

    output = state.get(output_key)
    if output is None:
        return [], primary

    changes = list(getattr(output, "proposed_changes", []) or [])
    return changes, primary


def _to_staging_items(changes: list[ProposedChange]) -> list[AgentStagingCreateItem]:
    """ProposedChange (agent internal model) -> AgentStagingCreateItem (persistence model)."""
    return [
        AgentStagingCreateItem(
            change_type=change.change_type,
            target_id=change.target_id,
            pending_id=change.pending_id,
            payload=change.payload,
            reasoning=change.reason,
        )
        for change in changes
    ]


def persistence_hub_node(state: AgentState) -> dict[str, Any]:
    session_id = state.get("session_id", "")
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()
    assembler = state.get("assembler_output")

    if not session_id:
        return {}

    # First transaction: user message persisted independently, decoupled from the assembler's success/failure
    with SessionLocal.begin() as db:
        if db.get(ChatSessionORM, session_id) is None:
            return {}
        if user_message:
            append_message(db, session_id=session_id, role="user", content=user_message)

    if assembler is None:
        return {}

    proposed_changes, agent_type = _collect_proposed_changes(state)
    staging_items = _to_staging_items(proposed_changes)

    # Second transaction: assistant_message and staging share the same transaction,
    # guaranteeing referential consistency between message and batch (a staging
    # row's message_id always points to a really existing message)
    with SessionLocal.begin() as db:
        meta: dict[str, Any] = {
            "agent_type": agent_type,
            "cited_node_ids": list(assembler.cited_node_ids),
            "staging_summary": assembler.staging_summary,
            "web_sources": [item.model_dump() for item in assembler.web_sources],
        }
        assistant_message = append_message(
            db,
            session_id=session_id,
            role="assistant",
            content=assembler.reply_text,
            meta=meta,
        )
        assistant_message_id = assistant_message.id

        batch_id: str | None = None
        if staging_items:
            batch_id, _ = insert_staging_batch(
                db,
                session_id=session_id,
                message_id=assistant_message_id,
                project_id=project_id,
                agent_type=agent_type,
                items=staging_items,
            )

    return {
        "assistant_message_id": assistant_message_id,
        "staging_batch_id": batch_id,
        "staging_count": len(staging_items),
    }