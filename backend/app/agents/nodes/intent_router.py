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


_SYSTEM_PROMPT = """\
你是创作助手的意图路由器, 不要直接回答用户。

把用户最新一轮消息归类到下面其中之一:
- inspiration: 发散思路、补设定、开放探索 (例如"还能再写些什么")
- research: 在已有项目里查询 / 总结 / 对比 (例如"我写过哪些角色")
- structure: 批量新增节点和连线、建关系 (例如"帮我把 X 和 Y 建关系")
- simulation: 推演 "如果...会怎样" 类假设题
- small_talk: 寒暄 / 闲聊 / 简短确认 ("好的"、"谢谢"等), 不归入上面四种

confidence: 0-1 之间的浮点, 表示判断把握; 不确定时给 0.5。
reasoning: 30 字以内的判断依据。
"""


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