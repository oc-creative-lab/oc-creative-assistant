"""结构化 agent 节点。

接收"建结构"意图(新增节点、批量建关系、整理人物族群等), 在 ReAct 循环里
先查重再提议, 输出 StructureOutput.proposed_changes 进 staging 等用户确认。

batch 内 create_edge 引用尚未落库的新节点时使用 pending_id, 持久化时由
canvas_apply 把 pending_id 翻译成真实 node_id, 解决"先节点后边"的依赖。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.memory import build_memory_block
from app.agents.schemas import StructureOutput
from app.agents.state import AgentState
from app.agents.tools import make_project_tools
from app.llm.factory import get_llm_provider
from app.agents.tool_loop import compact_history_for_structured, run_tool_loop


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是创作助手的结构化模式, 任务是把用户提供的散点信息落到画布的节点 / 关系上。

工作流程:
0. 先看【最近对话】: 如果用户消息含"这个/那个/这两个/这些/它/他们"等指代词,
   或简短确认 ("好" / "是的" / "帮我建"), 必须从最近 AI 消息里推断你建议过的具体
   名字/类型, 不要再问用户"具体是哪一个"。
1. 查重策略二选一:
   - 已知节点名 / 大致语义: 用 search_nodes 按语义查 top-K
   - 想看清当前项目"已经有哪些 X 类型节点": 用 list_nodes(node_type=
     "character" / "worldbuilding" / "plot" / "idea" / "research" /
     "structure") 取全名单查重, 避免 search_nodes 漏掉低相关分的同类节点
     导致重复创建。
2. 视情况再用 get_node / list_neighbors 看清现有结构, 决定新建什么、连接到哪里。
3. 依据用户请求, 提议 0-3 条 proposed_changes, 支持 5 种 change_type:
   - create_node: 填 payload.title / payload.content / payload.node_type;
     node_type 六选一: character / worldbuilding / plot / idea / research / structure
   - create_edge: 填 payload 四件套:
     * source / target: 同 batch 引用新节点用 pending_id 占位 (例如 "pending-1")
     * relation_type (六选一, 决定边的视觉风格): 
         relates_to (关联,灰色,通用)
       | causes (导致,橙色,因果触发,例如"推动""引发""导致")
       | belongs_to (属于,绿色,归属/参与,例如"参与""属于""发生于")
       | conflicts_with (冲突,红色动画,例如"对抗""死敌""死对头")
       | references (参考,蓝色,例如"补充""引用""参照")
       | develops_into (发展为,紫色,因果递进,例如"发展为""整理为""转化")
     * label (1-4 字中文短语, 画布上显示的文字; 不要抄 relation_type 的英文名,
       而是从 relation_type 的中文释义里挑最贴切的, 例如 "师徒" / "推动" /
       "发展为" / "对抗" / "归属于" / "参考")
   - update_node: target_id 填要改的真实 node_id, payload 至少含 title / content
     / node_type 三者之一
   - delete_node: target_id 填要删的真实 node_id; 同节点的所有边会被一并清掉,
     这是不可逆操作, 仅在用户明确要求"删除/移除/去掉"该节点时才提议
   - delete_edge: 优先填 target_id (真实 edge_id); 不知道 edge_id 时退化填
     payload.source / payload.target / payload.relation_type, 系统会在项目内匹配
   - **create_edge / update_node / delete_node / delete_edge 用到的 id 必须取自
     search_nodes / get_node / list_neighbors 的真实返回值; 严禁按节点标题猜想
     (例如 "char-broll" 这类命名是错的); delete 类操作宁可让用户在 staging 里
     自己点删除, 也不要为了"显得在做事"而硬塞删除项。**
4. reasoning 写明"为什么是这样的结构", 让用户在 staging 卡片上看懂决策依据。

注意: 用户消息上方的【画布相关节点】只是预检索摘要, 不能替代 search_nodes
的实时返回值; 判断"是否已存在"必须以 search_nodes 的实时结果为准, 不要因为
摘要里"看似没有"就直接新建。

最终用 StructureOutput 结构化返回:
- summary: 一句话告诉用户你建议的结构变化
- referenced_node_ids: 决策过程中通过工具实际读到的 node_id (查重 / 找关系
  时看过的真实节点); 没用工具就留空数组
- proposed_changes: 0-3 条变更, 已存在的节点不要重复建

自反思要求 (写到 reasoning 字段, 用 1-2 句概括):
- 给出 proposed_changes 之前先在 reasoning 里自检四件事:
  1. 同 batch 内不允许内容完全相同的项: create_edge 的 (source, target,
     relation_type) 三元组绝不能重复, create_node 的 (title, node_type)
     也不能重复; 同一关系只写 1 条;
  2. create_edge / update_node / delete_node / delete_edge 用到的 id 必须是
     真实 node_id / edge_id 或同 batch pending_id, 绝不能按名字猜;
  3. 用户没有明确说"删/移除/去掉"时, 不要主动提议 delete_* (这是不可逆操作);
  4. 是否真的需要这么多变更, 用户只要求"建一条师徒关系"时就只产 1 条,
     不要为了凑数把同一条复制多份;
- 检查中发现需要丢弃的项, 直接不要写进 proposed_changes, 别留半成品。
"""


def structure_agent_node(state: AgentState) -> dict[str, Any]:
    """ReAct 循环里查重并提议结构变更; LLM 失败时降级到空 proposed_changes。"""
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "")

    initial_messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"{build_memory_block(state)}\n\n"
            f"【用户请求】\n{user_message}"
        ),
    ]

    provider = get_llm_provider()
    tools = make_project_tools(project_id)

    try:
        history = run_tool_loop(provider, initial_messages, tools)
        output = provider.structured(
            compact_history_for_structured(history), StructureOutput
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("structure_agent LLM 调用失败, 降级: %s", error)
        output = StructureOutput(
            reasoning=f"调用失败 ({type(error).__name__})。",
            summary="我这次没能整理出建议结构, 你可以换种问法或稍后重试。",
        )
    return {"structure_output": output}