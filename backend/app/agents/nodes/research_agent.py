"""Research agent node.

Receives "research-type" intents (looking up what has been written in the
project, comparing, summarizing) and calls search_nodes / get_node /
list_neighbors as needed within a ReAct loop to gather evidence, finally
producing ResearchOutput.

Tool-call results are the LLM's only basis for its statements; the "must call a
tool first" constraint in the prompt keeps the agent from bypassing the
knowledge base and fabricating things out of thin air, while handing the
judgment of "when to look something up again" back to the LLM.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import ResearchOutput
from app.agents.state import AgentState
from app.agents.tools import make_project_tools
from app.agents.web_query import (
    extract_web_sources_from_tool_history,
    merge_web_sources,
    prefetch_web_search,
    resolve_web_search_enabled,
)
from app.llm.factory import get_llm_provider
from app.agents.structured_call import call_structured
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.prompts import load_prompt
from datetime import datetime


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("research")


def research_agent_node(state: AgentState) -> dict[str, Any]:
    """Gather evidence in a ReAct loop then produce ResearchOutput; degrade to an empty summary when the LLM fails."""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    web_prefetch_block = ""
    web_fallback_answer = ""
    prefetch_sources = []
    web_search_mode = state.get("web_search_mode", "auto")
    web_enabled = resolve_web_search_enabled(user_message, web_search_mode)
    if web_enabled:
        prefetched = prefetch_web_search(user_message)
        if prefetched is not None:
            web_prefetch_block = prefetched.block
            web_fallback_answer = prefetched.fallback_answer
            prefetch_sources = prefetched.sources
            logger.info(
                "research_agent prefetched web_search (mode=%s)",
                web_search_mode,
            )

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"[Runtime info]\nCurrent time: {now_str}\n"
            f"Agent model: determined by the backend OC_LLM_MODEL config (state it directly if the user asks)\n\n"
            f"{build_memory_block(state, 'research')}\n\n"
            f"[User question]\n{user_message}"
            + (
                f"\n\n[Pre-fetched web_search result — use for external facts; cite the answer field]\n"
                f"{web_prefetch_block}"
                if web_prefetch_block
                else ""
            )
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id, include_web_search=web_enabled)

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        tool_sources = extract_web_sources_from_tool_history(history)
        web_sources = merge_web_sources(prefetch_sources, tool_sources)
        output = call_structured(
            provider,
            compact_history_for_structured(history),
            ResearchOutput,
            label="research_agent",
        )
        if output is None:
            if web_fallback_answer:
                output = ResearchOutput(
                    reasoning="Structured output was empty; used pre-fetched web_search.",
                    summary=web_fallback_answer,
                )
            else:
                output = ResearchOutput(
                    reasoning="Structured output was empty.",
                    summary=(
                        "这次没能整理出查询结果。你可以在输入框引用情节节点后再问，或直接说「我有哪些情节节点」。"
                        if any("\u4e00" <= c <= "\u9fff" for c in user_message)
                        else (
                            "I couldn't assemble a research summary this turn. "
                            "Try quoting the plot node in the composer, or ask again."
                        )
                    ),
                )
        if web_sources:
            output = output.model_copy(update={"web_sources": web_sources})
    except Exception as error:  # noqa: BLE001
        logger.warning("research_agent LLM call failed, degrading: %s", error)
        if web_fallback_answer:
            output = ResearchOutput(
                reasoning=f"Call failed ({type(error).__name__}); used pre-fetched web_search.",
                summary=web_fallback_answer,
                web_sources=merge_web_sources(prefetch_sources),
            )
        else:
            output = ResearchOutput(
                reasoning=f"Call failed ({type(error).__name__}).",
                summary="I couldn't find anything relevant this time. You could rephrase your question or try again later.",
            )
    return {"research_output": output}