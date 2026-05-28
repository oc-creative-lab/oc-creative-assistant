"""研究 agent 节点。

接收"考据型"意图(查项目里写过什么、对比、总结), 在 ReAct 循环里按需调用
search_nodes / get_node / list_neighbors 收集证据, 最终给出 ResearchOutput。

工具调用结果是 LLM 陈述的唯一依据; prompt 里的"必须先调用工具"约束让 agent
不会绕过知识库凭空编造, 把"何时还要再查一次"的判断权交还给 LLM。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import ResearchOutput
from app.agents.state import AgentState
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("research")


def research_agent_node(state: AgentState) -> dict[str, Any]:
    """ReAct 循环里收集证据后产出 ResearchOutput; LLM 失败时降级到空总结。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state, 'research')}\n\n"
            f"【用户问题】\n{user_message}"
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        output = provider.structured(
            compact_history_for_structured(history), ResearchOutput
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("research_agent LLM 调用失败, 降级: %s", error)
        output = ResearchOutput(
            reasoning=f"调用失败 ({type(error).__name__})。",
            summary="我这次没能查到相关内容, 你可以换种问法或稍后重试。",
        )
    return {"research_output": output}