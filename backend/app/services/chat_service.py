"""对话与 staging 的应用服务层。

对外暴露语义化操作: 创建会话、追加消息、列消息、推进 staging 状态机。
本模块不感知 LangGraph; 会在 ``append_session_message`` 内调用
agent_graph 触发完整推理链路, 当前阶段只做持久化 + 状态机。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from fastapi import HTTPException

from app.agents.graph import get_agent_graph
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
    ChatSessionUpdateRequest,
    ChatSessionPayload,
)
from app.services.chat_repository import (
    append_message,
    insert_session,
    insert_staging_batch,
    list_project_sessions,
    list_session_messages,
    list_staging_by_batch,
    list_staging_by_project,
    list_staging_by_session,
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
    """按 batch_id 聚合, 保持首次出现顺序; 同 batch 内保持 order_in_batch。"""
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
    """创建新会话, 校验项目存在。"""
    with SessionLocal.begin() as db:
        require_project(db, payload.project_id)
        record = insert_session(db, project_id=payload.project_id, title=payload.title)
        return _session_to_payload(record)


def list_sessions(project_id: str) -> list[ChatSessionPayload]:
    """列出指定项目下的会话, 校验项目存在。"""
    with SessionLocal() as db:
        require_project(db, project_id)
        return [_session_to_payload(r) for r in list_project_sessions(db, project_id)]


def update_session(session_id: str, payload: ChatSessionUpdateRequest) -> ChatSessionPayload:
    """重命名会话; 不存在抛 404。"""
    with SessionLocal.begin() as db:
        record = require_session(db, session_id)
        record.title = payload.title.strip()
        db.flush()
        return _session_to_payload(record)

        
def delete_session(session_id: str) -> None:
    """删除会话及其消息 / staging（relationship 配了级联, 子表自动清理）。"""
    with SessionLocal.begin() as db:
        record = require_session(db, session_id)
        db.delete(record)

# ---- Messages ----

def append_session_message(
    session_id: str,
    payload: ChatMessageCreateRequest,
) -> ChatMessagePayload:
    """追加一条消息到指定会话, 不触发 agent_graph; 仅用于联调和单测,
    生产对话流由 ``run_chat_turn`` 接管, 它在 graph 节点内部统一写入消息。"""
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
    """读取会话的全部消息。"""
    with SessionLocal() as db:
        require_session(db, session_id)
        return [_message_to_payload(r) for r in list_session_messages(db, session_id)]


# ---- Staging ----

def create_staging_batch(
    session_id: str,
    payload: AgentStagingBatchCreateRequest,
) -> AgentStagingBatchPayload:
    """写入一批 staging; persistence_hub 与手动接口都走这条路径。"""
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
    """按会话列出 staging, 自动按 batch 分组。"""
    with SessionLocal() as db:
        require_session(db, session_id)
        records = list_staging_by_session(db, session_id, status)
        return _group_by_batch(records)


def list_project_staging(
    project_id: str,
    status: str | None = None,
) -> list[AgentStagingBatchPayload]:
    """按项目列出 staging, 自动按 batch 分组（ChatWorkspace 待审面板用）。"""
    with SessionLocal() as db:
        require_project(db, project_id)
        records = list_staging_by_project(db, project_id, status)
        return _group_by_batch(records)


def resolve_staging_item(
    staging_id: str,
    payload: AgentStagingActionRequest,
) -> AgentStagingPayload:
    """单条 staging 推进状态机, 接受 / 编辑时同步把变更落到画布。
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

        # 单条接受 create_edge 时主动反查同 batch 已接受的 create_node, 重建
        # pending_id_map; 其它 change_type 不需要 map, 留空 dict 即可。
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
    """批量推进 staging; 已结案的项静默跳过, accept_all 时一并落到画布。

    create_edge 依赖 pending_id 解析到真实 node_id, pending_id_map 由两部分填充:
    1. 进循环前先扫一遍 records, 把"先前单条接受过的 create_node"的
       pending_id → target_id 反查进来, 防止本批的边因为前序节点已结案而跳过;
    2. 循环里再正常累积本次 accept_all 新建 create_node 的映射。
    没有这层预热, 用户混合"先单条接受 node、再全部接受剩余"时, 引用前序
    pending_id 的边会被 _resolve_endpoint 当成伪 id, 静默跳过整条。
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
    """执行 agent 完整推理链路, 返回装配后的回复 + staging 批次信息。

    本函数不在 graph.invoke 之前手动写 user_message; 写入由 persistence_hub
    节点统一负责, 让消息时序与 LLM 推理过程严格对应同一事务边界。

    任何 graph 内部异常 (LLM timeout / 解析错 / 节点 KeyError) 都会被收敛成
    200 + 兜底 ChatResponse, 让前端不至于撞 500 → fetch failed → 用户面前
    一片空白; 真正定位问题靠后端日志的 exception traceback。
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
            },
            config=config,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("graph.invoke 失败, 返回兜底回复: %s", exc)
        return ChatResponse(
            message_id="",
            reply_text="抱歉, 我这一轮在内部推理时出错了, 请再说一次, 或换种表述。",
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
            reply_text="我这一轮没拿到合适的结果, 不如再多说几句你想要的方向?",
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
    """对刚落库的节点逐一触发 ChromaDB 同步; 事务必须先提交避免脏写。"""
    for project_id, node_id in items:
        node = read_project_node(project_id, node_id)
        if node is not None:
            safe_sync_node_index(node)


def _sync_deletions(items: list[tuple[str, str]]) -> None:
    """对刚删的节点逐一从 ChromaDB 移除向量; 事务必须先提交避免脏写。

    Chroma 故障不回滚 SQLite 删除: 主数据源已经移除, 残留向量再调一次
    delete_node 即可清理, 日志保留排查线索即可。
    """
    for project_id, node_id in items:
        try:
            delete_node_vectors(project_id, node_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "delete chroma 失败 project=%s node=%s: %s", project_id, node_id, exc
            )