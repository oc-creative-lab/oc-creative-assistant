import { nextTick, ref, type Ref } from 'vue'
import { addEdge } from '@vue-flow/core'
import type { Connection, Edge } from '@vue-flow/core'
import type {
  CreativeFlowEdge,
  CreativeFlowNode,
  CreativeGraphSnapshot,
  CreativeNodeType,
  CreativeRelationType,
} from '../types/node'
import { createCreativeNode } from '../utils/nodeFactory'
import {
  DEFAULT_SOURCE_HANDLE,
  DEFAULT_TARGET_HANDLE,
  getRelationLabel,
  normalizeEdge,
} from '../utils/canvasRelations'

const LAYOUT_START_X = 80
const LAYOUT_START_Y = 80
const LAYOUT_COLUMN_GAP = 340
const LAYOUT_ROW_GAP = 180

interface Options {
  nodes: Ref<CreativeFlowNode[]>
  edges: Ref<CreativeFlowEdge[]>
  flowShell: Ref<HTMLElement | null>
  selectedRelationType: Ref<CreativeRelationType>
  fitView: (options?: { padding?: number; duration?: number }) => Promise<unknown> | void
  getViewport: () => { x: number; y: number; zoom: number }
  onGraphChanged: (snapshot: CreativeGraphSnapshot) => void
  onNodeAdded: (node: CreativeFlowNode) => void
  onNodeSelected: (id: string) => void
  onEdgeSelected: (id: string) => void
}

/**
 * Canvas 图操作的核心 composable。
 *
 * 集中所有"会改变 nodes / edges 内容"的交互: 新建节点、清空、自动布局、
 * 手动连线、拖动结束后的快照同步。所有 emit 都通过 options 注入的回调
 * 下放给宿主组件, 让本 composable 不耦合 Vue Flow 之外的业务事件。
 */
