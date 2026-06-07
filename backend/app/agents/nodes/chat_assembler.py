"""Chat assembler node.

Reads the structured output of the agent matching the current intent and uses
the LLM to translate it into a natural-language reply; small_talk goes through a
separate lightweight prompt so that chit-chat is not contaminated by character
names in the project context being mistaken for a "disguised username".

To support token-level streaming, the main path is split into two steps:
  Step 1 [streaming]: chat_stream generates the plain-text reply_text, with each
                      token pushed onto the LangGraph custom stream via
                      get_stream_writer
  Step 2 [non-streaming]: a structured call extracts cited_node_ids and
                          staging_summary from the already-generated reply_text

The small_talk text is very short and not worth an extra round-trip, so it
keeps a single structured call.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from app.agents.memory import build_memory_block, format_current_nodes
from app.agents.prompts import load_prompt
from app.agents.schemas import ChatAssemblerOutput, ChatMetadataOutput
from app.agents.state import AgentState
from app.agents.structured_call import call_structured
from app.core.settings import get_llm_settings
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


def _hint_block(state: AgentState) -> str:
    """Assemble the follow-up direction planned by question_planner into a hint block (empty when the gate is off).

    Provided only as a "suggested direction" for the assembler to weave in
    naturally, not to be copied verbatim, to avoid the reply turning into
    mechanical questioning.
    """
    hint = (state.get("next_question_hint") or "").strip()
    if not hint:
        return ""
    return (
        f"\n\n[Suggested next follow-up direction (weave into the reply naturally, do not copy verbatim)]\n{hint}"
    )


def _build_small_talk_brief(state: AgentState) -> str:
    """Expose only the top-level info of the worldbuilding outline, hiding node-level and conversation-level specific names, to keep the LLM from mistaking a project character for the user's name during chit-chat."""
    world_brief = (state.get("world_brief") or "").strip()
    if not world_brief:
        return "(no project background yet)"
    return f"[Project background at a glance]\n{world_brief[:120]}"


def _assemble_small_talk(state: AgentState) -> ChatAssemblerOutput:
    user_message = state.get("user_message", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    llm_model = get_llm_settings().model
    runtime_block = (
        f"[Runtime info]\n"
        f"Current time: {now_str}\n"
        f"Agent model: {llm_model}\n"
    )
    messages = [
        SystemMessage(_SMALL_TALK_PROMPT),
        HumanMessage(
            f"{runtime_block}\n{_build_small_talk_brief(state)}\n\n"
            f"{format_current_nodes(state.get('current_nodes') or [])}\n\n"
            f"[User's latest message]\n{user_message}"
            f"{_hint_block(state)}"
        ),
    ]
    output = call_structured(
        get_llm_provider(),
        messages,
        ChatAssemblerOutput,
        label="chat_assembler.small_talk",
    )
    if output is None:
        fallback = (
            "你好！我可以帮你查项目里的设定与情节、头脑风暴，或在画布上整理故事结构。"
            if any("\u4e00" <= c <= "\u9fff" for c in user_message)
            else (
                "Hi! I can help you look up project notes, brainstorm ideas, "
                "or organize structure on the canvas."
            )
        )
        return ChatAssemblerOutput(
            reply_text=fallback,
        )
    return output


def _build_reply_messages(
    state: AgentState, output: Any, primary: str
) -> list[BaseMessage]:
    user_message = state.get("user_message", "")
    warnings = state.get("boundary_warnings") or []
    warning_block = (
        "\n\n[Items skipped by boundary check]\n" + "\n".join(f"- {item}" for item in warnings)
        if warnings
        else ""
    )

    return [
        SystemMessage(_REPLY_PROMPT),
        HumanMessage(
            f"{build_memory_block(state, primary)}\n\n"
            f"[User's latest message]\n{user_message}\n\n"
            f"[Primary intent]\n{primary}\n\n"
            f"[Agent structured output]\n{output.model_dump_json()}"
            f"{warning_block}"
            f"{_hint_block(state)}\n\n"
            "Output the final user-facing reply body directly; be careful not to "
            "repeat what you already said in [Recent conversation], so the reply "
            "feels continuous."
        ),
    ]


def _stream_reply(messages: list[BaseMessage]) -> str:
    """Stream tokens while pushing them onto the LangGraph custom stream, returning the assembled whole.

    get_stream_writer raises RuntimeError under non-streaming calls (e.g. a
    direct graph.invoke), so it is wrapped in try/except to let unit tests and
    the old interface still reuse this node.
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
            f"[Generated reply]\n{reply_text}\n\n"
            f"[Original agent output]\n{output.model_dump_json()}"
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
                reply_text="I didn't get a suitable result this turn. How about telling me a bit more about the direction you want?"
            ),
        }

    reply_text = _stream_reply(_build_reply_messages(state, output, primary))

    metadata = call_structured(
        get_llm_provider(),
        _build_meta_messages(output, reply_text),
        ChatMetadataOutput,
        label="chat_assembler.metadata",
    )
    if metadata is None:
        metadata = ChatMetadataOutput(cited_node_ids=[], staging_summary="")

    web_sources = []
    if primary == "research":
        research = state.get("research_output")
        if research is not None:
            web_sources = list(research.web_sources)

    return {
        "assembler_output": ChatAssemblerOutput(
            reply_text=reply_text,
            cited_node_ids=metadata.cited_node_ids,
            staging_summary=metadata.staging_summary,
            web_sources=web_sources,
        )
    }