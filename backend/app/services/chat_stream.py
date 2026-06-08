"""SSE streaming chat implementation.

LangGraph's sync interface `graph.stream` is compatible with the `SqliteSaver`
(synchronous checkpointer) the project currently uses; calling `graph.astream`
directly would force `aget_tuple`, requiring `AsyncSqliteSaver` + `aiosqlite`,
which does not match the existing architecture.

Compromise: run the synchronous `graph.stream` inside `asyncio.to_thread` and
bridge it into an async generator via `asyncio.Queue`, which neither pulls in
the aiosqlite dependency nor requires rewriting chat_service.run_chat_turn as a
whole into async.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from collections.abc import AsyncIterator
from typing import Any

from app.agents.graph import get_agent_graph
from app.core.settings import get_app_settings
from app.db.database import SessionLocal
from app.db.models import NodeORM
from app.schemas import ChatRequest
from app.services.chat_service import require_session


logger = logging.getLogger(__name__)

_PROD_ERROR_MESSAGE = "Something went wrong during reasoning, please try again"


_NODE_LABELS: dict[str, str] = {
    "load_context": "Loading context",
    "intent_router": "Determining intent",
    "parallel_retrieval": "Searching knowledge base",
    "context_compress": "Compressing context",
    "inspiration_agent": "Brainstorming ideas",
    "research_agent": "Researching and verifying",
    "structure_agent": "Organizing structure",
    "simulation_agent": "Simulating branches",
    "boundary_check": "Boundary check",
    "chat_assembler": "Generating reply",
    "persistence_hub": "Persisting results",
    "structured_extractor": "Extracting entities",
    "question_planner": "Planning follow-up",
    "summary_compress": "Compressing conversation summary",
}


_DONE = object()


def _sse(data: dict[str, Any]) -> str:
    """Dict -> SSE protocol data line (events separated by double \\n)."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _traceback_tail(exc: BaseException, *, max_lines: int = 14) -> str:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    lines = tb.rstrip().splitlines()
    if len(lines) <= max_lines:
        return tb.rstrip()
    omitted = len(lines) - max_lines
    return "\n".join([f"... ({omitted} lines omitted) ...", *lines[-max_lines:]])


def _build_error_event(
    exc: BaseException,
    *,
    phase: str,
    last_node: str | None = None,
) -> dict[str, Any]:
    """Build the SSE error payload; include diagnostics only in dev mode."""
    if not get_app_settings().dev_mode:
        return {"type": "error", "message": _PROD_ERROR_MESSAGE}

    error_type = type(exc).__name__
    error_message = str(exc) or repr(exc)
    node_hint = f" at node `{last_node}`" if last_node else ""
    summary = f"{error_type}: {error_message}{node_hint}"

    return {
        "type": "error",
        "message": f"Reasoning failed during {phase}{node_hint}: {summary}",
        "debug": {
            "phase": phase,
            "last_node": last_node,
            "error_type": error_type,
            "error_message": error_message,
            "traceback": _traceback_tail(exc),
        },
    }


def _resolve_related_nodes(node_ids: list[str]) -> list[dict[str, str]]:
    """Resolve cited node ids to lightweight {id, title, node_type} for the chat UI."""
    ids = list(node_ids or [])
    if not ids:
        return []
    with SessionLocal() as db:
        rows = db.query(NodeORM).filter(NodeORM.id.in_(ids)).all()
    by_id = {n.id: n for n in rows}
    return [
        {"id": n.id, "title": n.title, "node_type": n.node_type}
        for nid in ids
        if (n := by_id.get(nid)) is not None
    ]


def _build_events(node_name: str, node_output: Any) -> list[dict[str, Any]]:
    """Node output -> list of SSE events (a main event + metadata events attached to key nodes)."""
    events: list[dict[str, Any]] = [
        {
            "type": "node_end",
            "node": node_name,
            "label": _NODE_LABELS.get(node_name, node_name),
        }
    ]

    if not isinstance(node_output, dict):
        return events

    if node_name == "intent_router":
        intent = node_output.get("intent")
        if intent is not None:
            events.append({
                "type": "intent",
                "primary": intent.primary,
                "confidence": intent.confidence,
            })

    elif node_name == "chat_assembler":
        assembler = node_output.get("assembler_output")
        if assembler is not None:
            events.append({
                "type": "reply_ready",
                "reply_text": assembler.reply_text,
                "cited_node_ids": list(assembler.cited_node_ids),
                "related_nodes": _resolve_related_nodes(assembler.cited_node_ids),
                "staging_summary": assembler.staging_summary,
                "web_sources": [item.model_dump() for item in assembler.web_sources],
            })

    elif node_name == "persistence_hub":
        events.append({
            "type": "persistence_done",
            "message_id": node_output.get("assistant_message_id", ""),
            "batch_id": node_output.get("staging_batch_id"),
            "staging_count": node_output.get("staging_count", 0),
        })
        applied = node_output.get("extraction_applied") or []
        if applied:
            events.append({"type": "extraction_applied", "items": applied})

    elif node_name == "structured_extractor":
        applied = node_output.get("extraction_applied") or []
        if applied:
            events.append({"type": "extraction_applied", "items": applied})

    return events


async def stream_chat_turn(payload: ChatRequest) -> AsyncIterator[str]:
    """Run graph.stream (sync) and convert each node output into SSE events.

    Any internal graph exception is funneled into a single error event, so the
    frontend can gracefully switch to fallback text without hitting a stream cut
    off midway.
    """
    with SessionLocal() as db:
        session = require_session(db, payload.session_id)
        thread_id = session.thread_id
        project_id = session.project_id

    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {
        "session_id": payload.session_id,
        "project_id": project_id,
        "user_message": payload.user_message,
        "selected_node_ids": list(payload.selected_node_ids),
        "extraction_enabled": payload.extraction_enabled,
        "auto_apply_staging": payload.auto_apply_staging,
        "web_search_mode": payload.web_search_mode,
    }

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer() -> None:
        """Synchronous thread runs graph.stream; call_soon_threadsafe delivers each chunk back to the loop.

        With multiple stream_modes, LangGraph wraps each chunk into a (mode,
        payload) tuple; the main coroutine dispatches by mode: "updates" is a
        node-level update, "custom" is a token event pushed from within a node via
        get_stream_writer.
        """
        try:
            stream = graph.stream(
                inputs, config=config, stream_mode=["updates", "custom"]
            )
            for chunk in stream:
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    producer_task = asyncio.create_task(asyncio.to_thread(producer))
    last_node: str | None = None

    try:
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            if isinstance(item, Exception):
                logger.exception(
                    "stream_chat_turn graph internal failure (last_node=%s): %s",
                    last_node,
                    item,
                )
                yield _sse(_build_error_event(item, phase="graph.stream", last_node=last_node))
                return

            mode, payload = item
            if mode == "custom":
                # Token events pushed by chat_assembler via get_stream_writer, passed through to the frontend
                if isinstance(payload, dict) and payload.get("type"):
                    yield _sse(payload)
                continue

            # mode == "updates": payload is a {node_name: node_output} dict
            for node_name, node_output in payload.items():
                last_node = node_name
                for event in _build_events(node_name, node_output):
                    yield _sse(event)

        yield _sse({"type": "done"})

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "stream_chat_turn failed (last_node=%s): %s",
            last_node,
            exc,
        )
        yield _sse(_build_error_event(exc, phase="stream loop", last_node=last_node))
    finally:
        await producer_task