<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { ConnectionMode, MarkerType, VueFlow, addEdge, useVueFlow } from '@vue-flow/core'
import type { Connection, Edge, NodeMouseEvent } from '@vue-flow/core'
import type {
  CreativeFlowEdge,
  CreativeFlowNode,
  CreativeGraphSnapshot,
  CreativeNodeType,
  CreativeRelationType,
} from '../../types/node'
import { RELATION_TYPE_OPTIONS } from '../../types/node'
import { createCreativeNode } from '../../utils/nodeFactory'
import CharacterNode from '../nodes/CharacterNode.vue'
import IdeaNode from '../nodes/IdeaNode.vue'
import PlotNode from '../nodes/PlotNode.vue'
import ResearchNode from '../nodes/ResearchNode.vue'
import StructureNode from '../nodes/StructureNode.vue'
import WorldNode from '../nodes/WorldNode.vue'

const FLOW_ID = 'oc-main-flow'
const DEFAULT_RELATION_TYPE: CreativeRelationType = 'relates_to'
const LAYOUT_START_X = 80
const LAYOUT_START_Y = 80
const LAYOUT_COLUMN_GAP = 340
const LAYOUT_ROW_GAP = 180
const DEFAULT_SOURCE_HANDLE = 'right'
const DEFAULT_TARGET_HANDLE = 'left'

const relationEdgeStyles: Record<CreativeRelationType, { color: string; labelBg: string; animated?: boolean }> = {
  relates_to: { color: '#7b8798', labelBg: '#ffffff' },
  causes: { color: '#dc2626', labelBg: '#fee2e2' },
  belongs_to: { color: '#0f766e', labelBg: '#ccfbf1' },
  conflicts_with: { color: '#b42318', labelBg: '#fee2e2', animated: true },
  references: { color: '#2563eb', labelBg: '#dbeafe' },
  develops_into: { color: '#7c3aed', labelBg: '#ede9fe' },
}

/**
 * 创作画布组件。
 *
 * 本组件负责 Vue Flow 运行时交互、节点渲染和连线创建；可持久化的 graph 快照
 * 通过事件交给 AppShell。组件不会直接访问后端，也不维护项目级保存状态。
 */
const props = defineProps<{
  selectedNodeId: string
  initialNodes: CreativeFlowNode[]
  initialEdges: CreativeFlowEdge[]
  graphVersion: number
  createNodeRequest: { type: CreativeNodeType; nonce: number } | null
}>()

const emit = defineEmits<{
  nodeSelected: [nodeId: string]
  edgeSelected: [edgeId: string]
  nodeAdded: [node: CreativeFlowNode]
  graphChanged: [snapshot: CreativeGraphSnapshot]
}>()

const flowShell = ref<HTMLElement | null>(null)
const selectedRelationType = ref<CreativeRelationType>(DEFAULT_RELATION_TYPE)

/**
 * 克隆节点并写入前端选中态。
 *
 * Vue Flow 会在交互过程中修改节点对象；这里避免直接修改父组件传入的 props。
 *
 * Args:
 *   node: 需要写入画布本地状态的节点。
 *   selectedNodeId: 当前选中的节点 ID。
 *
 * Returns:
 *   带有 isActive 展示状态的节点副本。
 */
function cloneNode(node: CreativeFlowNode, selectedNodeId = props.selectedNodeId): CreativeFlowNode {
  return {
    ...node,
    data: { ...node.data, isActive: node.id === selectedNodeId },
  }
}

function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? '关联'
}

function getRelationStyle(relationType: CreativeRelationType) {
  return relationEdgeStyles[relationType] ?? relationEdgeStyles.relates_to
}

/**
 * 补齐连线的展示标签和业务关系类型。
 *
 * Args:
 *   edge: 从后端、父组件或 Vue Flow 回传的连线。
 *
 * Returns:
 *   可稳定渲染并可保存的连线对象。
 */
function normalizeEdge(edge: CreativeFlowEdge): CreativeFlowEdge {
  const relationType = edge.data?.relationType ?? DEFAULT_RELATION_TYPE
  const label = edge.data?.label || edge.label || getRelationLabel(relationType)
  const relationStyle = getRelationStyle(relationType)

  return {
    ...edge,
    label,
    sourceHandle: edge.sourceHandle ?? DEFAULT_SOURCE_HANDLE,
    targetHandle: edge.targetHandle ?? DEFAULT_TARGET_HANDLE,
    type: edge.type ?? 'smoothstep',
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: relationStyle.color,
    },
    animated: Boolean(edge.animated || relationStyle.animated),
    class: `creative-edge creative-edge--${relationType}`,
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
    interactionWidth: 18,
    data: {
      label,
      relationType,
    },
  }
}

