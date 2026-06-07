"""Structure agent node.

Receives "build structure" intents (adding nodes, creating relations in bulk,
organizing character groups, etc.). In a ReAct loop it checks for duplicates
first, then proposes, outputting StructureOutput.proposed_changes into staging
for user confirmation.

When a create_edge within the batch references a new node that hasn't been
persisted yet, it uses a pending_id; at persistence time canvas_apply translates
the pending_id into a real node_id, resolving the "nodes before edges"
dependency.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import StructureOutput
from app.agents.state import AgentState
from app.agents.tools import make_project_tools
from app.agents.web_query import resolve_web_search_enabled
from app.llm.factory import get_llm_provider
from app.agents.structured_call import call_structured
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("structure")

def structure_agent_node(state: AgentState) -> dict[str, Any]:
    """Check for duplicates and propose structure changes in a ReAct loop; degrade to empty proposed_changes when the LLM fails."""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state, 'structure')}\n\n"
            f"[User request]\n{user_message}"
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
            StructureOutput,
            label="structure_agent",
        )
        if output is None:
            output = StructureOutput(
                reasoning="Structured output was empty.",
                summary=(
                    "I couldn't put together a suggested structure this time. "
                    "You could rephrase your question or try again later."
                ),
            )
    except Exception as error:  # noqa: BLE001
        logger.warning("structure_agent LLM call failed, degrading: %s", error)
        output = StructureOutput(
            reasoning=f"Call failed ({type(error).__name__}).",
            summary="I couldn't put together a suggested structure this time. You could rephrase your question or try again later.",
        )
    return {"structure_output": output}