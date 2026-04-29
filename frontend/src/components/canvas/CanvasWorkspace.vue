<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { MarkerType, VueFlow, addEdge, useVueFlow } from '@vue-flow/core'
import type { Connection, Edge, NodeMouseEvent } from '@vue-flow/core'
import type {
  CreativeFlowEdge,
  CreativeFlowNode,
  CreativeGraphSnapshot,
  CreativeNodeType,
} from '../../types/node'
import { createCreativeNode, nodeTypeOptions } from '../../utils/nodeFactory'
import CharacterNode from '../nodes/CharacterNode.vue'
import PlotNode from '../nodes/PlotNode.vue'
import WorldNode from '../nodes/WorldNode.vue'

const FLOW_ID = 'oc-main-flow'

const props = defineProps<{
  // selectedNodeId 由 AppShell 统一维护，画布只负责映射到节点高亮。
  selectedNodeId: string
  initialNodes: CreativeFlowNode[]
  initialEdges: CreativeFlowEdge[]
  // graphVersion 变化表示父组件已从后端拿到新的权威快照。
  graphVersion: number
}>()

const emit = defineEmits<{
  nodeSelected: [nodeId: string]
  nodeAdded: [node: CreativeFlowNode]
  graphChanged: [snapshot: CreativeGraphSnapshot]
}>()

const flowShell = ref<HTMLElement | null>(null)

// 克隆节点时顺手写入选中态，避免直接修改父组件传入的 props。
function cloneNode(node: CreativeFlowNode, selectedNodeId = props.selectedNodeId): CreativeFlowNode {
  return {
    ...node,
    data: { ...node.data, isActive: node.id === selectedNodeId },
  }
}

const nodes = ref<CreativeFlowNode[]>(props.initialNodes.map((node) => cloneNode(node)))
const edges = ref<CreativeFlowEdge[]>(props.initialEdges.map((edge) => ({ ...edge })))
const addNodeCount = ref(0)
const addEdgeCount = ref(0)
const isNodeMenuOpen = ref(false)

// useVueFlow 绑定固定 id，确保工具栏操作的是当前这一个画布实例。
const { fitView, getViewport, setCenter, zoomIn, zoomOut } = useVueFlow({ id: FLOW_ID })

// 把 Vue Flow 内部状态整理成可保存快照，避免 computedPosition 等运行时字段泄漏到后端。
function getGraphSnapshot(): CreativeGraphSnapshot {
  return {
    nodes: nodes.value.map((node) => ({
      id: node.id,
      type: node.type,
      position: { x: node.position.x, y: node.position.y },
      sourcePosition: node.sourcePosition,
      targetPosition: node.targetPosition,
      data: {
        title: node.data.title,
        typeLabel: node.data.typeLabel,
        summary: node.data.summary,
        meta: node.data.meta,
      },
    })),
    edges: edges.value.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      type: edge.type,
      animated: edge.animated,
      markerEnd: edge.markerEnd,
    })),
  }
}

// 通知上层当前 graph 已变化，AppShell 会据此标记未保存并准备保存载荷。
function emitGraphChanged() {
  emit('graphChanged', getGraphSnapshot())
}

// 统一处理选中态，保证左侧点击、画布点击和新建节点都走同一条数据流。
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

    // 等节点选中态写入 DOM 后再移动视口，避免刚加载时定位到旧布局。
    void nextTick(() => {
      void setCenter(centerX, centerY, {
        zoom: 1,
        duration: 260,
      })
    })
  }
}

// 画布节点点击后只向上抛出 id，由 AppShell 负责同步右侧 sidebar。
function handleNodeClick(event: NodeMouseEvent) {
  emit('nodeSelected', event.node.id)
}

// 适应视图：保留为工具栏能力，后续可加快捷键。
function handleFitView() {
  void fitView({ padding: 0.2, duration: 260 })
}

// 放大当前画布视口。
function handleZoomIn() {
  void zoomIn({ duration: 180 })
}

// 缩小当前画布视口。
function handleZoomOut() {
  void zoomOut({ duration: 180 })
}

// 根据当前 viewport 反推画布坐标，让新增节点落在用户正在看的区域中心附近。
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

// 用户先选择节点类型，再用工厂函数生成对应默认节点。
function handleCreateNode(type: CreativeNodeType) {
  addNodeCount.value += 1
  isNodeMenuOpen.value = false

  const node = createCreativeNode(type, addNodeCount.value, getNextNodePosition())

  nodes.value = [...nodes.value, node]
  emit('nodeAdded', node)
  emitGraphChanged()
  emit('nodeSelected', node.id)
}

