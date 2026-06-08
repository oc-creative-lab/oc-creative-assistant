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

# Heuristic overrides when the LLM picks small_talk or returns nothing for clear creative tasks.
_STRUCTURE_FRAGMENTS = (
    "create a character",
    "create character",
    "add a character",
    "new character",
    "create a plot",
    "create plot",
    "add a node",
    "add to the canvas",
    "build a relation",
    "build relation",
    " named ",
    "创建角色",
    "创建人物",
    "新建角色",
    "添加角色",
    "创建情节",
    "建立关系",
    "加到画布",
)

_INSPIRATION_FRAGMENTS = (
    "write a story",
    "i want to write",
    "help me write",
    "brainstorm",
    "what else can",
    "what else could",
    "帮我想",
    "想写",
    "写一个故事",
    "写故事",
)

_SIMULATION_FRAGMENTS = (
    "what if",
    "what would happen",
    "would happen if",
    "如果",
    "会怎样",
    "会怎么样",
)


def _looks_like_project_query(message: str) -> bool:
    text = message.strip().lower()
    raw = message.strip()
    return any(frag in raw or frag in text for frag in _PROJECT_QUERY_FRAGMENTS)


def _guess_intent_from_message(message: str) -> IntentClassification | None:
    """Keyword fallback when structured intent classification is missing or too generic."""
    text = message.strip().lower()
    raw = message.strip()

    if any(frag in text or frag in raw for frag in _SIMULATION_FRAGMENTS):
        return IntentClassification(
            primary="simulation",
            confidence=0.8,
            reasoning="Hypothetical phrasing detected by heuristic.",
        )

    if any(frag in text or frag in raw for frag in _STRUCTURE_FRAGMENTS):
        return IntentClassification(
            primary="structure",
            confidence=0.85,
            reasoning="Entity or relation creation phrasing detected by heuristic.",
        )

    if any(frag in text or frag in raw for frag in _INSPIRATION_FRAGMENTS):
        return IntentClassification(
            primary="inspiration",
            confidence=0.8,
            reasoning="Open-ended story or brainstorm phrasing detected by heuristic.",
        )

    if _looks_like_project_query(message):
        return IntentClassification(
            primary="research",
            confidence=0.85,
            reasoning="Project/story visibility or content question detected by heuristic.",
        )

    return None


def _coerce_substantive_intent(
    intent: IntentClassification,
    user_message: str,
) -> IntentClassification:
    if intent.primary != "small_talk":
        return intent
    guessed = _guess_intent_from_message(user_message)
    if guessed is None:
        return intent
    return IntentClassification(
        primary=guessed.primary,
        confidence=max(intent.confidence, guessed.confidence),
        reasoning=guessed.reasoning,
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
        guessed = _guess_intent_from_message(user_message)
        if guessed is not None:
            intent = guessed
        elif state.get("current_nodes"):
            intent = IntentClassification(
                primary="research",
                confidence=0.5,
                reasoning="Intent LLM returned no result; user quoted canvas nodes, falling back to research.",
            )
        else:
            intent = IntentClassification(
                primary="small_talk",
                confidence=0.5,
                reasoning="Intent LLM returned no result; falling back to small_talk.",
            )
    else:
        intent = _coerce_substantive_intent(intent, user_message)

    return {"intent": intent}