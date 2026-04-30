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
 * 获取关系类型的中文展示名。
 *
 * Args:
 *   relationType: 业务关系类型。
 *
 * Returns:
 *   用户可读的关系标签。
 */
function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? '关联'
}

/**
 * 规范化后端返回的节点类型。
 *
 * Args:
 *   type: 后端或旧数据中的原始类型字符串。
 *
 * Returns:
 *   当前前端支持的节点类型；未知类型降级为灵感节点。
 */
function normalizeNodeType(type: string): CreativeNodeType {
  const allowedTypes: CreativeNodeType[] = ['character', 'plot', 'worldbuilding', 'idea', 'research', 'structure']

  return allowedTypes.includes(type as CreativeNodeType) ? (type as CreativeNodeType) : 'idea'
}

/**
 * 规范化节点同步状态。
 *
 * Args:
 *   status: 后端或旧数据中的原始状态。
 *
 * Returns:
 *   当前 UI 支持的节点状态。
 */
function normalizeStatus(status: string | undefined): CreativeNodeStatus {
  return status === 'synced' || status === 'outdated' ? status : 'draft'
}

/**
 * 将后端 graph DTO 转换为前端画布快照。
 *
 * Args:
 *   graph: 后端读取接口返回的完整 graph。
 *
 * Returns:
 *   可交给 Vue Flow 渲染的前端 graph 快照。
 */
export function graphDtoToSnapshot(graph: GraphDto): CreativeGraphSnapshot {
  return {
    nodes: graph.nodes.map((node) => graphNodeDtoToFlowNode(node)),
    edges: graph.edges.map((edge) => graphEdgeDtoToFlowEdge(edge)),
  }
}

/**
 * 将前端画布快照转换为后端保存 DTO。
 *
 * Args:
 *   snapshot: AppShell 当前维护的前端 graph 快照。
 *
 * Returns:
 *   去掉 Vue Flow 运行时状态后的保存请求体。
 */
export function snapshotToSaveDto(snapshot: CreativeGraphSnapshot): SaveGraphDto {
  return {
    nodes: snapshot.nodes.map((node) => flowNodeToGraphNodeDto(node)),
    edges: snapshot.edges.map((edge) => flowEdgeToGraphEdgeDto(edge)),
  }
}

/**
 * 将后端节点 DTO 转换为 Vue Flow 节点。
 *
 * 该函数兼容旧 DTO：`nodeType`、`tags`、`status` 缺失时会补齐安全默认值。
 *
 * Args:
 *   node: 后端节点 DTO。
 *
 * Returns:
 *   Vue Flow 可渲染的业务节点。
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
    },
  }
}

/**
 * 将后端边 DTO 转换为 Vue Flow 边。
 *
 * Args:
 *   edge: 后端边 DTO。
 *
 * Returns:
 *   带 marker 和业务关系 data 的前端边。
 */
function graphEdgeDtoToFlowEdge(edge: GraphEdgeDto): CreativeFlowEdge {
  const relationType = edge.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.label || getRelationLabel(relationType)

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
    },
  }
}

/**
 * 将前端节点转换为后端节点 DTO。
 *
 * 保存时去掉 `isActive` 等前端状态，只保留可恢复的业务内容和画布坐标。
 *
 * Args:
 *   node: 前端业务节点。
 *
 * Returns:
 *   后端保存接口需要的节点 DTO。
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
    position: {
      x: node.position.x,
      y: node.position.y,
    },
  }
}

/**
 * 将前端边转换为后端边 DTO。
 *
 * Args:
 *   edge: 前端业务边。
 *
 * Returns:
 *   后端保存接口需要的边 DTO。
 */
function flowEdgeToGraphEdgeDto(edge: CreativeFlowEdge): GraphEdgeDto {
  const relationType = edge.data?.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.data?.label || edge.label || getRelationLabel(relationType)

  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label,
    relationType,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: edge.type ?? 'smoothstep',
    animated: Boolean(edge.animated),
  }
}