export function useCanvasGraph(options: Options) {
  const addNodeCount = ref(0)
  const addEdgeCount = ref(0)

  function getGraphSnapshot(): CreativeGraphSnapshot {
    return {
      nodes: options.nodes.value.map((node) => ({
        id: node.id,
        type: node.type,
        position: { x: node.position.x, y: node.position.y },
        data: {
          title: node.data.title,
          content: node.data.content,
          nodeType: node.data.nodeType,
          tags: [...node.data.tags],
          status: node.data.status,
          icon: node.data.icon,
          typeLabel: node.data.typeLabel,
        },
      })),
      edges: options.edges.value.map((edge) => normalizeEdge(edge)),
    }
  }

  function emitGraphChanged() {
    options.onGraphChanged(getGraphSnapshot())
  }

  /**
   * 按 BFS 层级把所有节点分桶, 用于自动布局。
   *
   * 入度为 0 的节点放第 0 层; 与任何边都不相连的孤儿放到末层。
   * 不构造严格 DAG 也能给出"看起来合理"的层级。
   *
   * Returns:
   *   Map<层号, 该层节点数组>。
   */
  function buildLayoutLayers() {
    const allNodes = options.nodes.value
    const allEdges = options.edges.value
    const nodeIds = new Set(allNodes.map((node) => node.id))
    const outgoing = new Map<string, string[]>()
    const incomingCount = new Map<string, number>()
    const layerByNodeId = new Map<string, number>()

    for (const node of allNodes) {
      outgoing.set(node.id, [])
      incomingCount.set(node.id, 0)
    }

    for (const edge of allEdges) {
      if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
        continue
      }
      outgoing.get(edge.source)?.push(edge.target)
      incomingCount.set(edge.target, (incomingCount.get(edge.target) ?? 0) + 1)
    }

    const queue = allNodes
      .filter((node) => (incomingCount.get(node.id) ?? 0) === 0)
      .map((node) => node.id)

    if (queue.length === 0 && allNodes[0]) {
      queue.push(allNodes[0].id)
    }

    const visited = new Set<string>()

    for (const nodeId of queue) {
      layerByNodeId.set(nodeId, 0)
      visited.add(nodeId)
    }

    for (let cursor = 0; cursor < queue.length; cursor += 1) {
      const nodeId = queue[cursor]
      const currentLayer = layerByNodeId.get(nodeId) ?? 0

      for (const targetId of outgoing.get(nodeId) ?? []) {
        if (!visited.has(targetId)) {
          layerByNodeId.set(targetId, currentLayer + 1)
          visited.add(targetId)
          queue.push(targetId)
        }
      }
    }

    const fallbackLayer = Math.max(0, ...layerByNodeId.values()) + 1

    for (const node of allNodes) {
      if (!layerByNodeId.has(node.id)) {
        layerByNodeId.set(node.id, fallbackLayer)
      }
    }

    const layers = new Map<number, CreativeFlowNode[]>()

    for (const node of allNodes) {
      const layer = layerByNodeId.get(node.id) ?? 0
      const layerNodes = layers.get(layer) ?? []
      layerNodes.push(node)
      layers.set(layer, layerNodes)
    }

    return layers
  }

  function handleAutoLayout() {
    if (options.nodes.value.length === 0) return

    const layers = buildLayoutLayers()

    options.nodes.value = options.nodes.value.map((node) => {
      const layer =
        [...layers.entries()].find(([, layerNodes]) =>
          layerNodes.some((item) => item.id === node.id),
        )?.[0] ?? 0
      const layerNodes = layers.get(layer) ?? []
      const row = layerNodes.findIndex((item) => item.id === node.id)

      return {
        ...node,
        sourcePosition: undefined,
        targetPosition: undefined,
        position: {
          x: LAYOUT_START_X + layer * LAYOUT_COLUMN_GAP,
          y: LAYOUT_START_Y + Math.max(row, 0) * LAYOUT_ROW_GAP,
        },
      }
    })

    emitGraphChanged()
    void nextTick(() => {
      void options.fitView({ padding: 0.24, duration: 300 })
    })
  }

  /**
   * 计算新增节点的画布坐标。
   *
   * 根据当前 viewport 反推画布坐标, 让节点落在用户正在查看的区域中心附近;
   * 多次连续新建时按计数偏移, 避免叠在同一坐标。
   */
  function getNextNodePosition() {
    const viewport = options.getViewport()
    const rect = options.flowShell.value?.getBoundingClientRect()
    const centerX = rect ? rect.width / 2 : 520
    const centerY = rect ? rect.height / 2 : 300
    const offset = addNodeCount.value * 28

    return {
      x: (centerX - viewport.x) / viewport.zoom + offset,
      y: (centerY - viewport.y) / viewport.zoom + offset,
    }
  }

  function handleCreateNode(type: CreativeNodeType) {
    addNodeCount.value += 1
    const node = createCreativeNode(type, addNodeCount.value, getNextNodePosition())
    options.nodes.value = [...options.nodes.value, node]
    options.onNodeAdded(node)
    emitGraphChanged()
    options.onNodeSelected(node.id)
  }

  function handleClearCanvas() {
    const confirmed = window.confirm('确定要清空当前画布吗？此操作会删除所有节点和连线。')
    if (!confirmed) return

    options.nodes.value = []
    options.edges.value = []
    options.onNodeSelected('')
    emitGraphChanged()
  }

  function hasDuplicateEdge(connection: Connection) {
    return options.edges.value.some(
      (edge) =>
        edge.source === connection.source &&
        edge.target === connection.target &&
        (edge.sourceHandle ?? null) === (connection.sourceHandle ?? null) &&
        (edge.targetHandle ?? null) === (connection.targetHandle ?? null),
    )
  }

  function handleConnect(connection: Connection) {
    if (!connection.source || !connection.target || connection.source === connection.target) {
      return
    }
    if (hasDuplicateEdge(connection)) return

    addEdgeCount.value += 1
    const relationType = options.selectedRelationType.value
    const label = getRelationLabel(relationType)

    const edge: CreativeFlowEdge = {
      id: `edge-${connection.source}-${connection.target}-${Date.now()}-${addEdgeCount.value}`,
      source: connection.source,
      target: connection.target,
      label,
      sourceHandle: connection.sourceHandle ?? DEFAULT_SOURCE_HANDLE,
      targetHandle: connection.targetHandle ?? DEFAULT_TARGET_HANDLE,
      type: 'smoothstep',
      data: {
        label,
        relationType,
      },
    }

    options.edges.value = addEdge(
      normalizeEdge(edge) as Edge,
      options.edges.value as Edge[],
    ) as CreativeFlowEdge[]
    emitGraphChanged()
    options.onEdgeSelected(edge.id)
  }

  function handleNodeDragStop() {
    emitGraphChanged()
  }

  return {
    handleAutoLayout,
    handleCreateNode,
    handleClearCanvas,
    handleConnect,
    handleNodeDragStop,
  }
}