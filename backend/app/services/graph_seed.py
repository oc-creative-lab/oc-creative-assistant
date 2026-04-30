"""Graph 默认数据定义。

本模块属于服务层的初始化配置，负责提供默认项目和首屏示例 graph。
它不访问数据库，也不处理 HTTP 请求或向量索引同步。
"""

from app.schemas import EdgePayload, NodePayload, PositionPayload


DEFAULT_PROJECT_ID = "default-project"
DEFAULT_PROJECT_NAME = "星庭档案"

DEFAULT_NODES = [
    NodePayload(
        id="char-airin",
        type="character",
        title="艾琳",
        content="年轻的见习记录官，对王都隐藏的魔法痕迹异常敏感。",
        meta="主角 / 视角节点",
        typeLabel="角色",
        tags=["角色", "主角"],
        status="synced",
        position=PositionPayload(x=40, y=80),
    ),
    NodePayload(
        id="char-mentor",
        type="character",
        title="导师",
        content="曾经服务于王室档案馆，保留着关于古老契约的秘密。",
        meta="引导者 / 信息源",
        typeLabel="角色",
        tags=["角色", "导师"],
        status="draft",
        position=PositionPayload(x=40, y=290),
    ),
    NodePayload(
        id="world-capital",
        type="worldbuilding",
        title="王都",
        content="建在三层古城遗址上的都城，地下仍有未注销的旧魔法阵。",
        meta="核心场景 / 城市",
        typeLabel="世界观",
        tags=["世界观", "城市"],
        status="synced",
        position=PositionPayload(x=360, y=40),
    ),
    NodePayload(
        id="world-magic-rule",
        type="worldbuilding",
        title="魔法规则",
        content="所有术式都需要以真名或记忆作为锚点，代价会追溯到施术者。",
        meta="规则 / 约束",
        typeLabel="设定",
        tags=["世界观", "规则"],
        status="outdated",
        position=PositionPayload(x=360, y=250),
    ),
    NodePayload(
        id="plot-first-meet",
        type="plot",
        title="初遇事件",
        content="艾琳在王都集市追查失窃档案，意外遇到伪装身份的导师。",
        meta="第一幕 / 开端",
        typeLabel="剧情",
        tags=["剧情", "第一幕"],
        status="draft",
        position=PositionPayload(x=700, y=120),
    ),
    NodePayload(
        id="plot-conflict-rise",
        type="plot",
        title="冲突升级",
        content="魔法阵被意外启动，王都地下遗址开始影响地表秩序。",
        meta="第二幕 / 压力",
        typeLabel="剧情",
        tags=["剧情", "冲突"],
        status="draft",
        position=PositionPayload(x=1020, y=210),
    ),
    NodePayload(
        id="idea-memory-cost",
        type="idea",
        title="记忆代价灵感",
        content="如果真名魔法会改写记忆，角色每次施术都可能遗失一个重要关系。",
        meta="灵感 / 代价",
        typeLabel="灵感",
        tags=["灵感", "魔法"],
        status="draft",
        position=PositionPayload(x=700, y=340),
    ),
    NodePayload(
        id="research-archive-source",
        type="research",
        title="档案馆资料来源",
        content="记录王室档案馆公开职责、隐藏职责和旧契约材料的参考摘要。",
        meta="资料 / 档案",
        typeLabel="资料",
        tags=["资料", "档案"],
        status="draft",
        position=PositionPayload(x=1020, y=20),
    ),
    NodePayload(
        id="structure-act-one",
        type="structure",
        title="第一幕结构整理",
        content="把失窃档案、初遇导师、魔法阵异动串成第一幕的因果链。",
        meta="结构 / 第一幕",
        typeLabel="结构整理",
        tags=["结构", "剧情"],
        status="draft",
        position=PositionPayload(x=1320, y=180),
    ),
]

DEFAULT_EDGES = [
    EdgePayload(
        id="edge-airin-first-meet",
        source="char-airin",
        target="plot-first-meet",
        label="参与",
        relationType="belongs_to",
    ),
    EdgePayload(
        id="edge-mentor-first-meet",
        source="char-mentor",
        target="plot-first-meet",
        label="推动",
        relationType="causes",
    ),
    EdgePayload(
        id="edge-capital-first-meet",
        source="world-capital",
        target="plot-first-meet",
        label="发生于",
        relationType="belongs_to",
    ),
    EdgePayload(
        id="edge-magic-conflict",
        source="world-magic-rule",
        target="plot-conflict-rise",
        label="导致",
        relationType="causes",
    ),
    EdgePayload(
        id="edge-first-meet-conflict",
        source="plot-first-meet",
        target="plot-conflict-rise",
        label="发展为",
        relationType="develops_into",
        animated=True,
    ),
    EdgePayload(
        id="edge-idea-magic-rule",
        source="idea-memory-cost",
        target="world-magic-rule",
        label="补充",
        relationType="references",
    ),
    EdgePayload(
        id="edge-conflict-structure",
        source="plot-conflict-rise",
        target="structure-act-one",
        label="整理为",
        relationType="develops_into",
    ),
]
