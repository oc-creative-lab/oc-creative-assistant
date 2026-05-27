"""意图分类节点。

把用户最新一轮消息归类到一个 agent 类型上, 写入 state.intent, 让下游
graph 按 intent 路由到对应 agent。空消息直接归 small_talk 兜底, 不调
LLM 节省成本。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.schemas import IntentClassification
from app.agents.state import AgentState
from app.llm.factory import get_llm_provider
from app.agents.prompts import load_prompt


_SYSTEM_PROMPT = load_prompt("intent_router")


def intent_router_node(state: AgentState) -> dict[str, Any]:
    """根据用户消息 + 近期对话决定 IntentClassification; 空消息直接 small_talk。"""
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {
            "intent": IntentClassification(primary="small_talk", reasoning="用户消息为空。"),
        }

    recent = state.get("recent_messages") or []
    history = "\n".join(f"{m['role']}: {m['content']}" for m in recent[-4:])
    history_block = f"【近期对话】\n{history}\n\n" if history else ""

    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(f"{history_block}【最新消息】\n{user_message}"),
    ]

    intent = get_llm_provider().structured(messages, IntentClassification)
    return {"intent": intent}