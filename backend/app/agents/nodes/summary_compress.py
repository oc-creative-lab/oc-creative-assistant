"""会话摘要压缩节点。

跑在 persistence_hub 之后, 把 keep_recent 之外的"老消息" + 已有 summary 喂给
LLM, 输出新一版 ``conversation_summary`` 写回 ChatSessionORM。

节流策略基于高水位 ``summary_message_count``: 只有当新累积的老消息超过
``summary_compress_every`` 才再压一次, 避免每轮都触发 LLM。

LLM 失败时不阻断主链路: 捕获异常后保持旧 summary 原样, 让用户已经收到的
回复不会因为后置摘要失败而被回滚。
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
    return "\n".join(lines) or "(无)"


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
        f"【已有 summary (可能为空)】\n{previous_summary or '(空)'}\n\n"
        f"【这次需要并入 summary 的对话片段】\n{_format_messages_for_prompt(old_messages)}\n\n"
        "请输出更新后的 summary 与 key_facts。"
    )
    messages_for_llm = [SystemMessage(_SYSTEM_PROMPT), HumanMessage(user_block)]

    try:
        output = get_llm_provider().structured(messages_for_llm, SummaryOutput)
    except Exception as error:  # noqa: BLE001
        logger.warning("summary_compress LLM 调用失败, 保持旧 summary: %s", error)
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