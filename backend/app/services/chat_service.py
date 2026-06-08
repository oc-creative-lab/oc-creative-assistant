"""Application service layer for chat and staging.

Exposes semantic operations: create session, append message, list messages,
and advance the staging state machine. This module is not aware of LangGraph;
Phase 4 will call agent_graph inside ``append_session_message`` to trigger the
full reasoning chain, while the current phase only does persistence + state
machine.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from fastapi import HTTPException

from app.agents.graph import get_agent_graph
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm.factory import get_llm_provider
from app.db.database import SessionLocal
from app.db.models import AgentStagingORM, ChatMessageORM, ChatSessionORM
from app.indexing.sync import safe_sync_node_index
from app.indexing.vector_store import delete_node as delete_node_vectors
from app.services.canvas_apply import apply_staging_record
from app.services.graph_repository import read_project_node, require_project
from app.schemas import (
    AgentStagingActionRequest,
    AgentStagingBatchActionRequest,
    AgentStagingBatchCreateRequest,
    AgentStagingBatchPayload,
    AgentStagingPayload,
    ChatMessageCreateRequest,
    ChatMessagePayload,
    ChatRequest,
    ChatResponse,
    ChatSessionCreateRequest,
    ChatSessionPayload,
)
from app.services.chat_repository import (
    append_message,
    delete_session,
    insert_session,
    list_project_sessions,
    list_session_messages,
    list_staging_by_batch,
    list_staging_by_project,
    list_staging_by_session,
    rename_session,
    require_message,
    require_session,
    require_staging,
    transition_staging,
)


# ---- ORM → DTO ----

def _session_to_payload(record: ChatSessionORM) -> ChatSessionPayload:
    return ChatSessionPayload(
        id=record.id,
        project_id=record.project_id,
        thread_id=record.thread_id,
        title=record.title,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _message_to_payload(record: ChatMessageORM) -> ChatMessagePayload:
    return ChatMessagePayload(
        id=record.id,
        session_id=record.session_id,
        role=record.role,
        content=record.content,
        meta=record.meta,
        created_at=record.created_at,
    )


def _staging_to_payload(record: AgentStagingORM) -> AgentStagingPayload:
    return AgentStagingPayload(
        id=record.id,
        session_id=record.session_id,
        message_id=record.message_id,
        project_id=record.project_id,
        batch_id=record.batch_id,
        change_type=record.change_type,
        target_id=record.target_id,
        pending_id=record.pending_id,
        payload=record.payload,
        payload_edited=record.payload_edited,
        agent_type=record.agent_type,
        reasoning=record.reasoning,
        order_in_batch=record.order_in_batch,
        status=record.status,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )


def _group_by_batch(records: list[AgentStagingORM]) -> list[AgentStagingBatchPayload]:
    """Aggregate by batch_id, preserving first-appearance order; within a batch, preserve order_in_batch."""
    grouped: dict[str, list[AgentStagingORM]] = {}
    order: list[str] = []
    for record in records:
        if record.batch_id not in grouped:
            grouped[record.batch_id] = []
            order.append(record.batch_id)
        grouped[record.batch_id].append(record)
    return [
        AgentStagingBatchPayload(
            batch_id=batch_id,
            items=[_staging_to_payload(r) for r in grouped[batch_id]],
        )
        for batch_id in order
    ]


# ---- Session ----

def create_session(payload: ChatSessionCreateRequest) -> ChatSessionPayload:
    """Create a new session, verifying the project exists."""
    with SessionLocal.begin() as db:
        require_project(db, payload.project_id)
        record = insert_session(db, project_id=payload.project_id, title=payload.title)
        return _session_to_payload(record)


def list_sessions(project_id: str) -> list[ChatSessionPayload]:
    """List sessions under a given project, verifying the project exists."""
    with SessionLocal() as db:
        require_project(db, project_id)
        return [_session_to_payload(r) for r in list_project_sessions(db, project_id)]


def delete_chat_session(session_id: str) -> None:
    """Delete a session and its messages / staging (cascade)."""
    with SessionLocal.begin() as db:
        delete_session(db, session_id)


def rename_chat_session(session_id: str, title: str) -> ChatSessionPayload:
    """Rename a session; empty titles fall back to a placeholder."""
    with SessionLocal.begin() as db:
        record = rename_session(db, session_id, title.strip() or "Untitled chat")
        return _session_to_payload(record)


_TITLE_SYSTEM = (
    "You name chat sessions. Reply with ONLY a very short title for the user's first "
    "message, in the user's language: at most 4 words, or at most 5 Chinese characters. "
    "No quotes, no punctuation, no explanation — just the core topic."
)


def _summarize_title(user_message: str) -> str:
    """Ask the LLM for a short session title; fall back to truncation on failure."""
    text = user_message.strip()
    if not text:
        return "New chat"
    try:
        reply = get_llm_provider().chat(
            [SystemMessage(content=_TITLE_SYSTEM), HumanMessage(content=text)]
        )
        title = (reply or "").strip().strip('"').strip().splitlines()[0].strip()
        return title[:14] or text[:10]
    except Exception as error:  # noqa: BLE001
        logger.warning("session title generation failed, falling back: %s", error)
        return text[:10]


def generate_session_title(session_id: str, user_message: str) -> ChatSessionPayload:
    """Summarize the first user message into a title and persist it."""
    title = _summarize_title(user_message)
    with SessionLocal.begin() as db:
        record = rename_session(db, session_id, title)
        return _session_to_payload(record)

# ---- Messages ----

def append_session_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
) -> ChatMessagePayload:
    """Append a message to a given session without triggering agent_graph; used only for integration debugging and unit tests.
    The production chat flow is handled by ``run_chat_turn``, which writes
    messages uniformly inside the graph nodes."""
    with SessionLocal.begin() as db:
        require_session(db, session_id)
        record = append_message(
            db,
            session_id=session_id,
            role=payload.role,
            content=payload.content,
            meta=payload.meta,
        )
        return _message_to_payload(record)


def get_session_messages(session_id: str) -> list[ChatMessagePayload]:
    """Read all messages of a session."""
    with SessionLocal() as db:
        require_session(db, session_id)
        return [_message_to_payload(r) for r in list_session_messages(db, session_id)]


# ---- Staging ----

def create_staging_batch(
    session_id: str,
    payload: AgentStagingBatchCreateRequest,
) -> AgentStagingBatchPayload:
    """Write a batch of staging; both persistence_hub and the manual interface go through this path."""
    with SessionLocal.begin() as db:
        session = require_session(db, session_id)
        require_message(db, payload.message_id)
        batch_id, records = insert_staging_batch(
            db,
            session_id=session_id,
            message_id=payload.message_id,
            project_id=session.project_id,
            agent_type=payload.agent_type,
            items=payload.items,
        )
        return AgentStagingBatchPayload(
            batch_id=batch_id,
            items=[_staging_to_payload(r) for r in records],
        )


def list_session_staging(
    session_id: str,
    status: str | None = None,
) -> list[AgentStagingBatchPayload]:
    """List staging by session, automatically grouped by batch."""
    with SessionLocal() as db:
        require_session(db, session_id)
        records = list_staging_by_session(db, session_id, status)
        return _group_by_batch(records)


def list_project_staging(
    project_id: str,
    status: str | None = None,
) -> list[AgentStagingBatchPayload]:
    """List staging by project, automatically grouped by batch (used by the ChatWorkspace pending-review panel)."""
    with SessionLocal() as db:
        require_project(db, project_id)
        records = list_staging_by_project(db, project_id, status)
        return _group_by_batch(records)


def resolve_staging_item(
    staging_id: str,
    payload: AgentStagingActionRequest,
) -> AgentStagingPayload:
    """Advance the state machine for a single staging record; on accept / edit, also applies the change to the canvas.
    """
    upserted: list[tuple[str, str]] = []
    deleted: list[tuple[str, str]] = []

    with SessionLocal.begin() as db:
        record = require_staging(db, staging_id)

        if payload.action == "accept":
            transition_staging(record, new_status="accepted")
        elif payload.action == "edit":
            if payload.payload_edited is None:
                raise HTTPException(
                    status_code=400,
                    detail="payload_edited is required when action='edit'",
                )
            transition_staging(
                record,
                new_status="edited",
                payload_edited=payload.payload_edited,
            )
        else:
            transition_staging(record, new_status="rejected")

        # On single-record accept of create_edge, actively look up already-accepted
        # create_node records in the same batch to rebuild the pending_id_map;
        # other change_types do not need the map, so an empty dict is fine.
        pending_id_map: dict[str, str] = {}
        if record.change_type == "create_edge":
            siblings = list_staging_by_batch(db, record.batch_id)
            for sibling in siblings:
                if (
                    sibling.change_type == "create_node"
                    and sibling.status in {"accepted", "edited"}
                    and sibling.pending_id
                    and sibling.target_id
                ):
                    pending_id_map[sibling.pending_id] = sibling.target_id

        upserted_id, deleted_id = apply_staging_record(db, record, pending_id_map)
        if upserted_id:
            upserted.append((record.project_id, upserted_id))
        if deleted_id:
            deleted.append((record.project_id, deleted_id))

        result = _staging_to_payload(record)

    _sync_indices(upserted)
    _sync_deletions(deleted)
    return result


def resolve_staging_batch(
    batch_id: str,
    payload: AgentStagingBatchActionRequest,
) -> list[AgentStagingPayload]:
    """Batch-advance staging; already-resolved items are silently skipped, and on accept_all they are also applied to the canvas.

    create_edge relies on resolving pending_id to a real node_id; the
    pending_id_map is populated in two parts:
    1. Before the loop, scan the records once to look up the pending_id ->
       target_id of "previously single-record-accepted create_node" records, to
       prevent this batch's edges from being skipped because a preceding node was
       already resolved;
    2. In the loop, normally accumulate the mapping of create_node records newly
       created in this accept_all.
    Without this priming, when the user mixes "first single-record accept a node,
    then accept all the rest", edges referencing a preceding pending_id would be
    treated as a fake id by _resolve_endpoint and the whole edge silently
    skipped.
    """
    new_status = "accepted" if payload.action == "accept_all" else "rejected"
    upserted: list[tuple[str, str]] = []
    deleted: list[tuple[str, str]] = []
    pending_id_map: dict[str, str] = {}

    with SessionLocal.begin() as db:
        records = list_staging_by_batch(db, batch_id)
        if not records:
            raise HTTPException(status_code=404, detail="Staging batch not found")

        for record in records:
            if (
                record.change_type == "create_node"
                and record.status in {"accepted", "edited"}
                and record.pending_id
                and record.target_id
            ):
                pending_id_map[record.pending_id] = record.target_id

        ordered = sorted(
            records,
            key=lambda r: (0 if r.change_type == "create_node" else 1, r.order_in_batch),
        )

        for record in ordered:
            if record.status != "pending":
                continue
            transition_staging(record, new_status=new_status)
            upserted_id, deleted_id = apply_staging_record(db, record, pending_id_map)
            if upserted_id:
                upserted.append((record.project_id, upserted_id))
            if deleted_id:
                deleted.append((record.project_id, deleted_id))

        results = [_staging_to_payload(r) for r in records]

    _sync_indices(upserted)
    _sync_deletions(deleted)
    return results


# ---- Agent turn ----

def run_chat_turn(payload: ChatRequest) -> ChatResponse:
    """Run the agent's full reasoning chain, returning the assembled reply + staging batch info.

    This function does not manually write the user_message before graph.invoke;
    the write is handled uniformly by the persistence_hub node, so that message
    ordering strictly corresponds to the LLM reasoning process within the same
    transaction boundary.

    Any internal graph exception (LLM timeout / parse error / node KeyError) is
    funneled into a 200 + fallback ChatResponse, so that the frontend does not
    hit 500 -> fetch failed -> a blank screen in front of the user; actually
    diagnosing the problem relies on the exception traceback in the backend logs.
    """
    with SessionLocal() as db:
        session = require_session(db, payload.session_id)
        thread_id = session.thread_id
        project_id = session.project_id

    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = graph.invoke(
            {
                "session_id": payload.session_id,
                "project_id": project_id,
                "user_message": payload.user_message,
                "selected_node_ids": list(payload.selected_node_ids),
                "extraction_enabled": payload.extraction_enabled,
                "web_search_mode": payload.web_search_mode,
                "preferred_intent": payload.preferred_intent,
            },
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("graph.invoke failed, returning fallback reply: %s", exc)
        return ChatResponse(
            message_id="",
            reply_text="Sorry, something went wrong during my internal reasoning this round. Please say it again, or rephrase.",
            cited_node_ids=[],
            intent="",
            batch_id=None,
            staging_count=0,
            staging_summary="",
        )

    assembler = final_state.get("assembler_output")
    intent = final_state.get("intent")
    intent_name = intent.primary if intent is not None else ""

    if assembler is None:
        return ChatResponse(
            message_id="",
            reply_text="I didn't get a suitable result this round. Why not tell me a bit more about the direction you're after?",
            cited_node_ids=[],
            intent=intent_name,
            batch_id=None,
            staging_count=0,
            staging_summary="",
        )

    return ChatResponse(
        message_id=final_state.get("assistant_message_id", ""),
        reply_text=assembler.reply_text,
        cited_node_ids=list(assembler.cited_node_ids),
        intent=intent_name,
        batch_id=final_state.get("staging_batch_id"),
        staging_count=final_state.get("staging_count", 0),
        staging_summary=assembler.staging_summary,
    )

def _sync_indices(items: list[tuple[str, str]]) -> None:
    """Trigger ChromaDB sync for each just-persisted node; the transaction must commit first to avoid dirty writes."""
    for project_id, node_id in items:
        node = read_project_node(project_id, node_id)
        if node is not None:
            safe_sync_node_index(node)


def _sync_deletions(items: list[tuple[str, str]]) -> None:
    """Remove vectors from ChromaDB for each just-deleted node; the transaction must commit first to avoid dirty writes.

    A Chroma failure does not roll back the SQLite delete: the primary data
    source has already removed it, and any leftover vector can be cleaned up by
    calling delete_node once more; the log is kept just as a troubleshooting
    clue.
    """
    for project_id, node_id in items:
        try:
            delete_node_vectors(project_id, node_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "delete chroma failed project=%s node=%s: %s", project_id, node_id, exc
            )