const nodes = ref<CreativeFlowNode[]>(props.initialNodes.map((node) => cloneNode(node)))
const edges = ref<CreativeFlowEdge[]>(props.initialEdges.map((edge) => normalizeEdge(edge)))
const addNodeCount = ref(0)
const addEdgeCount = ref(0)

/* 固定 flow id 确保工具栏操作绑定到当前画布实例，而不是页面上其他 Vue Flow。 */
const { fitView, getViewport, setCenter, zoomIn, zoomOut } = useVueFlow({ id: FLOW_ID })

/**
 * 构造可保存的 graph 快照。
 *
 * Vue Flow 会附加 computedPosition、尺寸等运行时字段；保存前只保留业务内容、
 * 坐标和连线恢复所需字段。
 *
 * Returns:
 *   可交给 AppShell 持久化的 graph 快照。
 */
function getGraphSnapshot(): CreativeGraphSnapshot {
  return {
    nodes: nodes.value.map((node) => ({
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
    edges: edges.value.map((edge) => normalizeEdge(edge)),
  }
}

/** 通知 AppShell 当前 graph 已变化，并进入统一自动保存流程。 */
function emitGraphChanged() {
  emit('graphChanged', getGraphSnapshot())
}

/**
 * 更新画布节点选中态，并按需聚焦视口。
 *
 * Args:
 *   nodeId: 需要选中的节点 ID。
 *   shouldFocus: 是否将视口移动到该节点附近。
 */
function selectNode(nodeId: string, shouldFocus = false) {
  const nextNodes: CreativeFlowNode[] = []

  for (const node of nodes.value) {
    nextNodes.push({
      ...node,
      data: { ...node.data, isActive: node.id === nodeId },
    })
  }

  nodes.value = nextNodes

  if (!shouldFocus) {
    return
  }

  const target = nodes.value.find((node) => node.id === nodeId)

  if (target) {
    const centerX = target.position.x + 120
    const centerY = target.position.y + 70

    /* 先等待选中态写入 DOM，避免刚加载时聚焦到 Vue Flow 的旧布局位置。 */
    void nextTick(() => {
      void setCenter(centerX, centerY, {
        zoom: 1,
        duration: 260,
      })
    })
  }
}

/** 将 Vue Flow 节点点击事件上抛给 AppShell 维护全局选中对象。 */
function handleNodeClick(event: NodeMouseEvent) {
  emit('nodeSelected', event.node.id)
}

/** 将 Vue Flow 连线点击事件上抛给 AppShell 维护全局选中对象。 */
function handleEdgeClick(event: { edge: Edge }) {
  emit('edgeSelected', event.edge.id)
}

/** 将视口调整到完整 graph 范围，便于节点变多后找回全局结构。 */
function handleFitView() {
  void fitView({ padding: 0.2, duration: 260 })
}

function handleZoomIn() {
  void zoomIn({ duration: 180 })
}

function handleZoomOut() {
  void zoomOut({ duration: 180 })
}

/**
 * 清空当前画布。
 *
 * 该操作会删除所有节点和连线，因此必须由用户二次确认。
 */
function handleClearCanvas() {
  const confirmed = window.confirm('确定要清空当前画布吗？此操作会删除所有节点和连线。')

  if (!confirmed) {
    return
  }

  nodes.value = []
  edges.value = []
  emit('nodeSelected', '')
  emitGraphChanged()
}

function buildLayoutLayers() {
  const nodeIds = new Set(nodes.value.map((node) => node.id))
  const outgoing = new Map<string, string[]>()
  const incomingCount = new Map<string, number>()
  const layerByNodeId = new Map<string, number>()

  for (const node of nodes.value) {
    outgoing.set(node.id, [])
    incomingCount.set(node.id, 0)
  }

  for (const edge of edges.value) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      continue
    }

    outgoing.get(edge.source)?.push(edge.target)
    incomingCount.set(edge.target, (incomingCount.get(edge.target) ?? 0) + 1)
  }

  const queue = nodes.value
    .filter((node) => (incomingCount.get(node.id) ?? 0) === 0)
    .map((node) => node.id)

  if (queue.length === 0 && nodes.value[0]) {
    queue.push(nodes.value[0].id)
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

  for (const node of nodes.value) {
    if (!layerByNodeId.has(node.id)) {
      layerByNodeId.set(node.id, fallbackLayer)
    }
  }

  const layers = new Map<number, CreativeFlowNode[]>()

  for (const node of nodes.value) {
    const layer = layerByNodeId.get(node.id) ?? 0
    const layerNodes = layers.get(layer) ?? []

    layerNodes.push(node)
    layers.set(layer, layerNodes)
  }

  return layers
}

function handleAutoLayout() {
  if (nodes.value.length === 0) {
    return
  }

  const layers = buildLayoutLayers()

  nodes.value = nodes.value.map((node) => {
    const layer = [...layers.entries()].find(([, layerNodes]) => layerNodes.some((item) => item.id === node.id))?.[0] ?? 0
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
    void fitView({ padding: 0.24, duration: 300 })
  })
}

/**
 * 计算新增节点的画布坐标。
 *
 * 根据当前 viewport 反推画布坐标，让节点落在用户正在查看的区域中心附近。
 *
 * Returns:
 *   新节点应使用的画布坐标。
 */
function getNextNodePosition() {
  const viewport = getViewport()
  const rect = flowShell.value?.getBoundingClientRect()
  const centerX = rect ? rect.width / 2 : 520
  const centerY = rect ? rect.height / 2 : 300
  const offset = addNodeCount.value * 28

  return {
    x: (centerX - viewport.x) / viewport.zoom + offset,
    y: (centerY - viewport.y) / viewport.zoom + offset,
  }
}

/**
 * 根据左侧工具栏请求创建节点。
 *
 * Args:
 *   type: 需要创建的业务节点类型。
 */
function handleCreateNode(type: CreativeNodeType) {
  addNodeCount.value += 1

  const node = createCreativeNode(type, addNodeCount.value, getNextNodePosition())

  nodes.value = [...nodes.value, node]
  emit('nodeAdded', node)
  emitGraphChanged()
  emit('nodeSelected', node.id)
}

/**
 * 判断一次连接是否已存在等价连线。
 *
 * Args:
 *   connection: Vue Flow 提供的连接信息。
 *
 * Returns:
 *   source、target 和 handle 完全一致时返回 true。
 */
function hasDuplicateEdge(connection: Connection) {
  return edges.value.some(
    (edge) =>
      edge.source === connection.source &&
      edge.target === connection.target &&
      (edge.sourceHandle ?? null) === (connection.sourceHandle ?? null) &&
      (edge.targetHandle ?? null) === (connection.targetHandle ?? null),
  )
}

/**
 * 创建用户手动连接的边。
 *
 * 自连接和重复连接会被忽略；新连线默认表达创作关系，不代表工作流执行顺序。
 *
 * Args:
 *   connection: Vue Flow 提供的连接信息。
 */
function handleConnect(connection: Connection) {
  if (!connection.source || !connection.target || connection.source === connection.target) {
    return
  }

  if (hasDuplicateEdge(connection)) {
    return
  }

  addEdgeCount.value += 1
  const relationType = selectedRelationType.value
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

  edges.value = addEdge(normalizeEdge(edge) as Edge, edges.value as Edge[]) as CreativeFlowEdge[]
  emitGraphChanged()
  emit('edgeSelected', edge.id)
}

function handleNodeDragStop() {
  emitGraphChanged()
}

watch(
  () => props.selectedNodeId,
  (nodeId, oldNodeId) => {
    /* 首次 immediate 只同步高亮；后续外部选择再自动聚焦到节点。 */
    selectNode(nodeId, Boolean(oldNodeId && nodeId))
  },
  { immediate: true },
)

watch(
  () => props.graphVersion,
  () => {
    /* 右侧详情编辑或后端恢复后，AppShell 会把新的权威快照推回画布。 */
    nodes.value = props.initialNodes.map((node) => cloneNode(node))
    edges.value = props.initialEdges.map((edge) => normalizeEdge(edge))
  },
)

watch(
  () => props.createNodeRequest?.nonce,
  () => {
    if (!props.createNodeRequest) {
      return
    }

    handleCreateNode(props.createNodeRequest.type)
  },
)
</script>

<template>
  <section class="canvas-workspace">
    <!-- 画布工具栏：只处理画布相关操作 -->
    <header class="canvas-toolbar">
      <div class="mode-actions" aria-label="画布模式">
        <span class="interaction-hint">点击节点选择，拖拽端点连线</span>
        <label class="relation-picker" for="new-edge-relation">
          新连线关系
          <select id="new-edge-relation" v-model="selectedRelationType">
            <option v-for="option in RELATION_TYPE_OPTIONS" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <button type="button" @click="handleAutoLayout">自动布局</button>
      </div>

      <div class="canvas-actions" aria-label="画布工具">
        <button type="button" title="放大" @click="handleZoomIn">+</button>
        <button type="button" title="缩小" @click="handleZoomOut">-</button>
        <button type="button" @click="handleFitView">适配视图</button>
        <button type="button" class="danger" @click="handleClearCanvas">清空画布</button>
      </div>
    </header>

    <div ref="flowShell" class="flow-shell">
      <!-- v-model 绑定本地 refs；拖拽、连线和标签恢复后由事件把可保存快照抛给 AppShell。 -->
      <VueFlow
        :id="FLOW_ID"
        v-model:nodes="nodes"
        v-model:edges="edges"
        class="creative-flow"
        :default-viewport="{ x: 40, y: 36, zoom: 0.82 }"
        :min-zoom="0.35"
        :max-zoom="1.6"
        :nodes-connectable="true"
        :nodes-draggable="true"
        :elements-selectable="true"
        :connection-mode="ConnectionMode.Loose"
        :connect-on-click="false"
        :connection-radius="24"
        :fit-view-on-init="true"
        @connect="handleConnect"
        @node-click="handleNodeClick"
        @edge-click="handleEdgeClick"
        @node-drag-stop="handleNodeDragStop"
      >
        <template #node-character="nodeProps">
          <CharacterNode v-bind="nodeProps" />
        </template>

        <template #node-worldbuilding="nodeProps">
          <WorldNode v-bind="nodeProps" />
        </template>

        <template #node-plot="nodeProps">
          <PlotNode v-bind="nodeProps" />
        </template>

        <template #node-idea="nodeProps">
          <IdeaNode v-bind="nodeProps" />
        </template>

        <template #node-research="nodeProps">
          <ResearchNode v-bind="nodeProps" />
        </template>

        <template #node-structure="nodeProps">
          <StructureNode v-bind="nodeProps" />
        </template>
      </VueFlow>
    </div>
  </section>
</template>

<style scoped>
.canvas-workspace {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  background: var(--canvas-bg);
}

.canvas-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-strong);
}

