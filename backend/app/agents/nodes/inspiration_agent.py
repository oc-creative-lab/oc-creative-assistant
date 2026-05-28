"""灵感发散 agent 节点。

调用 LlmProvider 输出 InspirationOutput, 强制带 reasoning 字段显式吐出 CoT 推理。
Prompt 由 build_memory_block 注入多层记忆 + RAG 上下文, 让 LLM 在已有世界观和近期
对话内发散, 不脱离用户语境。

工具是"可选"的: LLM 自己判断"我这条建议要不要先用 search_nodes 核验一下项目里有没有
类似节点"。research_agent 强制必查工具的策略不适合发散场景, 这里靠 ReAct early-exit
机制让 LLM 没问题时直接收口, 一轮不调工具也合法。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import InspirationOutput
from app.agents.state import AgentState
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("inspiration")


def inspiration_agent_node(state: AgentState) -> dict[str, Any]:
    """通过 ReAct 循环可选地查证, 产出 InspirationOutput; LLM 失败时降级。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()

    if not user_message:
        empty = InspirationOutput(reasoning="用户消息为空, 跳过推理。", suggestions=[])
        return {"inspiration_output": empty}

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state, 'inspiration')}\n\n"
            f"【用户问题】\n{user_message}"
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        output = provider.structured(
            compact_history_for_structured(history), InspirationOutput
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("inspiration_agent LLM 调用失败, 降级: %s", error)
        output = InspirationOutput(
            reasoning=f"调用失败 ({type(error).__name__}), 暂时无法发散灵感。",
            suggestions=[],
        )
    return {"inspiration_output": output}