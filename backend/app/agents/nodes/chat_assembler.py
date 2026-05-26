"""对话装配器节点。

读取当前 intent 对应那个 agent 的结构化输出, 用 LLM 把它翻译成自然语言
回复; small_talk 走单独的轻量 prompt, 让闲聊不被项目上下文里的角色名
干扰成"伪装用户名"。

cited_node_ids 与 staging_summary 由 LLM 一并产出, 让前端能在气泡尾部
展示"我准备改 N 处"的提示。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import ChatAssemblerOutput
from app.agents.state import AgentState
from app.llm.factory import get_llm_provider


_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
    "simulation": "simulation_output",
}


_SMALL_TALK_PROMPT = """\
你是创作助手, 用户在闲聊或寒暄, 给一句温暖、简短 (40 字内) 的中文回应,
顺手提醒用户你能帮忙做什么 (例如发散灵感、查项目里写过的设定、建角色与关系网),
让对话能自然进入创作主题。

- reply_text: 一两句话, 不要写编号清单
- cited_node_ids: 留空数组
- staging_summary: 留空字符串
"""


_SYSTEM_PROMPT = """\
你是创作助手的对话装配器, 把内部 agent 的结构化输出翻译成自然、亲切的中文回复,
让用户感觉自己在和"一个人"对话, 而不是看 JSON 报告。

规则:
- reply_text: 直接面向用户, 不要用第三人称, 不要复述 reasoning 的字面内容,
  把推理过程自然融入语气; 整体控制在 280 字以内
- 输出含 suggestions 时, 用编号列出 (1. 2. 3.)
- 输出含 branches (推演) 时, 用"如果 X / 那么 Y"的结构逐条展开,
  每条带一个 likelihood 提示 (高/中/低 可能), 列 1-2 条最关键的后续影响
- 没有列表时围绕 summary 自然展开
- cited_node_ids: 取 referenced_node_ids 与 branches[*].affected_node_ids
  的去重并集
- staging_summary: 仅当 proposed_changes 非空时填一行
  "我准备帮你新增 N 处, 等你确认。", 否则留空字符串

重要 - 副作用的措辞:
- 任何 proposed_changes 都还在 staging 等用户确认, 别用 "我已经把...建好了/挂上了"
  这种过去完成时, 改用 "我准备帮你..." / "建议你新增..." 这类未落地措辞;
- 看到【边界检查跳过的项】时, 在 reply_text 里如实说明被跳过的关键原因,
  不要假装这些项已经做完。

不要编造结构化输出里没有的信息, 也不要省略关键内容。
"""


def _build_small_talk_brief(state: AgentState) -> str:
    """只暴露世界观纲要的最高层信息, 屏蔽节点级和对话级的具体人名,
    避免 LLM 在闲聊时把项目角色当成用户的名字。
    """
    world_brief = (state.get("world_brief") or "").strip()
    if not world_brief:
        return "(暂无项目背景)"
    head = world_brief[:120]
    return f"【项目背景速览】\n{head}"


def _assemble_small_talk(state: AgentState) -> ChatAssemblerOutput:
    user_message = state.get("user_message", "")
    messages = [
        SystemMessage(_SMALL_TALK_PROMPT),
        HumanMessage(
            f"{_build_small_talk_brief(state)}\n\n【用户最新消息】\n{user_message}"
        ),
    ]
    return get_llm_provider().structured(messages, ChatAssemblerOutput)


def chat_assembler_node(state: AgentState) -> dict[str, Any]:
    intent = state.get("intent")
    primary = intent.primary if intent is not None else ""

    if primary == "small_talk":
        return {"assembler_output": _assemble_small_talk(state)}

    output_key = _OUTPUT_KEY_BY_INTENT.get(primary)
    output = state.get(output_key) if output_key else None
    if output is None:
        return {
            "assembler_output": ChatAssemblerOutput(
                reply_text="我这一轮没拿到合适的结果, 不如再多说几句你想要的方向?"
            ),
        }

    user_message = state.get("user_message", "")
    warnings = state.get("boundary_warnings") or []
    if warnings:
        joined = "\n".join(f"- {item}" for item in warnings)
        warning_block = f"\n\n【边界检查跳过的项】\n{joined}"
    else:
        warning_block = ""

    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state)}\n\n"
            f"【用户最新消息】\n{user_message}\n\n"
            f"【主导意图】\n{primary}\n\n"
            f"【agent 结构化输出】\n{output.model_dump_json()}"
            f"{warning_block}\n\n"
            "请把以上结构化输出装配成一段自然语言回复; 注意不要重复"
            "【最近对话】里你已经说过的话, 让回复有连续感而不是从头解释。"
        ),
    ]

    assembled = get_llm_provider().structured(messages, ChatAssemblerOutput)
    return {"assembler_output": assembled}