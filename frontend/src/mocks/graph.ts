import { MarkerType, Position } from '@vue-flow/core'
import type { CreativeFlowEdge, CreativeFlowNode } from '../types/node'
import { createNodeData } from '../utils/nodeFactory'

/**
 * 《咒术回战》涉谷站线风格 mock 节点（与后端 `app/services/graph_seed.py` 默认示例对齐）。
 *
 * 设定：一个被咒力污染的地铁站，每到末班车后，站内广播会开始念出不存在的站名。
 */
export const mockGraphNodes: CreativeFlowNode[] = [
  {
    id: 'char-yuji-ticket',
    type: 'character',
    position: { x: 33.47138068598984, y: -17.515147652182712 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: '虎杖检票员',
      content:
        '白天负责检票，晚上负责把逃票咒灵塞回闸机。因为吞过一张特级车票，偶尔会听见列车在胃里报站。',
      typeLabel: '角色',
      tags: ['角色', '检票员', '主角'],
      status: 'synced',
    },
  },
  {
    id: 'char-gojo-stationmaster',
    type: 'character',
    position: { x: -64.45790902416242, y: 352.6430965700507 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: '五条站长',
      content: '戴着眼罩的神秘站长，能让所有乘客永远差一厘米刷不到卡。他声称这是“无限候车”。',
      typeLabel: '角色',
      tags: ['角色', '站长', '最强'],
      status: 'synced',
    },
  },
  {
    id: 'char-nobara-lostfound',
    type: 'character',
    position: { x: 159.99062826248527, y: 629.992971196864 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: '钉崎失物招领员',
      content: '负责管理失物招领处，擅长用钉子把乘客遗失的怨念钉回原主人身上。',
      typeLabel: '角色',
      tags: ['角色', '失物招领', '咒具'],
      status: 'synced',
    },
  },
  {
    id: 'world-cursed-station',
    type: 'worldbuilding',
    position: { x: 399.58585794203043, y: -131.52726577392886 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: '涉谷地下第零站台',
      content: '地图上不存在的地铁站台，只在末班车之后开放。站牌会根据乘客最害怕的地方自动改名。',
      typeLabel: '世界观',
      tags: ['世界观', '车站', '诅咒空间'],
      status: 'synced',
    },
  },
  {
    id: 'world-ticket-curse',
    type: 'worldbuilding',
    position: { x: 194.58721148211174, y: 196.8478148386396 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: '特级咒物：半价月票',
      content: '传说只要使用这张月票，就能无限乘车。但代价是永远无法出站，只能在换乘通道里轮回。',
      typeLabel: '世界观',
      tags: ['世界观', '咒物', '月票'],
      status: 'synced',
    },
  },
  {
    id: 'world-announcement',
    type: 'worldbuilding',
    position: { x: 777.9052605024667, y: -220.62055743461664 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: '午夜广播系统',
      content:
        '每天 00:00 后，广播会用乘客亲人的声音报站。听到自己名字的人，下一站会被送往“终点站”。',
      typeLabel: '世界观',
      tags: ['世界观', '广播', '怪谈'],
      status: 'synced',
    },
  },
  {
    id: 'plot-last-train',
    type: 'plot',
    position: { x: 758.694276137198, y: 39.04512050627413 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: '末班车误入第零站台',
      content: '虎杖检票员发现一列不在时刻表上的末班车停靠，车厢里全是没有影子的乘客。',
      typeLabel: '剧情',
      tags: ['剧情', '第一幕', '末班车'],
      status: 'synced',
    },
  },
  {
    id: 'plot-ticket-awakening',
    type: 'plot',
    position: { x: 760, y: 340 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: '半价月票苏醒',
      content: '特级咒物半价月票在闸机中苏醒，要求所有乘客补票，补不上的人会被折叠进地铁线路图。',
      typeLabel: '剧情',
      tags: ['剧情', '冲突', '咒物觉醒'],
      status: 'synced',
    },
  },
  {
    id: 'plot-final-transfer',
    type: 'plot',
    position: { x: 760, y: 560 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: '终点站换乘仪式',
      content: '五条站长决定封锁第零站台，钉崎则在失物招领处找到一枚属于“终点站”的旧站章。',
      typeLabel: '剧情',
      tags: ['剧情', '高潮', '封印'],
      status: 'synced',
    },
  },
]

/** 《咒术回战》涉谷站线风格 mock 连线（与后端 `graph_seed.py` 一致）。 */
export const mockGraphEdges: CreativeFlowEdge[] = [
  {
    id: 'edge-yuji-last-train',
    source: 'char-yuji-ticket',
    target: 'plot-last-train',
    label: '发现异常',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '发现异常',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-gojo-final-transfer',
    source: 'char-gojo-stationmaster',
    target: 'plot-final-transfer',
    label: '执行封锁',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '执行封锁',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-nobara-final-transfer',
    source: 'char-nobara-lostfound',
    target: 'plot-final-transfer',
    label: '提供站章',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '提供站章',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-station-last-train',
    source: 'world-cursed-station',
    target: 'plot-last-train',
    label: '发生地点',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '发生地点',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-ticket-awakening',
    source: 'world-ticket-curse',
    target: 'plot-ticket-awakening',
    label: '核心咒物',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '核心咒物',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-last-train-ticket',
    source: 'plot-last-train',
    target: 'plot-ticket-awakening',
    label: '引出',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '引出',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-ticket-final',
    source: 'plot-ticket-awakening',
    target: 'plot-final-transfer',
    label: '升级为',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '升级为',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-world-announcement-plot-last-train-1777562934373-2',
    source: 'world-announcement',
    target: 'plot-last-train',
    label: '触发怪谈',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '触发怪谈',
      relationType: 'relates_to',
    },
  },
]