// 避免同一组 source/target/handle 重复连线，保持 PoC 阶段图数据干净。
function hasDuplicateEdge(connection: Connection) {
  return edges.value.some(
    (edge) =>
      edge.source === connection.source &&
      edge.target === connection.target &&
      (edge.sourceHandle ?? null) === (connection.sourceHandle ?? null) &&
      (edge.targetHandle ?? null) === (connection.targetHandle ?? null),
  )
}

// Vue Flow 的 connect 事件只给连接参数，这里用 addEdge 生成真实 edge 并写入状态。
function handleConnect(connection: Connection) {
  if (!connection.source || !connection.target || connection.source === connection.target) {
    return
  }

  if (hasDuplicateEdge(connection)) {
    return
  }

  addEdgeCount.value += 1

  const edge: CreativeFlowEdge = {
    id: `edge-${connection.source}-${connection.target}-${Date.now()}-${addEdgeCount.value}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle,
    targetHandle: connection.targetHandle,
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
  }

  edges.value = addEdge(edge as Edge, edges.value as Edge[]) as CreativeFlowEdge[]
  emitGraphChanged()
}

// 节点拖拽结束时记录最新 position，并标记当前 graph 需要保存。
function handleNodeDragStop() {
  emitGraphChanged()
}

watch(
  () => props.selectedNodeId,
  (nodeId, oldNodeId) => {
    // 首次 immediate 只同步高亮；后续外部选择才自动聚焦到节点。
    selectNode(nodeId, Boolean(oldNodeId))
  },
  { immediate: true },
)

watch(
  () => props.graphVersion,
  () => {
    // 父组件确认后端快照后，画布用新的初始数据替换本地编辑态。
    nodes.value = props.initialNodes.map((node) => cloneNode(node))
    edges.value = props.initialEdges.map((edge) => ({ ...edge }))

    void nextTick(() => {
      void fitView({ padding: 0.2, duration: 200 })
    })
  },
)
</script>

<template>
  <section class="canvas-workspace">
    <header class="canvas-toolbar">
      <div class="view-tabs" aria-label="&#20027;&#32534;&#36753;&#21306;&#35270;&#22270;&#20999;&#25442;">
        <button class="active" type="button">&#30011;&#24067;&#35270;&#22270;</button>
        <button type="button">&#35282;&#33394;&#20851;&#31995;&#22270;</button>
        <button type="button">&#21095;&#24773;&#33033;&#32476;&#22270;</button>
      </div>

      <div class="canvas-actions" aria-label="&#30011;&#24067;&#24037;&#20855;">
        <button type="button" title="&#25918;&#22823;" @click="handleZoomIn">+</button>
        <button type="button" title="&#32553;&#23567;" @click="handleZoomOut">-</button>
        <button type="button" @click="handleFitView">&#36866;&#24212;&#35270;&#22270;</button>
        <div class="add-node-menu">
          <button type="button" @click="isNodeMenuOpen = !isNodeMenuOpen">
            &#28155;&#21152;&#33410;&#28857;
          </button>
          <div v-if="isNodeMenuOpen" class="node-type-menu" role="menu">
            <button
              v-for="option in nodeTypeOptions"
              :key="option.type"
              type="button"
              role="menuitem"
              @click="handleCreateNode(option.type)"
            >
              {{ option.label }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <div ref="flowShell" class="flow-shell">
      <!-- v-model 绑定本地 refs；拖拽/连线后由事件把可保存快照抛给 AppShell。 -->
      <VueFlow
        :id="FLOW_ID"
        v-model:nodes="nodes"
        v-model:edges="edges"
        class="creative-flow"
        :default-viewport="{ x: 40, y: 36, zoom: 0.82 }"
        :min-zoom="0.35"
        :max-zoom="1.6"
        :nodes-connectable="true"
        :fit-view-on-init="true"
        @connect="handleConnect"
        @node-click="handleNodeClick"
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

.view-tabs,
.canvas-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.view-tabs button,
.canvas-actions button {
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--muted);
  cursor: pointer;
}

.view-tabs button.active,
.canvas-actions button:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent);
}

.canvas-actions button:first-child,
.canvas-actions button:nth-child(2) {
  width: 32px;
  padding: 0;
  color: var(--text);
  font-size: 1.05rem;
  font-weight: 700;
}

.add-node-menu {
  position: relative;
}

.node-type-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 20;
  width: 148px;
  display: grid;
  gap: 4px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-strong);
  box-shadow: 0 14px 28px rgba(31, 41, 51, 0.16);
}

.node-type-menu button {
  width: 100%;
  justify-content: flex-start;
  color: var(--text);
  text-align: left;
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

  .view-tabs,
  .canvas-actions {
    align-items: stretch;
  }
}
</style>
