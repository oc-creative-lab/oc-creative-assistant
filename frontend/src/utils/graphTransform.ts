import { MarkerType, Position } from '@vue-flow/core'
import type { GraphDto, GraphEdgeDto, GraphNodeDto, SaveGraphDto } from '../api/graphApi'
import {
  RELATION_TYPE_OPTIONS,
  type CreativeFlowEdge,
  type CreativeFlowNode,
  type CreativeGraphSnapshot,
  type CreativeNodeStatus,
  type CreativeNodeType,
  type CreativeRelationType,
} from '../types/node'
import { getNodeTypeOption } from './nodeFactory'

const DEFAULT_RELATION_TYPE: CreativeRelationType = 'relates_to'

/**
 * Get the display name of a relation type.
 *
 * Args:
 *   relationType: The business relation type.
 *
 * Returns:
 *   A user-readable relation label.
 */
function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? 'related'
}

/**
 * Normalize the node type returned by the backend.
 *
 * Args:
 *   type: The raw type string from the backend or legacy data.
 *
 * Returns:
 *   A node type currently supported by the frontend; unknown types fall back to the idea node.
 */
function normalizeNodeType(type: string): CreativeNodeType {
  const allowedTypes: CreativeNodeType[] = ['character', 'plot', 'worldbuilding', 'idea', 'research', 'structure']

  return allowedTypes.includes(type as CreativeNodeType) ? (type as CreativeNodeType) : 'idea'
}

/**
 * Normalize the node sync status.
 *
 * Args:
 *   status: The raw status from the backend or legacy data.
 *
 * Returns:
 *   A node status currently supported by the UI.
 */
function normalizeStatus(status: string | undefined): CreativeNodeStatus {
  return status === 'synced' || status === 'outdated' ? status : 'draft'
}

/**
 * Convert a backend graph DTO into a frontend canvas snapshot.
 *
 * Args:
 *   graph: The complete graph returned by the backend read endpoint.
 *
 * Returns:
 *   A frontend graph snapshot that can be handed to Vue Flow for rendering.
 */
export function graphDtoToSnapshot(graph: GraphDto): CreativeGraphSnapshot {
  return {
    nodes: graph.nodes.map((node) => graphNodeDtoToFlowNode(node)),
    edges: graph.edges.map((edge) => graphEdgeDtoToFlowEdge(edge)),
  }
}

/**
 * Convert a frontend canvas snapshot into a backend save DTO.
 *
 * Args:
 *   snapshot: The frontend graph snapshot currently maintained by AppShell.
 *
 * Returns:
 *   The save request body with Vue Flow runtime state removed.
 */
export function snapshotToSaveDto(snapshot: CreativeGraphSnapshot): SaveGraphDto {
  return {
    nodes: snapshot.nodes.map((node) => flowNodeToGraphNodeDto(node)),
    edges: snapshot.edges.map((edge) => flowEdgeToGraphEdgeDto(edge)),
  }
}

/**
 * Convert a backend node DTO into a Vue Flow node.
 *
 * This function is compatible with legacy DTOs: when `nodeType`, `tags` or `status` are missing, safe defaults are filled in.
 *
 * Args:
 *   node: The backend node DTO.
 *
 * Returns:
 *   A business node that Vue Flow can render.
 */
function graphNodeDtoToFlowNode(node: GraphNodeDto): CreativeFlowNode {
  const nodeType = normalizeNodeType(node.nodeType ?? node.type)
  const option = getNodeTypeOption(nodeType)

  return {
    id: node.id,
    type: nodeType,
    position: node.position,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: node.title,
      content: node.content,
      nodeType,
      tags: node.tags ?? (node.meta ? node.meta.split('/').map((tag) => tag.trim()).filter(Boolean) : []),
      status: normalizeStatus(node.status),
      icon: option.icon,
      typeLabel: node.typeLabel || option.label,
      parentId: node.parentId ?? null,
      sortOrder: node.sortOrder ?? 0,
    },
  }
}

/**
 * Convert a backend edge DTO into a Vue Flow edge.
 *
 * Args:
 *   edge: The backend edge DTO.
 *
 * Returns:
 *   A frontend edge with a marker and business relation data.
 */
function graphEdgeDtoToFlowEdge(edge: GraphEdgeDto): CreativeFlowEdge {
  const relationType = edge.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.label || getRelationLabel(relationType)
  const waypoint = edge.waypoint
    ? {
        orientation: edge.waypoint.orientation,
        middle: edge.waypoint.middle,
        nearSource: edge.waypoint.nearSource ?? undefined,
        nearTarget: edge.waypoint.nearTarget ?? undefined,
      }
    : undefined

  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: edge.type,
    animated: edge.animated,
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label,
      relationType,
      waypoint,
    },
  }
}

/**
 * Convert a frontend node into a backend node DTO.
 *
 * On save, frontend state such as `isActive` is dropped, keeping only the recoverable business content and canvas coordinates.
 *
 * Args:
 *   node: The frontend business node.
 *
 * Returns:
 *   The node DTO required by the backend save endpoint.
 */
function flowNodeToGraphNodeDto(node: CreativeFlowNode): GraphNodeDto {
  return {
    id: node.id,
    type: node.type,
    nodeType: node.data.nodeType,
    title: node.data.title,
    content: node.data.content,
    meta: node.data.tags.join(' / '),
    typeLabel: node.data.typeLabel,
    tags: node.data.tags,
    status: node.data.status,
    parentId: node.data.parentId ?? null,
    sortOrder: node.data.sortOrder ?? 0,
    position: {
      x: node.position.x,
      y: node.position.y,
    },
  }
}

/**
 * Convert a frontend edge into a backend edge DTO.
 *
 * Args:
 *   edge: The frontend business edge.
 *
 * Returns:
 *   The edge DTO required by the backend save endpoint.
 */
function flowEdgeToGraphEdgeDto(edge: CreativeFlowEdge): GraphEdgeDto {
  const relationType = edge.data?.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.data?.label || edge.label || getRelationLabel(relationType)
  const wp = edge.data?.waypoint

  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label,
    relationType,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: edge.type ?? 'bezier',
    animated: Boolean(edge.animated),
    waypoint: wp
      ? {
          orientation: wp.orientation,
          middle: wp.middle,
          nearSource: wp.nearSource ?? null,
          nearTarget: wp.nearTarget ?? null,
        }
      : null,
  }
}
