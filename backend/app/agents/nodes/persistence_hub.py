"""持久化中枢节点。

每轮把以下副作用分两段独立事务落库:
1. user_message 独立入库 (单独事务); 即使后续 chat_assembler 失败, 用户消息
   也已经 commit, 下一轮 recent_messages 不会出现单边断档。
2. assembler_output 存在时, 在第二段事务里追加 assistant_message; 当轮
   agent 输出含 proposed_changes 的话, 同事务内写入同一 batch_id 的
   AgentStaging, 等用户在前端 staging 面板接受 / 编辑 / 拒绝。

session 不存在时整体静默跳过, 让 graph.invoke 仍能返回一份 in-memory 的
assembler_output 给调用方做兜底。
"""

from __future__ import annotations

from typing import Any

from app.agents.schemas import ProposedChange
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import ChatSessionORM
from app.schemas import AgentStagingCreateItem
from app.services.chat_repository import append_message, insert_staging_batch


_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
}
"""仅这三类 agent 会产出 proposed_changes; simulation 物理隔离, 不进。"""


def _collect_proposed_changes(state: AgentState) -> tuple[list[ProposedChange], str]:
    """从当前 intent 对应 agent 的输出里取 proposed_changes; 没有就回空列表。

    agent_type 取 intent.primary, 让 staging 表能按 agent 来源分组展示。
    """
    intent = state.get("intent")
    primary = intent.primary if intent is not None else ""
    output_key = _OUTPUT_KEY_BY_INTENT.get(primary)
    if output_key is None:
        return [], primary

    output = state.get(output_key)
    if output is None:
        return [], primary

    changes = list(getattr(output, "proposed_changes", []) or [])
    return changes, primary


def _to_staging_items(changes: list[ProposedChange]) -> list[AgentStagingCreateItem]:
    """ProposedChange (agent 内部模型) → AgentStagingCreateItem (持久化模型)。"""
    return [
        AgentStagingCreateItem(
            change_type=change.change_type,
            target_id=change.target_id,
            pending_id=change.pending_id,
            payload=change.payload,
            reasoning=change.reason,
        )
        for change in changes
    ]


def persistence_hub_node(state: AgentState) -> dict[str, Any]:
    session_id = state.get("session_id", "")
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()
    assembler = state.get("assembler_output")

    if not session_id:
        return {}

    # 第一段事务: 用户消息独立入库, 与 assembler 成败解耦
    with SessionLocal.begin() as db:
        if db.get(ChatSessionORM, session_id) is None:
            return {}
        if user_message:
            append_message(db, session_id=session_id, role="user", content=user_message)

    if assembler is None:
        return {}

    proposed_changes, agent_type = _collect_proposed_changes(state)
    staging_items = _to_staging_items(proposed_changes)

    # 第二段事务: assistant_message 与 staging 共享同一事务, 保证消息与
    # batch 的引用一致性 (staging 行 message_id 必然指向真实存在的消息)
    with SessionLocal.begin() as db:
        meta: dict[str, Any] = {
            "agent_type": agent_type,
            "cited_node_ids": list(assembler.cited_node_ids),
            "staging_summary": assembler.staging_summary,
        }
        assistant_message = append_message(
            db,
            session_id=session_id,
            role="assistant",
            content=assembler.reply_text,
            meta=meta,
        )
        assistant_message_id = assistant_message.id

        batch_id: str | None = None
        if staging_items:
            batch_id, _ = insert_staging_batch(
                db,
                session_id=session_id,
                message_id=assistant_message_id,
                project_id=project_id,
                agent_type=agent_type,
                items=staging_items,
            )

    return {
        "assistant_message_id": assistant_message_id,
        "staging_batch_id": batch_id,
        "staging_count": len(staging_items),
    }