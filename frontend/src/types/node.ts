import type { Edge, EdgeMarkerType, Position } from '@vue-flow/core'

/** 当前画布支持的节点类型，需要与后端 DTO、节点工厂和 Vue Flow 插槽名保持一致。 */
export type CreativeNodeType = 'character' | 'plot' | 'worldbuilding' | 'idea' | 'research' | 'structure'

/** 节点同步状态，目前用于表达未来 RAG/Agent 处理后的 UI 状态。 */
export type CreativeNodeStatus = 'draft' | 'synced' | 'outdated'

/** 连线关系类型表达创作语义，而不是工作流执行顺序。 */
export type CreativeRelationType =
  | 'relates_to'
  | 'causes'
  | 'belongs_to'
  | 'conflicts_with'
  | 'references'
  | 'develops_into'

/** 连线关系类型的展示选项。 */
export const RELATION_TYPE_OPTIONS: Array<{ value: CreativeRelationType; label: string }> = [
  { value: 'relates_to', label: '关联' },
  { value: 'causes', label: '导致' },
  { value: 'belongs_to', label: '属于' },
  { value: 'conflicts_with', label: '冲突' },
  { value: 'references', label: '参考' },
  { value: 'develops_into', label: '发展为' },
]

/**
 * 节点业务数据。
 *
 * 该结构会随 graph 一起持久化；`isActive` 只是前端选中态，不写入后端。
 */
export interface CreativeNodeData {
  /** 节点标题，用于画布卡片和右侧详情编辑。 */
  title: string
  /** 节点完整内容，画布只展示摘要，右侧面板负责编辑全文。 */
  content: string
  /** 节点业务类型，放在 data 中是为了让右侧编辑区不依赖 Vue Flow 外层 type。 */
  nodeType: CreativeNodeType
  /** 标签用于后续筛选和 RAG 索引，目前先作为字符串数组保存。 */
  tags: string[]
  /** 同步状态当前只是 UI 占位，不代表真的接入了 ChromaDB 或 Agent。 */
  status: CreativeNodeStatus
  /** 展示用图标，避免节点组件反复写类型映射。 */
  icon: string
  /** 展示用类型标签，避免节点组件反复写类型映射。 */
  typeLabel: string
  /** 前端选中态，只服务画布渲染，不参与持久化。 */
  isActive?: boolean
}

/** 业务节点在 Vue Flow 中的最小形态，避免把运行时字段直接扩散到应用状态。 */
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

/** 业务边只保存恢复画布所需的字段；markerEnd 是前端渲染补充项。 */
export interface CreativeFlowEdge {
  id: string
  source: string
  target: string
  /** Vue Flow 内置 label 字段负责画布上的直接展示。 */
  label?: string
  sourceHandle?: string | null
  targetHandle?: string | null
  type?: string
  animated?: boolean
  markerEnd?: EdgeMarkerType
  data: CreativeEdgeData
}

/** 连线业务数据。 */
export interface CreativeEdgeData {
  /** 连线标签是用户可编辑的创作关系文本。 */
  label: string
  /** 关系类型用于后续筛选、结构整理和 RAG 检索扩展。 */
  relationType: CreativeRelationType
}

/** 需要传给 Vue Flow 工具函数时使用的兼容类型。 */
export type VueFlowCompatibleEdge = Edge & CreativeFlowEdge

/** AppShell 和 CanvasWorkspace 之间传递的可保存 graph 快照。 */
export interface CreativeGraphSnapshot {
  nodes: CreativeFlowNode[]
  edges: CreativeFlowEdge[]
}
