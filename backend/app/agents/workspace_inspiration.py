"""工作台轻量灵感 agent（second_revision 改点 B / W5）。

独立的被动 agent，【不在主对话 StateGraph 内】，也【不复用 ChatWorkspace 的
question_planner】（职责不同：前者主动推进，本 agent 只在用户发消息时被动回应）。

输入：项目 id + 用户消息 + 引用的节点 id。
输出：一条 WorkspaceInspirationOutput（type ∈ search/rag/question/feedback + content），
由 SSE 推给前端，按 type 分发到右栏不同卡片。
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import load_prompt
from app.agents.schemas import WorkspaceInspirationOutput
from app.db.database import SessionLocal
from app.db.models import NodeORM
from app.llm.factory import get_llm_provider


_SYSTEM_PROMPT = load_prompt("workspace_inspiration")


def _quoted_block(project_id: str, node_ids: list[str]) -> str:
    """把引用节点的标题 + 内容拼成提示块；无引用时返回占位。"""
    if not node_ids:
        return "(无引用节点)"
    with SessionLocal() as db:
        lines: list[str] = []
        for node_id in node_ids:
            node = db.get(NodeORM, node_id)
            if node is None or node.project_id != project_id:
                continue
            content = (node.content or "").strip().replace("\n", " ")
            lines.append(f"- [{node.node_type}] {node.title}: {content[:160]}")
    return "\n".join(lines) or "(无有效引用节点)"


def generate_workspace_output(
    project_id: str,
    message: str,
    quoted_node_ids: list[str],
) -> WorkspaceInspirationOutput:
    """同步生成一条工作台灵感输出；LLM 失败时退化为一条鼓励反馈。"""
    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"【引用节点】\n{_quoted_block(project_id, quoted_node_ids)}\n\n"
            f"【用户消息】\n{message}"
        ),
    ]
    try:
        return get_llm_provider().structured(messages, WorkspaceInspirationOutput)
    except Exception:
        return WorkspaceInspirationOutput(
            reasoning="LLM 不可用，退化反馈",
            type="feedback",
            content="我先记下了。你可以继续展开这个想法，或选中相关节点一起发给我。",
        )
