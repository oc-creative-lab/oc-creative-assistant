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
 * Relation type -> visual style lookup table.
 *
 * Color / light background / whether to animate flow map to the stroke, label
 * background and animated properties. A record is used instead of a switch so
 * that adding a new relation type later only requires changing this one place.
 */
// The palette stays within the purple / orange / rose (tension) / gray family to echo the overall dreamy tone.
const relationEdgeStyles: Record<CreativeRelationType, RelationEdgeStyle> = {
  relates_to: { color: '#a29bc4', labelBg: '#f6f4fb' },
  causes: { color: '#f59e0b', labelBg: '#fff7ed' },
  belongs_to: { color: '#8b5cf6', labelBg: '#f5f3ff' },
  conflicts_with: { color: '#fb7185', labelBg: '#fff1f3', animated: true },
  references: { color: '#6366f1', labelBg: '#eef2ff' },
  develops_into: { color: '#a855f7', labelBg: '#faf5ff' },
}

export function getRelationLabel(relationType: CreativeRelationType): string {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? 'related'
}

export function getRelationStyle(relationType: CreativeRelationType): RelationEdgeStyle {
  return relationEdgeStyles[relationType] ?? relationEdgeStyles.relates_to
}

/**
 * Clone a node and write in the frontend presentation state.
 *
 * Vue Flow mutates node objects during interactions, so this avoids mutating the
 * props passed in by the parent component directly. The highlighted set controls
 * the brief flash of "just-appeared nodes", while the selected state is determined
 * by selectedNodeId.
 *
 * Args:
 *   node: The source node.
 *   selectedNodeId: The ID of the currently selected node.
 *   highlighted: The set of node IDs that should currently flash.
 *
 * Returns:
 *   A copy of the node with presentation-state fields.
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
 * Fill in an edge's presentation fields and business relation type.
 *
 * Used after an edge is returned from the backend, the parent component or Vue
 * Flow, to uniformly fill in visual fields such as markerEnd, stroke and label
 * background, and to ensure required fields like sourceHandle / targetHandle /
 * type are not lost.
 *
 * Args:
 *   edge: The raw edge.
 *   highlighted: The set of edge IDs that should currently flash; defaults to an empty set (for the save-snapshot scenario).
 *
 * Returns:
 *   An edge object that renders stably and can be saved.
 */
export function normalizeEdge(
  edge: CreativeFlowEdge,
  highlighted: Set<string> = new Set(),
  selected = false,
): CreativeFlowEdge {
  const relationType = edge.data?.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.data?.label || edge.label || getRelationLabel(relationType)
  const relationStyle = getRelationStyle(relationType)
  const classNames = [
    'creative-edge',
    `creative-edge--${relationType}`,
    highlighted.has(edge.id) ? 'is-highlighted' : '',
    selected ? 'is-selected' : '',
  ].filter(Boolean)

  return {
    ...edge,
    selected,
    label,
    sourceHandle: edge.sourceHandle ?? DEFAULT_SOURCE_HANDLE,
    targetHandle: edge.targetHandle ?? DEFAULT_TARGET_HANDLE,
    type: 'bezier',
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
    interactionWidth: 24,
    data: {
      ...(edge.data ?? {}),
      label,
      relationType,
    },
  }
}