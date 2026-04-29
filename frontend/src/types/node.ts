import type { Edge, EdgeMarkerType, Position } from '@vue-flow/core'

// 当前画布支持的三类业务节点，需要与后端默认数据和 Vue Flow 插槽名保持一致。
export type CreativeNodeType = 'character' | 'worldbuilding' | 'plot'

// 节点卡片展示数据。isActive 是前端选中态，不会保存到后端。
export interface CreativeNodeData {
  title: string
  typeLabel: string
  summary: string
  meta: string
  isActive?: boolean
}

// 业务节点在 Vue Flow 中的最小形态，避免把运行时字段直接扩散到应用状态。
export interface CreativeFlowNode {
  id: string
  type: CreativeNodeType
  position: {
    x: number
    y: number
  }
  sourcePosition?: Position
  targetPosition?: Position
  data: CreativeNodeData
}

// 业务边只保存恢复画布所需的字段；markerEnd 是前端渲染补充项。
export interface CreativeFlowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
  type?: string
  animated?: boolean
  markerEnd?: EdgeMarkerType
}

// 需要传给 Vue Flow 工具函数时使用的兼容类型。
export type VueFlowCompatibleEdge = Edge & CreativeFlowEdge

// AppShell 和 CanvasWorkspace 之间传递的可保存 graph 快照。
export interface CreativeGraphSnapshot {
  nodes: CreativeFlowNode[]
  edges: CreativeFlowEdge[]
}
