"""提问规划节点（Agent B 之二，first_revision 决策 5）。

在 chat_assembler 之前运行：根据种子 / 最近对话 / 待补字段，规划对话助手下一步
该自然追问的方向，写入 ``state.next_question_hint`` 供装配器拼进回复。

仅在 ``extraction_enabled`` 为真（ChatWorkspace 全屏聊天模式）时工作；关闭时
直接 no-op，保证 FloatingChatDock 旧流程行为与成本完全不变。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import load_prompt
from app.agents.schemas import QuestionPlannerOutput
from app.agents.state import AgentState
from app.llm.factory import get_llm_provider


_SYSTEM_PROMPT = load_prompt("question_planner")


def question_planner_node(state: AgentState) -> dict[str, Any]:
    if not state.get("extraction_enabled"):
        return {}

    recent = state.get("recent_messages") or []
    history = "\n".join(f"{m['role']}: {m['content']}" for m in recent[-6:]) or "(无)"
    deferred = state.get("deferred_fields") or []
    deferred_block = (
        "\n".join(f"- {d.get('entity')}: {d.get('field')}" for d in deferred) or "(无)"
    )
    seed = (state.get("seed_context") or state.get("world_brief") or "").strip()

    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"【项目种子/背景】\n{seed[:500] or '(暂无)'}\n\n"
            f"【最近对话】\n{history}\n\n"
            f"【待补字段】\n{deferred_block}\n\n"
            f"【用户最新消息】\n{state.get('user_message', '')}"
        ),
    ]

    try:
        out = get_llm_provider().structured(messages, QuestionPlannerOutput)
    except Exception:
        # 规划失败不应阻断回复，hint 留空即可。
        return {}

    return {"next_question_hint": out.next_question}
