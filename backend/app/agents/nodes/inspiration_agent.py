"""灵感发散 agent 节点。

调用 LlmProvider.structured 输出 InspirationOutput, 强制带 reasoning 字段
显式吐出 CoT 推理。Prompt 由 build_memory_block 注入多层记忆 + RAG 上下文,
让 LLM 在已有世界观和近期对话内发散, 不脱离用户语境。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import InspirationOutput
from app.agents.state import AgentState
from app.llm.factory import get_llm_provider

_SYSTEM_PROMPT = """\
你是创作助手的"灵感发散"模式: 围绕用户已有世界观, 抛出 3-5 条开放式建议,
而不是替用户决定。

输出严格遵守以下契约:
- reasoning: 一段简短推理, 解释你为什么给出这些建议 (50 字以内)
- suggestions: 3-5 条建议, 每条不超过 60 字, 与用户当前节点和已有内容呼应
- referenced_node_ids: 建议中引用到的现有节点 id, 没有则留空数组
- proposed_changes: 0-2 条 create_node 建议; 仅当你的灵感包含一个具体的新角色
  或新概念时才填写, 否则保持空数组。每条变更形如:
    change_type: "create_node"
    pending_id: 同 batch 内占位 id, 用 "pending-1" / "pending-2" 这类简短字符串
    payload: {"title": <标题>, "content": <一句话设定>,
             "node_type": "character" | "worldbuilding" | "plot"
                          | "idea" | "research" | "structure"}
    reason: 一句话说明为什么建议这个新节点

记住: 你的角色是"陪伴"而不是"代笔"。proposed_changes 是给用户的"建议",
最终接受与否由用户决定; 没有具体新概念时就留空数组, 不要硬塞。

自反思要求 (写到 reasoning 字段, 50 字内):
- proposed_changes 默认空; 仅当你的 suggestions 里包含一个具体可命名的新概念
  (人物 / 设定 / 事件) 时才填; 不要为了"显得在做事"而硬塞一条;
- 一旦填了 proposed_changes, 在 reasoning 里给出"为什么这条值得新建"的判断,
  不写就视同未深思, 别冲业绩。
"""


def inspiration_agent_node(state: AgentState) -> dict[str, Any]:
    """根据 RAG 上下文与用户消息生成 InspirationOutput; 空消息直接降级。"""
    user_message = state.get("user_message", "").strip()

    if not user_message:
        empty = InspirationOutput(reasoning="用户消息为空, 跳过推理。", suggestions=[])
        return {"inspiration_output": empty}

    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state)}\n\n"
            f"【用户问题】\n{user_message}"
        ),
    ]

    output = get_llm_provider().structured(messages, InspirationOutput)
    return {"inspiration_output": output}