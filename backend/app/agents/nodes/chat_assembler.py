"""对话装配器节点。

读取当前 intent 对应那个 agent 的结构化输出, 用 LLM 把它翻译成自然语言回复;
small_talk 走单独的轻量 prompt, 让闲聊不被项目上下文里的角色名干扰成
"伪装用户名"。

为支持 token 级流式, 主路径拆成两步:
  Step 1 [流式]: chat_stream 生成 reply_text 纯文本, 每个 token 通过
                 get_stream_writer 推到 LangGraph custom stream 上
  Step 2 [非流式]: structured 调用从已生成的 reply_text 抽出
                   cited_node_ids 与 staging_summary

small_talk 文本极短, 不值得为它额外加 round-trip, 保留一次性 structured。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from app.agents.memory import build_memory_block
from app.agents.prompts import load_prompt
from app.agents.schemas import ChatAssemblerOutput, ChatMetadataOutput
from app.agents.state import AgentState
from app.llm.factory import get_llm_provider


_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
    "simulation": "simulation_output",
}


_SMALL_TALK_PROMPT = load_prompt("chat_assembler_small_talk")
_REPLY_PROMPT = load_prompt("chat_assembler_reply")
_METADATA_PROMPT = load_prompt("chat_assembler_metadata")


def _build_small_talk_brief(state: AgentState) -> str:
    """只暴露世界观纲要的最高层信息, 屏蔽节点级和对话级的具体人名,
    避免 LLM 在闲聊时把项目角色当成用户的名字。
    """
    world_brief = (state.get("world_brief") or "").strip()
    if not world_brief:
        return "(暂无项目背景)"
    return f"【项目背景速览】\n{world_brief[:120]}"


def _assemble_small_talk(state: AgentState) -> ChatAssemblerOutput:
    user_message = state.get("user_message", "")
    messages = [
        SystemMessage(_SMALL_TALK_PROMPT),
        HumanMessage(
            f"{_build_small_talk_brief(state)}\n\n【用户最新消息】\n{user_message}"
        ),
    ]
    return get_llm_provider().structured(messages, ChatAssemblerOutput)


def _build_reply_messages(
    state: AgentState, output: Any, primary: str
) -> list[BaseMessage]:
    user_message = state.get("user_message", "")
    warnings = state.get("boundary_warnings") or []
    warning_block = (
        "\n\n【边界检查跳过的项】\n" + "\n".join(f"- {item}" for item in warnings)
        if warnings
        else ""
    )

    return [
        SystemMessage(_REPLY_PROMPT),
        HumanMessage(
            f"{build_memory_block(state)}\n\n"
            f"【用户最新消息】\n{user_message}\n\n"
            f"【主导意图】\n{primary}\n\n"
            f"【agent 结构化输出】\n{output.model_dump_json()}"
            f"{warning_block}\n\n"
            "请直接输出最终面向用户的回复正文; 注意不要重复【最近对话】里"
            "你已经说过的话, 让回复有连续感。"
        ),
    ]


def _stream_reply(messages: list[BaseMessage]) -> str:
    """边 stream token 边推到 LangGraph custom stream, 返回拼好的整段。

    get_stream_writer 在非流式调用 (例如直接 graph.invoke) 下会抛
    RuntimeError, 用 try/except 包住让单测和老接口仍可复用本节点。
    """
    try:
        writer = get_stream_writer()
    except Exception:
        writer = None

    chunks: list[str] = []
    for token in get_llm_provider().chat_stream(messages):
        chunks.append(token)
        if writer is not None:
            try:
                writer({"type": "reply_token", "text": token})
            except Exception:
                writer = None
    return "".join(chunks)


def _build_meta_messages(output: Any, reply_text: str) -> list[BaseMessage]:
    return [
        SystemMessage(_METADATA_PROMPT),
        HumanMessage(
            f"【已生成的回复】\n{reply_text}\n\n"
            f"【原始 agent 输出】\n{output.model_dump_json()}"
        ),
    ]


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

    reply_text = _stream_reply(_build_reply_messages(state, output, primary))

    metadata = get_llm_provider().structured(
        _build_meta_messages(output, reply_text), ChatMetadataOutput
    )

    return {
        "assembler_output": ChatAssemblerOutput(
            reply_text=reply_text,
            cited_node_ids=metadata.cited_node_ids,
            staging_summary=metadata.staging_summary,
        )
    }