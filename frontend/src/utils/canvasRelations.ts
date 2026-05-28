import { MarkerType } from '@vue-flow/core'
import {
  RELATION_TYPE_OPTIONS,
  type CreativeFlowEdge,
  type CreativeFlowNode,
  type CreativeRelationType,
} from '../types/node'

export const DEFAULT_RELATION_TYPE: CreativeRelationType = 'relates_to'
export const DEFAULT_SOURCE_HANDLE = 'right'
export const DEFAULT_TARGET_HANDLE = 'left'

interface RelationEdgeStyle {
  color: string
  labelBg: string
  animated?: boolean
}

/**
 * 关系类型 → 视觉样式查表。
 *
 * 颜色 / 浅底色 / 是否流动动画对应 stroke、label 背景和 animated 属性。
 * 用 record 而非 switch 是为了后续新增关系类型时只改这一个地方。
 */
const relationEdgeStyles: Record<CreativeRelationType, RelationEdgeStyle> = {
  relates_to: { color: '#64748b', labelBg: '#f8fafc' },
  causes: { color: '#d97706', labelBg: '#fffbeb' },
  belongs_to: { color: '#059669', labelBg: '#ecfdf5' },
  conflicts_with: { color: '#dc2626', labelBg: '#fef2f2', animated: true },
  references: { color: '#2563eb', labelBg: '#eff6ff' },
  develops_into: { color: '#7c3aed', labelBg: '#f5f3ff' },
}

export function getRelationLabel(relationType: CreativeRelationType): string {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? '关联'
}

export function getRelationStyle(relationType: CreativeRelationType): RelationEdgeStyle {
  return relationEdgeStyles[relationType] ?? relationEdgeStyles.relates_to
}

/**
 * 克隆节点并写入前端展示态。
 *
 * Vue Flow 会在交互过程中修改节点对象, 这里避免直接修改父组件传入的 props。
 * highlighted 集合控制"刚出现的节点"短暂闪光, 选中态由 selectedNodeId 决定。
 *
 * Args:
 *   node: 来源节点。
 *   selectedNodeId: 当前选中的节点 ID。
 *   highlighted: 当前应该闪光的节点 ID 集合。
 *
 * Returns:
 *   带有展示态字段的节点副本。
 */
export function cloneNode(
  node: CreativeFlowNode,
  selectedNodeId: string,
  highlighted: Set<string>,
): CreativeFlowNode {
  return {
    ...node,
    class: highlighted.has(node.id) ? 'is-highlighted' : '',
    data: { ...node.data, isActive: node.id === selectedNodeId },
  }
}

/**
 * 补齐连线的展示字段和业务关系类型。
 *
 * 用于从后端、父组件或 Vue Flow 回传连线后, 统一补齐 markerEnd、stroke、
 * label 背景等视觉字段, 并保证 sourceHandle / targetHandle / type 等
 * 必须字段不会丢失。
 *
 * Args:
 *   edge: 原始连线。
 *   highlighted: 当前应该闪光的连线 ID 集合; 缺省为空集 (用于保存快照场景)。
 *
 * Returns:
 *   可稳定渲染并可保存的连线对象。
 */
export function normalizeEdge(
  edge: CreativeFlowEdge,
  highlighted: Set<string> = new Set(),
): CreativeFlowEdge {
  const relationType = edge.data?.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.data?.label || edge.label || getRelationLabel(relationType)
  const relationStyle = getRelationStyle(relationType)
  const classNames = [
    'creative-edge',
    `creative-edge--${relationType}`,
    highlighted.has(edge.id) ? 'is-highlighted' : '',
  ].filter(Boolean)

  return {
    ...edge,
    label,
    sourceHandle: edge.sourceHandle ?? DEFAULT_SOURCE_HANDLE,
    targetHandle: edge.targetHandle ?? DEFAULT_TARGET_HANDLE,
    type: 'orthogonal',
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: relationStyle.color,
    },
    animated: Boolean(edge.animated || relationStyle.animated),
    class: classNames.join(' '),
    style: {
      stroke: relationStyle.color,
    },
    labelStyle: {
      fill: relationStyle.color,
      fontWeight: 700,
    },
    labelBgStyle: {
      fill: relationStyle.labelBg,
      stroke: relationStyle.color,
    },
    interactionWidth: 0,
    data: {
      ...(edge.data ?? {}),
      label,
      relationType,
    },
  }
}