import { MarkerType, Position } from '@vue-flow/core'
import type { CreativeFlowEdge, CreativeFlowNode } from '../types/node'
import { createNodeData } from '../utils/nodeFactory'

// 早期前端独立演示用 graph；当前主要作为 mock 状态和开发兜底数据来源。
export const mockGraphNodes: CreativeFlowNode[] = [
  {
    id: 'char-airin',
    type: 'character',
    position: { x: 40, y: 80 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: '艾琳',
      content: '年轻的见习记录官，对王都隐藏的魔法痕迹异常敏感。',
      tags: ['角色', '主角'],
      status: 'synced',
    },
  },
  {
    id: 'world-capital',
    type: 'worldbuilding',
    position: { x: 360, y: 40 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: '王都',
      content: '建在三层古城遗址上的都城，地下仍有未注销的旧魔法阵。',
      tags: ['世界观', '城市'],
      status: 'synced',
    },
  },
  {
    id: 'plot-first-meet',
    type: 'plot',
    position: { x: 700, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: '初遇事件',
      content: '艾琳在王都集市追查失窃档案，意外遇到伪装身份的导师。',
      tags: ['剧情', '第一幕'],
    },
  },
]

export const mockGraphEdges: CreativeFlowEdge[] = [
  {
    id: 'edge-airin-first-meet',
    source: 'char-airin',
    target: 'plot-first-meet',
    label: '参与',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '参与',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-capital-first-meet',
    source: 'world-capital',
    target: 'plot-first-meet',
    label: '发生于',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: '发生于',
      relationType: 'belongs_to',
    },
  },
]
