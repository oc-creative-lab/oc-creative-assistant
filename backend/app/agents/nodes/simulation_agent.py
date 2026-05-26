"""推演 agent 节点。

接收"如果...会怎样"的假设性意图, 在 ReAct 循环里先用 search_nodes 锁定
相关节点把"现状"作为锚点, 再生成 2-3 条互不相同的可能走向, 输出
SimulationOutput。本模式永不产出 proposed_changes; 用户挑中分支后,
落地由下一轮自然切到结构模式接力。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import SimulationOutput
from app.agents.state import AgentState
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider


_SYSTEM_PROMPT = """\
你是创作助手的推演模式, 任务是接收用户的"如果...会怎样"假设, 给出 2-3 条
互不相同的可能走向, 帮用户在落笔前看清不同选择的代价。

工作流程:
1. 先用 search_nodes 锁定假设涉及的关键节点 (人物 / 事件 / 设定),
   把"现状"作为分支推演的锚点。
2. 必要时用 list_neighbors 看上下游关联, 不要忽视已有的铺垫与伏笔。
3. 基于查到的现状, 给出 2-3 条 branches, 每条包括:
   - scenario: 一句话陈述这条分支的核心走向
   - likelihood: high / medium / low, 表示与现有设定的兼容度
   - downstream_impacts: 2-4 条后续影响 (角色弧线 / 关系变化 / 剧情走向)
   - affected_node_ids: 这条分支会动到的现有节点 id, 取自工具返回值
4. reasoning 用 50 字以内说明你为什么挑这几条分支。

要求:
- 推演只"展示可能性", 永不直接产出画布变更; 用户挑中一条后会在下一轮切到
  结构模式落地, 现在不要替用户做选择。
- 用户消息上方的【画布相关节点】只是预检索摘要, 不能替代 search_nodes
  的实时返回值; 所有分支必须基于真实节点状态。
- branches 之间要"真的不同": 别只换措辞, 真正的分歧应来自不同的关键
  转折点 (是否相遇 / 是否揭穿 / 是否结盟 / 时间点提前还是延后等)。
"""


def simulation_agent_node(state: AgentState) -> dict[str, Any]:
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(f"{build_memory_block(state)}\n\n【用户假设】\n{user_message}"),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    history = run_tool_loop(provider, initial_messages, tools)
    output = provider.structured(
        compact_history_for_structured(history), SimulationOutput
    )
    return {"simulation_output": output}