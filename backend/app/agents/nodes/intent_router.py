"""Intent classification node.

Classifies the user's latest-turn message into an agent type and writes it to
state.intent, so the downstream graph routes by intent to the matching agent.
An empty message falls back directly to small_talk without calling the LLM,
saving cost.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import format_current_nodes
from app.agents.structured_call import call_structured
from app.agents.schemas import IntentClassification
from app.agents.state import AgentState
from app.llm.factory import get_llm_provider
from app.agents.prompts import load_prompt


_SYSTEM_PROMPT = load_prompt("intent_router")

# Substantive project/story questions must not be swallowed by a leading greeting.
_PROJECT_QUERY_FRAGMENTS = (
    "看得到",
    "能看见",
    "看到",
    "可见",
    "故事",
    "情节",
    "剧情",
    "剧本",
    "项目里",
    "项目内",
    "画布",
    "节点",
    "写了什么",
    "有哪些",
    "can you see",
    "do you see",
    "my story",
    "my plot",
    "what plot",
    "what story",
    "what do i have",
    "what have i",
    "plot nodes",
    "story nodes",
)


def _looks_like_project_query(message: str) -> bool:
    text = message.strip().lower()
    raw = message.strip()
    return any(frag in raw or frag in text for frag in _PROJECT_QUERY_FRAGMENTS)


def _coerce_research_if_project_query(
    intent: IntentClassification,
    user_message: str,
) -> IntentClassification:
    if intent.primary != "small_talk" or not _looks_like_project_query(user_message):
        return intent
    return IntentClassification(
        primary="research",
        confidence=max(intent.confidence, 0.85),
        reasoning="Project/story visibility or content question overrides greeting small_talk.",
    )


def intent_router_node(state: AgentState) -> dict[str, Any]:
    """Decide IntentClassification from the user message + recent conversation; empty message goes straight to small_talk."""
    user_message = state.get("user_message", "").strip()
    if not user_message:
        return {
            "intent": IntentClassification(primary="small_talk", reasoning="User message is empty."),
        }

    recent = state.get("recent_messages") or []
    history = "\n".join(f"{m['role']}: {m['content']}" for m in recent[-4:])
    history_block = f"[Recent conversation]\n{history}\n\n" if history else ""
    quoted_block = format_current_nodes(state.get("current_nodes") or [])
    quoted_section = (
        f"[Quoted nodes from canvas]\n{quoted_block}\n\n"
        if state.get("current_nodes")
        else ""
    )

    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{history_block}{quoted_section}[Latest message]\n{user_message}"
        ),
    ]

    intent = call_structured(
        get_llm_provider(),
        messages,
        IntentClassification,
        label="intent_router",
    )

    if intent is None:
        # When the user quoted canvas nodes, default to research instead of small_talk.
        if state.get("current_nodes"):
            intent = IntentClassification(
                primary="research",
                confidence=0.5,
                reasoning="Intent LLM returned no result; user quoted canvas nodes, falling back to research.",
            )
        elif _looks_like_project_query(user_message):
            intent = IntentClassification(
                primary="research",
                confidence=0.5,
                reasoning="Intent LLM returned no result; project/story query, falling back to research.",
            )
        else:
            intent = IntentClassification(
                primary="small_talk",
                confidence=0.5,
                reasoning="Intent LLM returned no result; falling back to small_talk.",
            )
    else:
        intent = _coerce_research_if_project_query(intent, user_message)

    return {"intent": intent}