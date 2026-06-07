"""Tool calling execution loop.

Encapsulates the ReAct loop of "call LLM → look at tool_calls → execute → feed
results back to LLM", so agent nodes only care about the starting prompt and the
final structured output. MAX_TOOL_LOOPS=3 lets the LLM truly make multi-turn
decisions: round 1 calls the initial tools, rounds 2-3 see the results and
decide whether to keep querying or wrap up; scenarios needing more than 3 rounds
are rare in practice, and this also intercepts LLM infinite loops.

Dual upper bounds on the tool-call budget: per-round batch ≤ MAX_CALLS_PER_BATCH
prevents the LLM from firing a bunch of similar queries in parallel at once;
cross-round total ≤ MAX_TOTAL_TOOL_CALLS prevents the LLM from repeatedly firing
the same query across rounds.

``compact_history_for_structured`` flattens the post-loop history into a pure
SystemMessage + HumanMessage sequence, preventing the later
``with_structured_output`` function_calling parser from treating old tool_calls
as an "unknown tool" and throwing KeyError. Tool results are truncated by token
(not by character), so tools like list_nodes that return dozens of JSON entries
at once do not have key content cut off; the CoT of intermediate thinking is
still truncated by character, as it is less sensitive to length.
"""

from __future__ import annotations

import tiktoken
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from app.llm.provider import LlmProvider


MAX_TOOL_LOOPS = 3
MAX_CALLS_PER_BATCH = 3
MAX_TOTAL_TOOL_CALLS = 5
_TOOL_RESULT_TOKEN_CAP = 600
_MIDDLE_THOUGHT_CHAR_CAP = 400

# Reuse the same encoding as context_compress; works offline and is consistent with mainstream OpenAI-compatible models
_encoder = tiktoken.get_encoding("cl100k_base")


def run_tool_loop(
    provider: LlmProvider,
    initial_messages: list[BaseMessage],
    tools: list[BaseTool],
) -> list[BaseMessage]:
    """Run the tool calling loop to completion, returning the message history with all tool_calls / tool_results.

    Protocol key point: "every" call in AIMessage.tool_calls must be paired with
    a ToolMessage; missing even one will make the next chat_with_tools hit
    OpenAI protocol 400 ("insufficient tool messages following tool_calls
    message"); therefore the iteration always runs through all tool_calls, those
    over budget are not actually invoked but use a placeholder ToolMessage to
    notify the LLM "skipped, please wrap up directly".
    """
    tool_by_name = {tool.name: tool for tool in tools}
    history: list[BaseMessage] = list(initial_messages)
    total_calls = 0

    for _ in range(MAX_TOOL_LOOPS):
        response = provider.chat_with_tools(history, tools)
        history.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return history

        for idx, call in enumerate(tool_calls):
            within_batch = idx < MAX_CALLS_PER_BATCH
            within_budget = total_calls < MAX_TOTAL_TOOL_CALLS
            if not within_batch or not within_budget:
                content = (
                    "[Skipped: this round's tool calls exceeded the budget "
                    f"(at most {MAX_CALLS_PER_BATCH} per round, total budget "
                    f"{MAX_TOTAL_TOOL_CALLS}). Please wrap up directly based on "
                    "the existing evidence, and do not call any more tools.]"
                )
            else:
                tool_fn = tool_by_name.get(call["name"])
                if tool_fn is None:
                    content = f"Unknown tool: {call['name']}"
                else:
                    try:
                        content = tool_fn.invoke(call["args"])
                    except Exception as exc:  # noqa: BLE001
                        content = f"Tool execution failed: {exc}"
                total_calls += 1
            history.append(ToolMessage(content=str(content), tool_call_id=call["id"]))

        if total_calls >= MAX_TOTAL_TOOL_CALLS:
            return history

    return history


def _truncate_chars(text: str, limit: int) -> str:
    """Truncate by character count, suitable for length-insensitive CoT intermediate thinking."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _truncate_tokens(text: str, cap: int) -> str:
    """Truncate by token count, preserving more complete JSON / long-list tool return content."""
    stripped = text.strip()
    tokens = _encoder.encode(stripped)
    if len(tokens) <= cap:
        return stripped
    return _encoder.decode(tokens[:cap]) + "…"


def compact_history_for_structured(history: list[BaseMessage]) -> list[BaseMessage]:
    """Fold the tool calling traces into an evidence digest, for later use by ``provider.structured()``.

    Keep the original SystemMessage / HumanMessage, and turn the back-and-forth
    of AIMessage.tool_calls + ToolMessage into one newly added HumanMessage text
    block; this way with_structured_output does not run into off-target schema
    tool_call names while parsing the history.
    """
    system_messages: list[BaseMessage] = []
    human_messages: list[BaseMessage] = []
    trace_lines: list[str] = []
    pending_call_label: dict[str, str] = {}

    for message in history:
        if isinstance(message, SystemMessage):
            system_messages.append(message)
        elif isinstance(message, HumanMessage):
            human_messages.append(message)
        elif isinstance(message, AIMessage):
            calls = getattr(message, "tool_calls", None) or []
            for call in calls:
                pending_call_label[call["id"]] = (
                    f"{call['name']}({call.get('args', {})})"
                )
            content = (message.content or "").strip() if isinstance(message.content, str) else ""
            if content and not calls:
                trace_lines.append(
                    f"- Intermediate thinking: {_truncate_chars(content, _MIDDLE_THOUGHT_CHAR_CAP)}"
                )
        elif isinstance(message, ToolMessage):
            label = pending_call_label.pop(message.tool_call_id, "unknown call")
            result = message.content if isinstance(message.content, str) else str(message.content)
            trace_lines.append(
                f"- Called {label} → {_truncate_tokens(result, _TOOL_RESULT_TOKEN_CAP)}"
            )

    if not trace_lines:
        return [*system_messages, *human_messages]

    digest = "\n".join(trace_lines)
    return [
        *system_messages,
        *human_messages,
        HumanMessage(
            f"【Evidence just collected via tools】\n{digest}\n\n"
            "Please produce the structured output directly based on the above evidence, and do not call any more tools."
        ),
    ]