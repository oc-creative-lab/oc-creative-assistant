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

function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? '关联'
}

function normalizeNodeType(type: string): CreativeNodeType {
  const allowedTypes: CreativeNodeType[] = ['character', 'plot', 'worldbuilding', 'idea', 'research', 'structure']

  return allowedTypes.includes(type as CreativeNodeType) ? (type as CreativeNodeType) : 'idea'
}

function normalizeStatus(status: string | undefined): CreativeNodeStatus {
  return status === 'synced' || status === 'outdated' ? status : 'draft'
}

// 将后端 DTO 转成 Vue Flow 节点，补充 handle 方向和前端选中态字段。
export function graphDtoToSnapshot(graph: GraphDto): CreativeGraphSnapshot {
  return {
    nodes: graph.nodes.map((node) => graphNodeDtoToFlowNode(node)),
    edges: graph.edges.map((edge) => graphEdgeDtoToFlowEdge(edge)),
  }
}

// 将当前画布快照转成后端保存 DTO，去掉 Vue Flow 临时状态。
export function snapshotToSaveDto(snapshot: CreativeGraphSnapshot): SaveGraphDto {
  return {
    nodes: snapshot.nodes.map((node) => flowNodeToGraphNodeDto(node)),
    edges: snapshot.edges.map((edge) => flowEdgeToGraphEdgeDto(edge)),
  }
}

function graphNodeDtoToFlowNode(node: GraphNodeDto): CreativeFlowNode {
  // 持久化恢复时兼容旧 DTO：nodeType/tags/status 不存在时给出安全默认值。
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

function graphEdgeDtoToFlowEdge(edge: GraphEdgeDto): CreativeFlowEdge {
  // 旧数据没有 label/relationType 时默认显示“关联”，避免画布恢复时报错或空白。
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

function flowNodeToGraphNodeDto(node: CreativeFlowNode): GraphNodeDto {
  // 保存时去掉 isActive 等前端状态，只保留可恢复的业务内容和画布坐标。
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

function flowEdgeToGraphEdgeDto(edge: CreativeFlowEdge): GraphEdgeDto {
  // 修改关系标签后需要同步持久化，刷新或重启 Electron 才能恢复创作语义。
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
