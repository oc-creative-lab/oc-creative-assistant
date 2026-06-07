"""Conversation summary compression node.

Runs after persistence_hub, feeding the "old messages" beyond keep_recent + the
existing summary to the LLM, and writes a new version of
``conversation_summary`` back to ChatSessionORM.

The throttling strategy is based on the high-water mark
``summary_message_count``: it compresses again only when the newly accumulated
old messages exceed ``summary_compress_every``, avoiding triggering the LLM
every turn.

When the LLM fails it does not block the main path: after catching the
exception it keeps the old summary as is, so a reply the user has already
received is not rolled back due to a failed post-hoc summary.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents.schemas import SummaryOutput
from app.agents.state import AgentState
from app.core.settings import get_agent_settings
from app.db.database import SessionLocal
from app.db.models import ChatMessageORM, ChatSessionORM
from app.llm.factory import get_llm_provider
from app.services.chat_repository import update_session_summary
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = load_prompt("summary_compress")


def _format_messages_for_prompt(messages: list[ChatMessageORM]) -> str:
    lines: list[str] = []
    for record in messages:
        content = (record.content or "").strip()
        lines.append(f"- {record.role}: {content}")
    return "\n".join(lines) or "(none)"


def summary_compress_node(state: AgentState) -> dict[str, Any]:
    session_id = state.get("session_id", "")
    if not session_id:
        return {}

    settings = get_agent_settings()
    keep_recent = settings.summary_keep_recent
    compress_every = settings.summary_compress_every

    with SessionLocal() as db:
        session = db.get(ChatSessionORM, session_id)
        if session is None:
            return {}

        ordered_messages = list(
            db.scalars(
                select(ChatMessageORM)
                .where(ChatMessageORM.session_id == session_id)
                .order_by(ChatMessageORM.created_at)
            )
        )

        total = len(ordered_messages)
        new_high_water = total - keep_recent
        if new_high_water <= session.summary_message_count:
            return {}
        if new_high_water - session.summary_message_count < compress_every:
            return {}

        previous_summary = session.conversation_summary or ""
        old_messages = ordered_messages[session.summary_message_count : new_high_water]

    user_block = (
        f"[Existing summary (may be empty)]\n{previous_summary or '(empty)'}\n\n"
        f"[Conversation segments to merge into the summary this time]\n{_format_messages_for_prompt(old_messages)}\n\n"
        "Output the updated summary and key_facts."
    )
    messages_for_llm = [SystemMessage(_SYSTEM_PROMPT), HumanMessage(user_block)]

    try:
        output = get_llm_provider().structured(messages_for_llm, SummaryOutput)
    except Exception as error:  # noqa: BLE001
        logger.warning("summary_compress LLM call failed, keeping the old summary: %s", error)
        return {}

    with SessionLocal.begin() as db:
        update_session_summary(
            db,
            session_id=session_id,
            summary=output.summary,
            key_facts=list(output.key_facts),
            message_count=new_high_water,
        )

    return {
        "conversation_summary": output.summary,
        "key_facts": list(output.key_facts),
    }