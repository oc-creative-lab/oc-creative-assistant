"""对话与 staging HTTP 路由。

暴露会话 / 消息 / staging 的 CRUD 接口; ``POST /api/chat`` 是真正的
agent 入口, 触发 LangGraph 完整推理链路。
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
    """创建新对话会话; 同步分配 thread_id 给 LangGraph Checkpointer 使用。"""
    return create_session(payload)


@router.get("/projects/{project_id}/sessions", response_model=list[ChatSessionPayload])
async def list_project_chat_sessions(project_id: str) -> list[ChatSessionPayload]:
    """列出指定项目下的会话, 创建时间倒序。"""
    return list_sessions(project_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessagePayload])
async def list_chat_messages(session_id: str) -> list[ChatMessagePayload]:
    """读取会话完整消息历史。"""
    return get_session_messages(session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessagePayload)
async def append_chat_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
) -> ChatMessagePayload:
    """追加一条消息 (不触发 agent 推理); 仅用于联调与单测, 正式对话走 POST /api/chat。"""
    return append_session_message(session_id, payload)


@router.post("/sessions/{session_id}/staging", response_model=AgentStagingBatchPayload)
async def create_chat_staging_batch(
    session_id: str,
    payload: AgentStagingBatchCreateRequest,
) -> AgentStagingBatchPayload:
    """写入一批 staging; persistence_hub 与手动接口共用该入口。"""
    return create_staging_batch(session_id, payload)


@router.get(
    "/sessions/{session_id}/staging",
    response_model=list[AgentStagingBatchPayload],
)
async def list_chat_staging(
    session_id: str,
    status: Literal["pending", "accepted", "edited", "rejected"] | None = None,
) -> list[AgentStagingBatchPayload]:
    """按会话列出 staging, 自动按 batch 分组; 默认返回所有状态。"""
    return list_session_staging(session_id, status)


@router.patch("/staging/{staging_id}", response_model=AgentStagingPayload)
async def resolve_chat_staging_item(
    staging_id: str,
    payload: AgentStagingActionRequest,
) -> AgentStagingPayload:
    """单条 staging 的 accept / edit / reject; 已结案再次操作返回 409。"""
    return resolve_staging_item(staging_id, payload)


@router.patch(
    "/staging/batch/{batch_id}",
    response_model=list[AgentStagingPayload],
)
async def resolve_chat_staging_batch(
    batch_id: str,
    payload: AgentStagingBatchActionRequest,
) -> list[AgentStagingPayload]:
    """批量接受 / 拒绝同一 turn 的 staging; 已结案的项静默跳过。"""
    return resolve_staging_batch(batch_id, payload)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(payload: ChatRequest) -> ChatResponse:
    """触发 agent_graph 完整推理链路; 同步返回对话回复 + staging 批次信息。"""
    return run_chat_turn(payload)


@router.post("/chat/stream")
async def post_chat_stream(payload: ChatRequest) -> StreamingResponse:
    """SSE 流式 chat 接口; 前端用 fetch + ReadableStream 解析事件流。
    Cache-Control 关 cache, X-Accel-Buffering 关 nginx 中间缓冲, 让事件
    能立即推到前端, 避免反代积压成"突发到达"破坏渐进体验。
    """
    return StreamingResponse(
        stream_chat_turn(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )