"""Shared helpers for LLM structured output calls.

OpenAI-compatible providers occasionally return ``None`` from
``with_structured_output`` without raising, which would otherwise leave agent
state fields empty and trigger generic chat_assembler fallbacks.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.llm.provider import LlmProvider


logger = logging.getLogger(__name__)

TSchema = TypeVar("TSchema", bound=BaseModel)


def call_structured(
    provider: LlmProvider,
    messages: list[BaseMessage],
    schema: type[TSchema],
    *,
    label: str,
) -> TSchema | None:
    """Invoke structured output; log and return None on failure or empty result."""
    try:
        result = provider.structured(messages, schema)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s structured call failed: %s", label, exc)
        return None
    if result is None:
        logger.warning("%s structured call returned None", label)
    return result
