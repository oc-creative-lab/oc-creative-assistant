import { MarkerType, Position } from '@vue-flow/core'
import type { GraphDto, GraphEdgeDto, GraphNodeDto, SaveGraphDto } from '../api/graphApi'
import type { CreativeFlowEdge, CreativeFlowNode, CreativeGraphSnapshot } from '../types/node'

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
  // 后端 content 字段进入前端后命名为 summary，更贴近节点卡片语义。
  return {
    id: node.id,
    type: node.type,
    position: node.position,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: node.title,
      typeLabel: node.typeLabel,
      summary: node.content,
      meta: node.meta,
    },
  }
}

function graphEdgeDtoToFlowEdge(edge: GraphEdgeDto): CreativeFlowEdge {
  // markerEnd 只影响 Vue Flow 渲染，后端不需要持久化该对象结构。
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: edge.type,
    animated: edge.animated,
    markerEnd: MarkerType.ArrowClosed,
  }
}

function flowNodeToGraphNodeDto(node: CreativeFlowNode): GraphNodeDto {
  // 保存时去掉 isActive 等前端状态，只保留业务内容和画布坐标。
  return {
    id: node.id,
    type: node.type,
    title: node.data.title,
    content: node.data.summary,
    meta: node.data.meta,
    typeLabel: node.data.typeLabel,
    position: {
      x: node.position.x,
      y: node.position.y,
    },
  }
}

function flowEdgeToGraphEdgeDto(edge: CreativeFlowEdge): GraphEdgeDto {
  // label 当前未在 UI 中编辑，保存为空字符串以满足后端 DTO。
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: '',
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    type: edge.type ?? 'smoothstep',
    animated: Boolean(edge.animated),
  }
}
