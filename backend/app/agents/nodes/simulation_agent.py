"""推演 agent 节点。

接收"如果...会怎样"的假设性意图, 在 ReAct 循环里先用 search_nodes 锁定
相关节点把"现状"作为锚点, 再生成 2-3 条互不相同的可能走向, 输出
SimulationOutput。本模式永不产出 proposed_changes; 用户挑中分支后,
落地由下一轮自然切到结构模式接力。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import SimulationOutput
from app.agents.state import AgentState
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("simulation")


def simulation_agent_node(state: AgentState) -> dict[str, Any]:
    """ReAct 循环里锚定现状后推演分支; LLM 失败时降级到空 branches。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(f"{build_memory_block(state)}\n\n【用户假设】\n{user_message}"),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        output = provider.structured(
            compact_history_for_structured(history), SimulationOutput
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("simulation_agent LLM 调用失败, 降级: %s", error)
        output = SimulationOutput(
            reasoning=f"调用失败 ({type(error).__name__}), 暂时无法推演分支。",
            branches=[],
        )
    return {"simulation_output": output}