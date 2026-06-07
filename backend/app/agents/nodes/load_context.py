"""Read session metadata + recent messages + current nodes, writing the memory and context fields of AgentState.

This node is the graph's "entry loader"; subsequent RAG / agent nodes all
depend on the snapshot it writes. ``world_brief`` comes from the project-level
ProjectORM, letting multi-turn conversations share one worldbuilding context;
``recent_message_window`` works together with the summary_compress node's
``keep_recent`` to jointly decide which messages are "fed verbatim" and which
enter the summary.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.agents.state import AgentState
from app.core.settings import get_agent_settings
from app.db.database import SessionLocal
from app.db.models import ChatMessageORM, ChatSessionORM, NodeORM, ProjectORM, ProjectSeedORM
from app.indexing.document_loader import node_to_current_payload


def _empty_context() -> dict[str, Any]:
    """Return a zeroing delta for all AgentState fields that "may linger across turns".

    Both return paths (session missing / normal load) start from these zero
    values, preventing the previous turn's *_output or boundary_warnings from
    contaminating this turn's assembler input when LangGraph reuses a checkpoint.
    """
    return {
        "world_brief": "",
        "seed_context": "",
        "conversation_summary": "",
        "key_facts": [],
        "recent_messages": [],
        "current_nodes": [],
        "intent": None,
        "inspiration_output": None,
        "research_output": None,
        "structure_output": None,
        "simulation_output": None,
        "assembler_output": None,
        "boundary_warnings": [],
        "staging_batch_id": None,
        "staging_count": 0,
        "next_question_hint": "",
        "deferred_fields": [],
        "extraction_batch_id": None,
        "extraction_count": 0,
        "extraction_applied": [],
    }


def load_context_node(state: AgentState) -> dict[str, Any]:
    """Pull context from SQLite; return an empty skeleton when the session is missing or not provided."""
    session_id = state.get("session_id", "")
    selected_ids = state.get("selected_node_ids") or []

    if not session_id:
        return _empty_context()

    window = get_agent_settings().recent_message_window

    with SessionLocal() as db:
        session = db.get(ChatSessionORM, session_id)
        if session is None:
            return _empty_context()

        project = db.get(ProjectORM, session.project_id)
        world_brief = project.world_brief if project is not None else ""

        # Latest project seed (decision 4): a low-cost full-project snapshot injected at startup.
        latest_seed = (
            db.query(ProjectSeedORM)
            .filter(ProjectSeedORM.project_id == session.project_id)
            .order_by(ProjectSeedORM.version.desc())
            .first()
        )
        seed_context = latest_seed.seed_json if latest_seed is not None else ""

        recent = list(
            db.scalars(
                select(ChatMessageORM)
                .where(ChatMessageORM.session_id == session_id)
                .order_by(ChatMessageORM.created_at.desc())
                .limit(window)
            )
        )
        # SQL fetches in descending order for LIMIT; flip back to chronological order to feed the prompt
        recent.reverse()

        current_node_payloads: list[Any] = []
        for node_id in selected_ids:
            node = db.get(NodeORM, node_id)
            if node is not None:
                current_node_payloads.append(node_to_current_payload(node))

        return {
            **_empty_context(),
            "world_brief": world_brief,
            "seed_context": seed_context,
            "conversation_summary": session.conversation_summary,
            "key_facts": list(session.key_facts or []),
            "recent_messages": [
                {"role": message.role, "content": message.content} for message in recent
            ],
            "current_nodes": current_node_payloads,
        }