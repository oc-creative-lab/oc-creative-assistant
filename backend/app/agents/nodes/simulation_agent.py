"""Simulation agent node.

Receives "what if... what would happen" hypothetical intents. In a ReAct loop it
first uses search_nodes to pin down the relevant nodes and anchor the "current
state", then generates 2-3 distinct possible directions and outputs
SimulationOutput. This mode never produces proposed_changes; once the user picks
a branch, the next turn naturally switches to structure mode to carry the
follow-through.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import SimulationOutput
from app.agents.state import AgentState
from app.agents.structured_call import call_structured
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop
from app.agents.tools import make_project_tools
from app.agents.web_query import resolve_web_search_enabled
from app.llm.factory import get_llm_provider
from app.agents.prompts import load_prompt


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = load_prompt("simulation")


def simulation_agent_node(state: AgentState) -> dict[str, Any]:
    """Anchor the current state in a ReAct loop then simulate branches; degrade to empty branches when the LLM fails."""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(f"{build_memory_block(state, 'simulation')}\n\n[User hypothesis]\n{user_message}"),
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
            SimulationOutput,
            label="simulation_agent",
        )
        if output is None:
            output = SimulationOutput(
                reasoning="Structured output was empty.",
                branches=[],
            )
    except Exception as error:  # noqa: BLE001
        logger.warning("simulation_agent LLM call failed, degrading: %s", error)
        output = SimulationOutput(
            reasoning=f"Call failed ({type(error).__name__}); unable to simulate branches for now.",
            branches=[],
        )
    return {"simulation_output": output}