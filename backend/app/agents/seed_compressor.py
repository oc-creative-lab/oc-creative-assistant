"""项目种子压缩器（first_revision 阶段 5）。

独立 entrypoint，【不在主对话 StateGraph 内】：把一个项目的当前状态（所有节点，
按 sub-graph 分区）压成结构化种子 JSON（worldview / characters / plot / style），
供 Chat Agent 启动时低成本注入（决策 4：种子 ~500 tokens）。

由 project_service.rebuild_seed 调用并落到 ProjectSeedORM；触发来源包括聊天会话
关闭、工作台保存 debounce、手动 rebuild API。
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.schemas import SeedOutput
from app.db.database import SessionLocal
from app.db.models import NodeORM, ProjectORM
from app.llm.factory import get_llm_provider
from app.services.graph_repository import read_ordered_nodes


_SYSTEM_PROMPT = (
    "你是创作助手的项目种子压缩器。任务: 把下面这个项目的当前节点状态压成一份"
    "结构化快照, 供对话助手开场时快速了解项目全貌。只做客观概括, 不要新增设定、"
    "不要发挥剧情。worldview_summary 用 2-3 句话概括世界观; main_characters 列出"
    "主要角色名(最多 8 个); plot_outline 用 2-4 句概括当前剧情走向; style_notes "
    "概括基调/风格(没有就留空)。"
)


def _collect_project_brief(project_id: str) -> tuple[str, str]:
    """读取项目名 + 按类型分组的节点清单，拼成压缩输入文本。"""
    with SessionLocal() as db:
        project = db.get(ProjectORM, project_id)
        project_name = project.name if project is not None else project_id
        nodes = read_ordered_nodes(db, project_id)

    grouped: dict[str, list[NodeORM]] = {}
    for node in nodes:
        grouped.setdefault(node.node_type, []).append(node)

    lines: list[str] = [f"项目名: {project_name}"]
    for node_type, items in grouped.items():
        lines.append(f"\n[{node_type}]")
        for node in items:
            content = (node.content or "").strip().replace("\n", " ")
            lines.append(f"- {node.title}: {content[:120]}")

    return project_name, "\n".join(lines)


def build_seed_json(project_id: str) -> str | None:
    """生成项目种子 JSON 字符串；项目无内容或 LLM 失败时返回 None。

    返回 None 时由调用方决定回退策略（project_service 用占位种子兜底）。
    """
    _, brief = _collect_project_brief(project_id)
    if brief.count("\n") <= 1:  # 仅有项目名一行 → 项目还没内容
        return None

    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(f"【项目当前节点】\n{brief}"),
    ]
    try:
        seed = get_llm_provider().structured(messages, SeedOutput)
    except Exception:
        return None

    return json.dumps(
        {
            "worldview_summary": seed.worldview_summary,
            "main_characters": seed.main_characters,
            "plot_outline": seed.plot_outline,
            "style_notes": seed.style_notes,
        },
        ensure_ascii=False,
    )
