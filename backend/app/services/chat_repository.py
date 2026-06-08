"""Database operation helpers for chat and staging.

This is the persistence boundary between the service layer and the ORM,
responsible for CRUD on the three tables: sessions, messages, and staging.
The transaction strategy aligns with graph_repository: write operations are
wrapped by the caller in a ``SessionLocal.begin`` transaction, while read
operations each open their own independent session.
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
    """Generate a 32-character hex UUID, used as table primary key and LangGraph thread_id."""
    return uuid.uuid4().hex


def require_session(db: Session, session_id: str) -> ChatSessionORM:
    """Read a session and ensure it exists; raises 404 if not."""
    session = db.get(ChatSessionORM, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


def require_message(db: Session, message_id: str) -> ChatMessageORM:
    """Read a message and ensure it exists; raises 404 if not."""
    message = db.get(ChatMessageORM, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    return message


def require_staging(db: Session, staging_id: str) -> AgentStagingORM:
    """Read a staging record and ensure it exists; raises 404 if not."""
    record = db.get(AgentStagingORM, staging_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Staging item not found")
    return record


def insert_session(db: Session, *, project_id: str, title: str = "") -> ChatSessionORM:
    """Create a session, auto-assigning an id; ``thread_id`` reuses the same id, one-to-one."""
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
    """List sessions under a project, newest created first."""
    return list(
        db.scalars(
            select(ChatSessionORM)
            .where(ChatSessionORM.project_id == project_id)
            .order_by(ChatSessionORM.created_at.desc())
        )
    )


def delete_session(db: Session, session_id: str) -> None:
    """Delete a session; messages / staging cascade via FK ondelete=CASCADE."""
    record = require_session(db, session_id)
    db.delete(record)
    db.flush()


def rename_session(db: Session, session_id: str, title: str) -> ChatSessionORM:
    """Update a session's title."""
    record = require_session(db, session_id)
    record.title = title
    db.flush()
    return record

    
def list_session_messages(db: Session, session_id: str) -> list[ChatMessageORM]:
    """List session messages in chronological order."""
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
    """Append a message without modifying existing records."""
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
    """Persist multiple changes from the same Agent turn into the staging table, sharing one batch_id."""
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
    """List staging by session, optionally filtered by status; ordered by batch creation time + order within batch."""
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
    """List staging by project (first_revision phase 4: ChatWorkspace cross-session pending-review aggregation)."""
    stmt = (
        select(AgentStagingORM)
        .where(AgentStagingORM.project_id == project_id)
        .order_by(AgentStagingORM.created_at, AgentStagingORM.order_in_batch)
    )
    if status:
        stmt = stmt.where(AgentStagingORM.status == status)
    return list(db.scalars(stmt))


def list_staging_by_batch(db: Session, batch_id: str) -> list[AgentStagingORM]:
    """Read all changes for a given batch, returned in order within the batch."""
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
    """State machine transition; only transitions out of pending are allowed, operating again on a resolved record returns 409."""
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
    """Write back the conversation summary + core facts layer + high-water mark; silently skips if it does not exist.

    key_facts is designed as a "cumulative merge": new facts are deduplicated
    against the old ones and appended, so key settings accumulated early are not
    overwritten by this round. Duplicate facts are roughly detected
    case-insensitively + whitespace-stripped, so the LLM's likely repeated
    phrasings get absorbed.
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