"""Chat and staging HTTP routes.

Exposes the CRUD endpoints for sessions / messages / staging; ``POST /api/chat``
is the real agent entry point, triggering the full LangGraph reasoning pipeline.
"""

from typing import Literal

from fastapi import APIRouter

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
from app.services.chat_service import (
    append_session_message,
    create_session,
    create_staging_batch,
    get_session_messages,
    list_sessions,
    list_session_staging,
    resolve_staging_batch,
    resolve_staging_item,
    run_chat_turn,
)
from app.services.chat_stream import stream_chat_turn
from fastapi.responses import StreamingResponse


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionPayload)
async def create_chat_session(payload: ChatSessionCreateRequest) -> ChatSessionPayload:
    """Create a new chat session; also assigns a thread_id for use by the LangGraph Checkpointer."""
    return create_session(payload)


@router.get("/projects/{project_id}/sessions", response_model=list[ChatSessionPayload])
async def list_project_chat_sessions(project_id: str) -> list[ChatSessionPayload]:
    """List the sessions under the given project, ordered by creation time descending."""
    return list_sessions(project_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessagePayload])
async def list_chat_messages(session_id: str) -> list[ChatMessagePayload]:
    """Read the full message history of a session."""
    return get_session_messages(session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessagePayload)
async def append_chat_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
) -> ChatMessagePayload:
    """Append a single message (does not trigger agent reasoning); used only for integration debugging and unit tests, real conversations go through POST /api/chat."""
    return append_session_message(session_id, payload)


@router.post("/sessions/{session_id}/staging", response_model=AgentStagingBatchPayload)
async def create_chat_staging_batch(
    session_id: str,
    payload: AgentStagingBatchCreateRequest,
) -> AgentStagingBatchPayload:
    """Write a batch of staging items; shared entry point for persistence_hub and the manual endpoint."""
    return create_staging_batch(session_id, payload)


@router.get(
    "/sessions/{session_id}/staging",
    response_model=list[AgentStagingBatchPayload],
)
async def list_chat_staging(
    session_id: str,
    status: Literal["pending", "accepted", "edited", "rejected"] | None = None,
) -> list[AgentStagingBatchPayload]:
    """List staging by session, automatically grouped by batch; returns all statuses by default."""
    return list_session_staging(session_id, status)


@router.patch("/staging/{staging_id}", response_model=AgentStagingPayload)
async def resolve_chat_staging_item(
    staging_id: str,
    payload: AgentStagingActionRequest,
) -> AgentStagingPayload:
    """Accept / edit / reject a single staging item; operating again on an already-resolved item returns 409."""
    return resolve_staging_item(staging_id, payload)


@router.patch(
    "/staging/batch/{batch_id}",
    response_model=list[AgentStagingPayload],
)
async def resolve_chat_staging_batch(
    batch_id: str,
    payload: AgentStagingBatchActionRequest,
) -> list[AgentStagingPayload]:
    """Batch accept / reject the staging from the same turn; already-resolved items are silently skipped."""
    return resolve_staging_batch(batch_id, payload)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(payload: ChatRequest) -> ChatResponse:
    """Trigger the full agent_graph reasoning pipeline; returns the chat reply plus staging batch info synchronously."""
    return run_chat_turn(payload)


@router.post("/chat/stream")
async def post_chat_stream(payload: ChatRequest) -> StreamingResponse:
    """SSE streaming chat endpoint; the frontend parses the event stream with fetch + ReadableStream.
    Cache-Control disables caching and X-Accel-Buffering disables nginx
    intermediate buffering, so events can be pushed to the frontend immediately,
    preventing the reverse proxy from piling them up into a "burst arrival" that
    ruins the progressive experience.
    """
    return StreamingResponse(
        stream_chat_turn(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )