"""Strategy Pattern entry point for LLM calls.

Encapsulates the LangChain / OpenAI SDK details inside the Provider, so agent
nodes only see two unified methods, ``chat`` (string) and ``structured``
(Pydantic), shielding them from low-level protocol differences.

OpenAI-compatible services like DeepSeek / Tongyi generally don't support
``response_format=json_schema``, so the real provider explicitly pins
``method="function_calling"`` to use the tool-calls protocol for the widest
compatibility. The Mock provider is fully offline and returns registered samples
keyed by schema name, which is convenient for offline development and CI.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any, Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.settings import LlmSettings


logger = logging.getLogger(__name__)

TSchema = TypeVar("TSchema", bound=BaseModel)

_STRUCTURED_METHODS = ("function_calling", "json_mode")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull a JSON object from a plain-text model reply."""
    cleaned = _strip_json_fence(text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match is None:
        raise ValueError("No JSON object found in model response")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Model JSON root must be an object")
    return data


def _raw_message_snippet(raw: Any, *, limit: int = 240) -> str:
    if raw is None:
        return ""
    content = getattr(raw, "content", raw)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(block, str):
                parts.append(block)
        content = "\n".join(parts)
    text = content if isinstance(content, str) else str(content)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


class LlmProvider(Protocol):
    """The unified interface contract for LLM calls.

    Every agent node accesses the model through an implementation of this
    protocol; the Strategy Pattern lets the mock and real providers swap
    seamlessly via .env without changing business code.
    """

    def chat(self, messages: list[BaseMessage]) -> str: ...

    def chat_stream(self, messages: list[BaseMessage]) -> Iterator[str]: ...

    def structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema: ...

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[BaseTool],
    ) -> AIMessage: ...


class OpenAICompatibleProvider:
    """Calls services like DeepSeek / Tongyi / official OpenAI via the OpenAI-compatible protocol.

    Under the hood it uses LangChain's ``ChatOpenAI``, so when wiring up
    ToolNode / Checkpointer later we can reuse the LangChain ecosystem directly
    instead of hand-writing a tool-calling loop.
    """

    def __init__(self, settings: LlmSettings) -> None:
        if not settings.is_configured:
            raise ValueError("OC_LLM_* config is missing, cannot initialize the OpenAI-compatible provider")

        self._client = ChatOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            temperature=0.3,
        )

    def chat(self, messages: list[BaseMessage]) -> str:
        response = self._client.invoke(messages)
        content = response.content if isinstance(response, AIMessage) else response
        return content if isinstance(content, str) else str(content)

    def chat_stream(self, messages: list[BaseMessage]) -> Iterator[str]:
        """Yield text deltas chunk by chunk; natively supported by LangChain ChatOpenAI's .stream().

        Empty chunks (e.g. the LLM is still thinking and hasn't produced a token)
        are skipped, so the upper layer only sees tokens with real content and we
        avoid feeding None / "" into the string accumulation.
        """
        for chunk in self._client.stream(messages):
            content = chunk.content if isinstance(chunk, AIMessage) else chunk
            if isinstance(content, str) and content:
                yield content

    def structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema:
        """Structured output with fallbacks for OpenAI-compatible providers that return empty parses."""
        errors: list[str] = []

        for method in _STRUCTURED_METHODS:
            try:
                parsed, err = self._try_structured(messages, schema, method)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{method}: {exc}")
                logger.warning(
                    "%s structured via %s raised: %s",
                    schema.__name__,
                    method,
                    exc,
                )
                continue

            if parsed is not None:
                return parsed
            if err:
                errors.append(err)

        try:
            return self._structured_via_plain_json(messages, schema)
        except Exception as exc:  # noqa: BLE001
            detail = "; ".join(errors) if errors else str(exc)
            raise ValueError(
                f"structured output failed for {schema.__name__}: {detail}"
            ) from exc

    def _try_structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
        method: str,
    ) -> tuple[TSchema | None, str | None]:
        runnable = self._client.with_structured_output(
            schema,
            method=method,
            include_raw=True,
        )
        result = runnable.invoke(messages)

        if not isinstance(result, dict):
            if result is None:
                return None, f"{method}: parsed is None"
            return result, None

        parsed = result.get("parsed")
        if parsed is not None:
            return parsed, None

        parsing_error = result.get("parsing_error")
        raw_snippet = _raw_message_snippet(result.get("raw"))
        err_parts = [f"{method}: parsed is None"]
        if parsing_error is not None:
            err_parts.append(f"parsing_error={parsing_error}")
        if raw_snippet:
            err_parts.append(f"raw={raw_snippet}")
        err = "; ".join(err_parts)
        logger.warning("%s structured call returned None (%s)", schema.__name__, err)
        return None, err

    def _structured_via_plain_json(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema:
        """Last resort: plain chat + manual JSON parse (works when tool-calls are ignored)."""
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        prompt_messages = [
            *messages,
            HumanMessage(
                "Respond with ONLY one JSON object matching this schema "
                "(no markdown fences, no commentary):\n"
                f"{schema_json}"
            ),
        ]
        raw = self.chat(prompt_messages)
        data = _extract_json_object(raw)
        return schema.model_validate(data)

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[BaseTool],
    ) -> AIMessage:
        """Bind tools and call the LLM once, returning the raw AIMessage so tool_loop can parse tool_calls."""
        bound = self._client.bind_tools(tools)
        response = bound.invoke(messages)
        if isinstance(response, AIMessage):
            return response
        return AIMessage(content=str(getattr(response, "content", response)))

_MOCK_SAMPLES: dict[str, dict[str, Any]] = {
    "IntentClassification": {
        "primary": "inspiration",
        "confidence": 0.85,
        "reasoning": "The user wants to explore creative directions, matching the inspiration intent.",
    },
    "InspirationOutput": {
        "reasoning": "Add background conflict around the existing dwarven-blacksmith setting to make the character more three-dimensional.",
        "suggestions": [
            "Design a past for the blacksmith in which she was exiled by the clan chief",
            "Introduce a young apprentice who challenges her craft",
            "Have her hold an artifact that reveals an ancestral secret",
        ],
        "referenced_node_ids": [],
        "proposed_changes": [
            {
                "change_type": "create_node",
                "target_id": None,
                "pending_id": "pending-1",
                "payload": {
                    "title": "Duskstone",
                    "content": "A young dwarven apprentice, studying under the protagonist, secretly suspicious of her master's past",
                    "node_type": "character",
                },
                "reason": "Introduce a conflict line for the protagonist",
            }
        ],
    },
    "ResearchOutput": {
        "reasoning": "Summarize related characters and worldbuilding fragments by theme within the existing graph.",
        "summary": "[mock] This character has historical entanglements with the existing clan; the core conflict stems from identity.",
        "referenced_node_ids": [],
        "proposed_changes": [],
    },
    "StructureOutput": {
        "reasoning": "The character the user selected isn't yet connected to the plot; add an interaction line.",
        "summary": "Recommend adding an opposing interaction line between the character and the clan chief.",
        "proposed_changes": [],
    },
    "SimulationOutput": {
        "reasoning": "Lay out multiple directions for the user's hypothesis and assess the impact on existing nodes.",
        "branches": [
            {
                "scenario": "She accepts the mission but leaves herself a way out",
                "likelihood": "high",
                "downstream_impacts": ["The clan reconciles for now", "The apprentice's identity becomes a mystery"],
                "affected_node_ids": [],
            }
        ],
    },
    "ChatAssemblerOutput": {
        "reply_text": "[mock] For the blacksmith's story, here are a few directions: an exiled past, a young apprentice, an ancestral artifact.",
        "cited_node_ids": [],
        "staging_summary": "I'm ready to add 1 item for you, pending your confirmation.",
    },
    "ChatMetadataOutput": {
        "cited_node_ids": [],
        "staging_summary": "I'm ready to add 1 item for you, pending your confirmation.",
    },
        "SummaryOutput": {
        "summary": "[mock] The user and the agent had several rounds of discussion about the protagonist's past and the clan conflict, reaching basic consensus on the main direction.",
        "key_facts": [
            "The protagonist is a dwarven blacksmith with a questionable origin",
            "The user leans toward having the conflict come from within the clan",
        ],
    },
    "StructuredExtractionOutput": {
        "reasoning": "[mock] Extracted one character and one worldbuilding setting from the conversation.",
        "entities": [
            {"type": "character", "name": "Duskstone", "attributes": {"role": "dwarven blacksmith"}},
            {"type": "world", "name": "Ironforge Clan", "attributes": {}},
        ],
        "relations": [
            {"source_name": "Duskstone", "target_name": "Ironforge Clan", "label": "belongs to"},
        ],
        "deferred_fields": [{"entity": "Duskstone", "field": "appearance"}],
    },
    "QuestionPlannerOutput": {
        "reasoning": "[mock] The character has an identity but lacks motivation; ask about motivation.",
        "next_question": "Why did Duskstone leave the Ironforge Clan?",
        "target_field": "motivation",
    },
    "SeedOutput": {
        "worldview_summary": "[mock] A fantasy world centered on a clan of dwarven blacksmiths.",
        "main_characters": ["Duskstone"],
        "plot_outline": "[mock] The protagonist comes into conflict with the clan over the mystery of her origin.",
        "style_notes": "A weighty, introspective low-fantasy tone.",
    },
    "WorkspaceInspirationOutput": {
        "reasoning": "[mock] The user is sharing an idea; give positive feedback.",
        "type": "feedback",
        "content": "[mock] This direction is really interesting — especially with the conflict coming from within, the tension will be strong.",
    },
}


class MockProvider:
    """An offline, deterministic stub that makes no network requests.

    Returns the sample registered in ``_MOCK_SAMPLES`` based on the target schema
    name, so frontend integration and unit tests can run without an LLM. It raises
    on an unregistered schema, since surfacing the omission is safer than silently
    returning None.
    """

    def chat(self, messages: list[BaseMessage]) -> str:
        last_user = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
            "",
        )
        text = last_user if isinstance(last_user, str) else str(last_user)
        return f"[mock] received: {text[:60]}"

    def chat_stream(self, messages: list[BaseMessage]) -> Iterator[str]:
        """Split by character to simulate a token stream, so mock mode can also verify the frontend's progressive rendering."""
        for ch in self.chat(messages):
            yield ch

    def structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema:
        sample = _MOCK_SAMPLES.get(schema.__name__)
        if sample is None:
            raise ValueError(
                f"MockProvider is missing a {schema.__name__} sample; please register it in _MOCK_SAMPLES"
            )
        return schema.model_validate(sample)

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[BaseTool],
    ) -> AIMessage:
        """Mock mode skips tool calls and returns an empty reply so tool_loop exits immediately."""
        return AIMessage(content="")
