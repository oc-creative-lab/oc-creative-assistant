"""Inspiration agent node.

Calls LlmProvider to output InspirationOutput, forcing a reasoning field that
explicitly emits CoT reasoning. The prompt is injected by build_memory_block
with multi-layer memory + RAG context, letting the LLM brainstorm within the
existing worldbuilding and recent conversation without straying from the user's
context.

Tools are "optional": the LLM decides for itself "should I first verify with
search_nodes whether the project has a similar node for this suggestion".
research_agent's policy of forcing mandatory tool use does not suit a
brainstorming scenario; here the ReAct early-exit mechanism lets the LLM wrap up
directly when there is no problem, and not calling any tool in a turn is also
valid.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import InspirationOutput
from app.agents.state import AgentState
from app.agents.structured_call import call_structured
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.tools import make_project_tools
from app.agents.web_query import resolve_web_search_enabled
from app.llm.factory import get_llm_provider
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("inspiration")


def inspiration_agent_node(state: AgentState) -> dict[str, Any]:
    """Optionally verify via a ReAct loop and produce InspirationOutput; degrade gracefully when the LLM fails."""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()

    if not user_message:
        empty = InspirationOutput(reasoning="User message is empty; skipping reasoning.", suggestions=[])
        return {"inspiration_output": empty}

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state, 'inspiration')}\n\n"
            f"[User question]\n{user_message}"
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(
        project_id,
        include_web_search=resolve_web_search_enabled(
            user_message,
            state.get("web_search_mode", "auto"),
        ),
    )

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        output = call_structured(
            provider,
            compact_history_for_structured(history),
            InspirationOutput,
            label="inspiration_agent",
        )
        if output is None:
            output = InspirationOutput(
                reasoning="Structured output was empty.",
                suggestions=[],
            )
    except Exception as error:  # noqa: BLE001
        logger.warning("inspiration_agent LLM call failed, degrading: %s", error)
        output = InspirationOutput(
            reasoning=f"Call failed ({type(error).__name__}); unable to brainstorm ideas for now.",
            suggestions=[],
        )
    return {"inspiration_output": output}