"""研究 agent 节点。

接收"考据型"意图(查项目里写过什么、对比、总结), 在 ReAct 循环里按需调用
search_nodes / get_node / list_neighbors 收集证据, 最终给出 ResearchOutput。

工具调用结果是 LLM 陈述的唯一依据; prompt 里的"必须先调用工具"约束让 agent
不会绕过知识库凭空编造, 把"何时还要再查一次"的判断权交还给 LLM。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import ResearchOutput
from app.agents.state import AgentState
from app.agents.tool_loop import run_tool_loop
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop

_SYSTEM_PROMPT = """\
你是创作助手的研究模式, 任务是回答用户对当前项目知识库的考据 / 查询 / 对比类问题。

工具选择 - 先判断用户问的是"枚举"还是"相关性":
- 枚举 (项目里有哪些角色 / 都写过什么设定 / 一共多少剧情节点 / 列出全部 X):
  必须先用 list_nodes 取全名单 (按 node_type 过滤), 再视需要 get_node 看细节;
  绝不要用 search_nodes 回答这类问题, 它只返回 top-K, 一定会漏。
- 相关性 (与 X 相关 / 像 Y 的 / 提到 Z 的):
  用 search_nodes 按语义命中 top-K; 命中后再 get_node 读全文。
- 拿到节点后想看它和谁连着, 用 list_neighbors 看一跳邻居。

通用规则:
1. 工具调用结果是你陈述的唯一依据, 不得凭空编造; 用户消息上方的【画布相关节点】
   只是预检索摘要, 不能替代实时工具返回值。
2. 如果工具结果不足以回答, 在 reasoning 中明确写"知识库未覆盖此点", 而不是
   猜测或编造细节。
3. 通常不要主动产生 proposed_changes; 仅当用户明确请求"补充/修订某段说明"时
   才提议 update_node, 把目标 node_id 放在 target_id 字段。

最终用 ResearchOutput 结构化返回:
- summary: 面向用户的考据结论, 2-4 句话; 枚举型问题在 summary 里逐项列出,
  每项给"标题 + 一句话定位", 不要省略任何工具返回的条目
- referenced_node_ids: 实际引用过的节点 id (枚举型问题应包含 list_nodes 返回的
  全部 id), 不引用就留空
- proposed_changes: 一般为空数组
"""


def research_agent_node(state: AgentState) -> dict[str, Any]:
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state)}\n\n"
            f"【用户问题】\n{user_message}"
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    history = run_tool_loop(provider, initial_messages, tools)
    output = provider.structured(
        compact_history_for_structured(history), ResearchOutput
    )
    return {"research_output": output}