.mode-actions,
.canvas-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.mode-actions button,
.canvas-actions button,
.relation-picker select {
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--muted);
  cursor: pointer;
}

.mode-actions button:hover,
.canvas-actions button:hover,
.relation-picker select:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent);
}

.interaction-hint {
  color: var(--muted);
  font-size: 0.84rem;
}

.relation-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 0.84rem;
}

.canvas-actions button:first-child,
.canvas-actions button:nth-child(2) {
  width: 32px;
  padding: 0;
  color: var(--text);
  font-size: 1.05rem;
  font-weight: 700;
}

.canvas-actions button.danger {
  color: #b42318;
}

.flow-shell {
  min-height: 0;
}

.creative-flow {
  width: 100%;
  height: 100%;
  background-color: var(--canvas-bg);
  background-image:
    linear-gradient(var(--grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 28px 28px;
}

:deep(.vue-flow__edge-path) {
  stroke: #7b8798;
  stroke-width: 1.8;
}

:deep(.vue-flow__edge.animated .vue-flow__edge-path) {
  stroke: #2764c5;
}

:deep(.creative-edge.vue-flow__edge.animated .vue-flow__edge-path) {
  stroke-dasharray: 8 6;
}

:deep(.vue-flow__edge-text) {
  fill: #1f2933;
  font-size: 12px;
  font-weight: 700;
}

:deep(.vue-flow__edge-textbg) {
  fill: #ffffff;
  stroke: #d9dee7;
}

:deep(.vue-flow__handle) {
  width: 8px;
  height: 8px;
  border: 2px solid #ffffff;
  background: #667085;
}

@media (max-width: 640px) {
  .canvas-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .mode-actions,
  .canvas-actions {
    align-items: stretch;
  }
}
</style>
