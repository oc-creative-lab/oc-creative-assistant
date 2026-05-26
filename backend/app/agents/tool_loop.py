"""Tool calling 执行循环。

封装 "调 LLM → 看 tool_calls → 执行 → 把结果喂回 LLM" 的循环, 让 agent 节点
只关心起点 prompt 与终点结构化输出。MAX_TOOL_LOOPS 是硬上限: 实际场景里
2-3 轮 ReAct 已经收敛, 留余量同时拦截 LLM 死循环。

``compact_history_for_structured`` 把循环结束的 history 压扁成纯 SystemMessage
+ HumanMessage 序列, 防止旧 tool_calls 被后续 ``with_structured_output`` 的
function_calling parser 当成"未知 tool"抛 KeyError。
"""

from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from app.llm.provider import LlmProvider


MAX_TOOL_LOOPS = 1
MAX_CALLS_PER_BATCH = 3
MAX_TOTAL_TOOL_CALLS = 3
_TOOL_RESULT_TRUNCATE = 400


def run_tool_loop(
    provider: LlmProvider,
    initial_messages: list[BaseMessage],
    tools: list[BaseTool],
) -> list[BaseMessage]:
    """跑完 tool calling 循环, 返回包含全部 tool_call / tool_result 的消息历史。

    工具调用预算双重上限: 单轮 batch ≤ MAX_CALLS_PER_BATCH 防 LLM 一次性
    平行调一堆相似 query; 跨轮总数 ≤ MAX_TOTAL_TOOL_CALLS 防 LLM 在多轮里
    把同样的 query 反复打。

    协议关键: AIMessage.tool_calls 里"每一条" call 都必须配一条 ToolMessage,
    缺哪怕一条都会让下一轮 chat_with_tools 撞 OpenAI 协议 400
    ("insufficient tool messages following tool_calls message"); 因此遍历时
    总把 tool_calls 全跑完, 超出预算的不真调工具, 用占位 ToolMessage 通知
    LLM "已被跳过, 请直接收口"。
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
                    "[已跳过: 本轮工具调用超出预算 "
                    f"(单轮最多 {MAX_CALLS_PER_BATCH} 次, 总预算 "
                    f"{MAX_TOTAL_TOOL_CALLS} 次)。请直接基于已有证据收口, "
                    "不要再调用任何工具。]"
                )
            else:
                tool_fn = tool_by_name.get(call["name"])
                if tool_fn is None:
                    content = f"未知工具: {call['name']}"
                else:
                    try:
                        content = tool_fn.invoke(call["args"])
                    except Exception as exc:  # noqa: BLE001
                        content = f"工具执行失败: {exc}"
                total_calls += 1
            history.append(ToolMessage(content=str(content), tool_call_id=call["id"]))

        if total_calls >= MAX_TOTAL_TOOL_CALLS:
            return history

    return history


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def compact_history_for_structured(history: list[BaseMessage]) -> list[BaseMessage]:
    """把 tool calling 痕迹折叠成一段证据摘要, 供后续 ``provider.structured()`` 使用。

    保留原始 SystemMessage / HumanMessage, 把 AIMessage.tool_calls + ToolMessage
    的来回转成一个新增的 HumanMessage 文本块; 这样 with_structured_output 在解析
    history 时不会撞见非目标 schema 的 tool_call 名字。
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
                trace_lines.append(f"- 中间思考: {_truncate(content, _TOOL_RESULT_TRUNCATE)}")
        elif isinstance(message, ToolMessage):
            label = pending_call_label.pop(message.tool_call_id, "未知调用")
            result = message.content if isinstance(message.content, str) else str(message.content)
            trace_lines.append(f"- 调用 {label} → {_truncate(result, _TOOL_RESULT_TRUNCATE)}")

    if not trace_lines:
        return [*system_messages, *human_messages]

    digest = "\n".join(trace_lines)
    return [
        *system_messages,
        *human_messages,
        HumanMessage(
            f"【刚才通过工具收集到的证据】\n{digest}\n\n"
            "请基于以上证据直接产出结构化输出, 不要再调用任何工具。"
        ),
    ]