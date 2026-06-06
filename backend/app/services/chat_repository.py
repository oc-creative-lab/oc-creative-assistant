"""对话与 staging 的数据库操作 helper。

属于服务层与 ORM 之间的持久化边界, 负责会话、消息、staging 三张表的 CRUD。
事务策略与 graph_repository 对齐: 写操作由调用方包在 ``SessionLocal.begin``
事务内, 读操作各自打开独立 session。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentStagingORM, ChatMessageORM, ChatSessionORM
from app.schemas import AgentStagingCreateItem


def new_id() -> str:
    """生成 32 位 hex UUID, 作为表主键和 LangGraph thread_id。"""
    return uuid.uuid4().hex


def require_session(db: Session, session_id: str) -> ChatSessionORM:
    """读取会话并确保存在; 不存在抛 404。"""
    session = db.get(ChatSessionORM, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


def require_message(db: Session, message_id: str) -> ChatMessageORM:
    """读取消息并确保存在; 不存在抛 404。"""
    message = db.get(ChatMessageORM, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    return message


def require_staging(db: Session, staging_id: str) -> AgentStagingORM:
    """读取 staging 并确保存在; 不存在抛 404。"""
    record = db.get(AgentStagingORM, staging_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Staging item not found")
    return record


def insert_session(db: Session, *, project_id: str, title: str = "") -> ChatSessionORM:
    """创建会话, 自动分配 id; ``thread_id`` 直接用同一个 id, 一一对应。"""
    session_id = new_id()
    record = ChatSessionORM(
        id=session_id,
        project_id=project_id,
        thread_id=session_id,
        title=title,
        conversation_summary="",
    )
    db.add(record)
    db.flush()
    return record


def list_project_sessions(db: Session, project_id: str) -> list[ChatSessionORM]:
    """列出项目下的会话, 最新创建在前。"""
    return list(
        db.scalars(
            select(ChatSessionORM)
            .where(ChatSessionORM.project_id == project_id)
            .order_by(ChatSessionORM.created_at.desc())
        )
    )


def list_session_messages(db: Session, session_id: str) -> list[ChatMessageORM]:
    """列出会话消息, 时间正序。"""
    return list(
        db.scalars(
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at)
        )
    )


def append_message(
    db: Session,
    *,
    session_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> ChatMessageORM:
    """追加一条消息, 不修改既有记录。"""
    record = ChatMessageORM(
        id=new_id(),
        session_id=session_id,
        role=role,
        content=content,
        meta=meta or {},
    )
    db.add(record)
    db.flush()
    return record


def insert_staging_batch(
    db: Session,
    *,
    session_id: str,
    message_id: str,
    project_id: str,
    agent_type: str,
    items: list[AgentStagingCreateItem],
) -> tuple[str, list[AgentStagingORM]]:
    """把同一 Agent turn 的多条变更落入 staging 表, 共享同一 batch_id。"""
    batch_id = new_id()
    records: list[AgentStagingORM] = []
    for index, item in enumerate(items):
        record = AgentStagingORM(
            id=new_id(),
            session_id=session_id,
            message_id=message_id,
            project_id=project_id,
            batch_id=batch_id,
            change_type=item.change_type,
            target_id=item.target_id,
            pending_id=item.pending_id,
            payload=item.payload,
            payload_edited=None,
            agent_type=agent_type,
            reasoning=item.reasoning,
            order_in_batch=index,
            status="pending",
        )
        db.add(record)
        records.append(record)
    db.flush()
    return batch_id, records


def list_staging_by_session(
    db: Session,
    session_id: str,
    status: str | None = None,
) -> list[AgentStagingORM]:
    """按会话列出 staging, 可按 status 过滤; 排序按 batch 创建时间 + 批内顺序。"""
    stmt = (
        select(AgentStagingORM)
        .where(AgentStagingORM.session_id == session_id)
        .order_by(AgentStagingORM.created_at, AgentStagingORM.order_in_batch)
    )
    if status:
        stmt = stmt.where(AgentStagingORM.status == status)
    return list(db.scalars(stmt))


def list_staging_by_project(
    db: Session,
    project_id: str,
    status: str | None = None,
) -> list[AgentStagingORM]:
    """按项目列出 staging。"""
    stmt = (
        select(AgentStagingORM)
        .where(AgentStagingORM.project_id == project_id)
        .order_by(AgentStagingORM.created_at, AgentStagingORM.order_in_batch)
    )
    if status:
        stmt = stmt.where(AgentStagingORM.status == status)
    return list(db.scalars(stmt))


def list_staging_by_batch(db: Session, batch_id: str) -> list[AgentStagingORM]:
    """读取指定 batch 的所有变更, 按批内顺序返回。"""
    return list(
        db.scalars(
            select(AgentStagingORM)
            .where(AgentStagingORM.batch_id == batch_id)
            .order_by(AgentStagingORM.order_in_batch)
        )
    )


def transition_staging(
    record: AgentStagingORM,
    *,
    new_status: str,
    payload_edited: dict[str, Any] | None = None,
) -> None:
    """状态机迁移; 只允许从 pending 转出, 已结案再次操作返回 409。"""
    if record.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Staging item already resolved (status={record.status})",
        )
    record.status = new_status
    record.resolved_at = datetime.now(timezone.utc)
    if payload_edited is not None:
        record.payload_edited = payload_edited

def update_session_summary(
    db: Session,
    *,
    session_id: str,
    summary: str,
    key_facts: list[str],
    message_count: int,
) -> None:
    """写回会话摘要 + 核心事实层 + 高水位; 不存在则静默跳过。

    key_facts 设计为"累积合并": 新 facts 跟旧的去重后拼接, 让早期沉淀的
    关键设定不会被本轮覆盖。重复 fact 用大小写不敏感 + 去空白来粗判,
    LLM 大概率重复表述会被吸收。
    """
    record = db.get(ChatSessionORM, session_id)
    if record is None:
        return
    record.conversation_summary = summary

    existing = list(record.key_facts or [])
    seen = {fact.strip().lower() for fact in existing}
    for fact in key_facts:
        normalized = fact.strip()
        if normalized and normalized.lower() not in seen:
            existing.append(normalized)
            seen.add(normalized.lower())
    record.key_facts = existing

    record.summary_message_count = message_count