import type { Edge, EdgeMarkerType, Position } from '@vue-flow/core'

export type CreativeNodeType = 'character' | 'worldbuilding' | 'plot'

export interface CreativeNodeData {
  title: string
  typeLabel: string
  summary: string
  meta: string
  isActive?: boolean
}

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

export type VueFlowCompatibleEdge = Edge & CreativeFlowEdge

export interface CreativeGraphSnapshot {
  nodes: CreativeFlowNode[]
  edges: CreativeFlowEdge[]
}
