"""阶段 6 节点离线冒烟脚本; 仓库任意目录均可直接 ``python`` 运行。"""

import sys
from pathlib import Path

# 把 backend/ 注入 sys.path, 解耦运行目录与模块查找
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.nodes.research_agent import research_agent_node
from app.agents.nodes.structure_agent import structure_agent_node


research_state = {
    "project_id": "default-project",
    "user_message": "项目里有哪些角色?",   # research 题
    "merged_context": [],
}
structure_state = {
    "project_id": "default-project",
    "user_message": "帮我新建一个名叫黑斯廷的反派角色",   # structure 题
    "merged_context": [],
}
print(research_agent_node(research_state))
print(structure_agent_node(structure_state))