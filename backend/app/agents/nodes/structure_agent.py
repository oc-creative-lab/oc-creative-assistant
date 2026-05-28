"""结构化 agent 节点。

接收"建结构"意图(新增节点、批量建关系、整理人物族群等), 在 ReAct 循环里
先查重再提议, 输出 StructureOutput.proposed_changes 进 staging 等用户确认。

batch 内 create_edge 引用尚未落库的新节点时使用 pending_id, 持久化时由
canvas_apply 把 pending_id 翻译成真实 node_id, 解决"先节点后边"的依赖。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import StructureOutput
from app.agents.state import AgentState
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("structure")

def structure_agent_node(state: AgentState) -> dict[str, Any]:
    """ReAct 循环里查重并提议结构变更; LLM 失败时降级到空 proposed_changes。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state, 'structure')}\n\n"
            f"【用户请求】\n{user_message}"
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        output = provider.structured(
            compact_history_for_structured(history), StructureOutput
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("structure_agent LLM 调用失败, 降级: %s", error)
        output = StructureOutput(
            reasoning=f"调用失败 ({type(error).__name__})。",
            summary="我这次没能整理出建议结构, 你可以换种问法或稍后重试。",
        )
    return {"structure_output": output}