"""Graph 默认数据定义。

本模块属于服务层的初始化配置，负责提供默认项目和首屏示例 graph。
它不访问数据库，也不处理 HTTP 请求或向量索引同步。

默认示例与前端 `frontend/src/mocks/graph.ts` 的涉谷站线设定对齐，便于无后端 mock 时
与首屏 SQLite 种子数据一致。
"""

from app.schemas import EdgePayload, NodePayload, PositionPayload

DEFAULT_PROJECT_ID = 'default-project'
DEFAULT_PROJECT_NAME = '《咒术回战》涉谷站线'

DEFAULT_NODES = [
    NodePayload(
        id='char-yuji-ticket',
        type='character',
        title='虎杖检票员',
        content='白天负责检票，晚上负责把逃票咒灵塞回闸机。因为吞过一张特级车票，偶尔会听见列车在胃里报站。',
        meta='角色 / 检票员 / 主角',
        typeLabel='角色',
        tags=['角色', '检票员', '主角'],
        status='synced',
        position=PositionPayload(x=33.47138068598984, y=-17.515147652182712),
    ),
    NodePayload(
        id='char-gojo-stationmaster',
        type='character',
        title='五条站长',
        content='戴着眼罩的神秘站长，能让所有乘客永远差一厘米刷不到卡。他声称这是“无限候车”。',
        meta='角色 / 站长 / 最强',
        typeLabel='角色',
        tags=['角色', '站长', '最强'],
        status='synced',
        position=PositionPayload(x=-64.45790902416242, y=352.6430965700507),
    ),
    NodePayload(
        id='char-nobara-lostfound',
        type='character',
        title='钉崎失物招领员',
        content='负责管理失物招领处，擅长用钉子把乘客遗失的怨念钉回原主人身上。',
        meta='角色 / 失物招领 / 咒具',
        typeLabel='角色',
        tags=['角色', '失物招领', '咒具'],
        status='synced',
        position=PositionPayload(x=159.99062826248527, y=629.992971196864),
    ),
    NodePayload(
        id='world-cursed-station',
        type='worldbuilding',
        title='涉谷地下第零站台',
        content='地图上不存在的地铁站台，只在末班车之后开放。站牌会根据乘客最害怕的地方自动改名。',
        meta='世界观 / 车站 / 诅咒空间',
        typeLabel='世界观',
        tags=['世界观', '车站', '诅咒空间'],
        status='synced',
        position=PositionPayload(x=399.58585794203043, y=-131.52726577392886),
    ),
    NodePayload(
        id='world-ticket-curse',
        type='worldbuilding',
        title='特级咒物：半价月票',
        content='传说只要使用这张月票，就能无限乘车。但代价是永远无法出站，只能在换乘通道里轮回。',
        meta='世界观 / 咒物 / 月票',
        typeLabel='世界观',
        tags=['世界观', '咒物', '月票'],
        status='synced',
        position=PositionPayload(x=194.58721148211174, y=196.8478148386396),
    ),
    NodePayload(
        id='world-announcement',
        type='worldbuilding',
        title='午夜广播系统',
        content='每天 00:00 后，广播会用乘客亲人的声音报站。听到自己名字的人，下一站会被送往“终点站”。',
        meta='世界观 / 广播 / 怪谈',
        typeLabel='世界观',
        tags=['世界观', '广播', '怪谈'],
        status='synced',
        position=PositionPayload(x=777.9052605024667, y=-220.62055743461664),
    ),
    NodePayload(
        id='plot-last-train',
        type='plot',
        title='末班车误入第零站台',
        content='虎杖检票员发现一列不在时刻表上的末班车停靠，车厢里全是没有影子的乘客。',
        meta='剧情 / 第一幕 / 末班车',
        typeLabel='剧情',
        tags=['剧情', '第一幕', '末班车'],
        status='synced',
        position=PositionPayload(x=758.694276137198, y=39.04512050627413),
    ),
    NodePayload(
        id='plot-ticket-awakening',
        type='plot',
        title='半价月票苏醒',
        content='特级咒物半价月票在闸机中苏醒，要求所有乘客补票，补不上的人会被折叠进地铁线路图。',
        meta='剧情 / 冲突 / 咒物觉醒',
        typeLabel='剧情',
        tags=['剧情', '冲突', '咒物觉醒'],
        status='synced',
        position=PositionPayload(x=760.0, y=340.0),
    ),
    NodePayload(
        id='plot-final-transfer',
        type='plot',
        title='终点站换乘仪式',
        content='五条站长决定封锁第零站台，钉崎则在失物招领处找到一枚属于“终点站”的旧站章。',
        meta='剧情 / 高潮 / 封印',
        typeLabel='剧情',
        tags=['剧情', '高潮', '封印'],
        status='synced',
        position=PositionPayload(x=760.0, y=560.0),
    ),
]

DEFAULT_EDGES = [
    EdgePayload(
        id='edge-yuji-last-train',
        source='char-yuji-ticket',
        target='plot-last-train',
        label='发现异常',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-gojo-final-transfer',
        source='char-gojo-stationmaster',
        target='plot-final-transfer',
        label='执行封锁',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-nobara-final-transfer',
        source='char-nobara-lostfound',
        target='plot-final-transfer',
        label='提供站章',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-station-last-train',
        source='world-cursed-station',
        target='plot-last-train',
        label='发生地点',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-ticket-awakening',
        source='world-ticket-curse',
        target='plot-ticket-awakening',
        label='核心咒物',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-last-train-ticket',
        source='plot-last-train',
        target='plot-ticket-awakening',
        label='引出',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-ticket-final',
        source='plot-ticket-awakening',
        target='plot-final-transfer',
        label='升级为',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-world-announcement-plot-last-train-1777562934373-2',
        source='world-announcement',
        target='plot-last-train',
        label='触发怪谈',
        relationType='relates_to',
        type='smoothstep',
    ),
]
