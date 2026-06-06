<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { ConnectionMode, SelectionMode, VueFlow, getRectOfNodes, useVueFlow } from '@vue-flow/core'
import type { Edge, NodeMouseEvent } from '@vue-flow/core'
import type {
  CreativeFlowEdge,
  CreativeFlowNode,
  CreativeGraphSnapshot,
  CreativeNodeType,
  CreativeRelationType,
} from '../../types/node'
import {
  DEFAULT_RELATION_TYPE,
  cloneNode,
  normalizeEdge,
} from '../../utils/canvasRelations'
import { useCanvasGraph } from '../../composables/useCanvasGraph'
import { useComposerStore } from '../../stores/useComposerStore'
import { useCenterStageStore } from '../../stores/useCenterStageStore'
import CanvasContextMenu from './CanvasContextMenu.vue'
import CharacterNode from '../nodes/CharacterNode.vue'
import IdeaNode from '../nodes/IdeaNode.vue'
import PlotNode from '../nodes/PlotNode.vue'
import ResearchNode from '../nodes/ResearchNode.vue'
import StructureNode from '../nodes/StructureNode.vue'
import WorldNode from '../nodes/WorldNode.vue'
import OrthogonalEdge from './edges/OrthogonalEdge.vue'

const FLOW_ID = `oc-main-flow-${Math.random().toString(36).slice(2, 9)}`

/**
 * 创作画布组件。
 *
 * 本组件负责 Vue Flow 运行时交互、节点渲染, 以及外部 props (graphVersion /
 * createNodeRequest / highlightedXxxIds) 与本地 nodes/edges 的同步;
 * 涉及图内容增删改的核心操作集中在 useCanvasGraph, 关系类型 / 节点 clone
 * 等纯函数放在 utils/canvasRelations。
 */
const props = defineProps<{
  selectedNodeId: string
  initialNodes: CreativeFlowNode[]
  initialEdges: CreativeFlowEdge[]
  graphVersion: number
  createNodeRequest: { type: CreativeNodeType; nonce: number } | null
  /* 由 AppShell 在 staging 接受后做差集计算的"刚出现"的 ID; 跑完动画后会清空 */
  highlightedNodeIds: string[]
  highlightedEdgeIds: string[]
  /* 右键空白处可新建的节点类型；SubgraphCanvas 按 sub-graph 传入，未传则给全部类型 */
  createTypes?: CreativeNodeType[]
}>()

const emit = defineEmits<{
  nodeSelected: [nodeId: string]
  edgeSelected: [edgeId: string]
  nodeAdded: [node: CreativeFlowNode]
  graphChanged: [snapshot: CreativeGraphSnapshot]
}>()

const flowShell = ref<HTMLElement | null>(null)
const selectedRelationType = ref<CreativeRelationType>(DEFAULT_RELATION_TYPE)
const isRelationSelectOpen = ref(false)
const skipNextFocus = ref(false)

function closeAllSelects(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-select-container')) {
    isRelationSelectOpen.value = false
  }
  if (!target.closest('.ctx-menu')) {
    contextMenu.value.show = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeAllSelects)
  window.addEventListener('keydown', handleCopyKey, true)
})

onUnmounted(() => {
  document.removeEventListener('click', closeAllSelects)
  window.removeEventListener('keydown', handleCopyKey, true)
})

const nodes = ref<CreativeFlowNode[]>(
  props.initialNodes.map((node) =>
    cloneNode(node, props.selectedNodeId, new Set(props.highlightedNodeIds)),
  ),
)
const edges = ref<CreativeFlowEdge[]>(
  props.initialEdges.map((edge) => normalizeEdge(edge, new Set(props.highlightedEdgeIds))),
)

const {
  fitView,
  getViewport,
  setCenter,
  zoomIn,
  zoomOut,
  findEdge,
  onPaneContextMenu,
  onNodeContextMenu,
  onEdgeContextMenu,
  onNodeDoubleClick,
  onNodesInitialized,
  screenToFlowCoordinate,
  getNodes,
  getSelectedNodes,
} = useVueFlow({ id: FLOW_ID })

const FIT_MAX_ZOOM = 0.9
const FIXED_ZOOM = Number(localStorage.getItem('oc.canvasZoom')) || 0.8
const SNAP_TO_GRID = localStorage.getItem('oc.snapToGrid') === 'true'
const pendingFit = ref(true)

onNodesInitialized(() => {
  if (!pendingFit.value || getNodes.value.length === 0) return
  pendingFit.value = false
  const rect = getRectOfNodes(getNodes.value)
  void setCenter(rect.x + rect.width / 2, rect.y + rect.height / 2, { zoom: FIXED_ZOOM })
})

const {
  handleAutoLayout,
  handleCreateNode,
  handleClearCanvas,
  handleConnect,
  handleEdgeUpdate,
  updateEdgeData,
  handleNodeDragStop,
  applyEdgeWaypoint,
  updateNodeData,
  removeNode,
  removeEdge,
} = useCanvasGraph({
  nodes,
  edges,
  flowShell,
  selectedRelationType,
  fitView,
  getViewport,
  onGraphChanged: (snapshot) => emit('graphChanged', snapshot),
  onNodeAdded: (node) => emit('nodeAdded', node),
  onNodeSelected: (id) => emit('nodeSelected', id),
  onEdgeSelected: (id) => emit('edgeSelected', id),
})

provide('applyEdgeWaypoint', applyEdgeWaypoint)
provide('updateNodeData', updateNodeData)
provide('updateEdgeData', updateEdgeData)

const composer = useComposerStore()
const centerStage = useCenterStageStore()

const ALL_NODE_TYPES: CreativeNodeType[] = [
  'idea',
  'character',
  'worldbuilding',
  'plot',
  'research',
  'structure',
]
const blankCreateTypes = computed(() => props.createTypes ?? ALL_NODE_TYPES)

const contextMenu = ref<{
  show: boolean
  x: number
  y: number
  type: 'blank' | 'node' | 'edge'
  nodeId: string
  edgeId: string
}>({ show: false, x: 0, y: 0, type: 'blank', nodeId: '', edgeId: '' })

function closeContextMenu() {
  contextMenu.value.show = false
}

onPaneContextMenu((event) => {
  const mouse = event as MouseEvent
  mouse.preventDefault()
  contextMenu.value = { show: true, x: mouse.clientX, y: mouse.clientY, type: 'blank', nodeId: '', edgeId: '' }
})

onNodeContextMenu(({ event, node }) => {
  const mouse = event as MouseEvent
  mouse.preventDefault()
  contextMenu.value = {
    show: true,
    x: mouse.clientX,
    y: mouse.clientY,
    type: 'node',
    nodeId: node.id,
    edgeId: '',
  }
})

onEdgeContextMenu(({ event, edge }) => {
  const mouse = event as MouseEvent
  mouse.preventDefault()
  contextMenu.value = {
    show: true, x: mouse.clientX, y: mouse.clientY,
    type: 'edge', nodeId: '', edgeId: edge.id,
  }
})

// 双击节点 → 进入节点详情（中栏 NodeDetailView），带上当前数据快照。
onNodeDoubleClick(({ node }) => {
  centerStage.openDetail(node.id, {
    id: node.id,
    title: node.data?.title ?? '',
    content: node.data?.content ?? '',
    nodeType: (node.data?.nodeType ?? node.type ?? 'idea') as string,
    typeLabel: node.data?.typeLabel ?? '',
    icon: node.data?.icon ?? '',
    tags: [...(node.data?.tags ?? [])],
    status: node.data?.status ?? 'draft',
  })
})

function nodeRef(nodeId: string) {
  return nodes.value.find((node) => node.id === nodeId)
}

function handleMenuCreate(type: CreativeNodeType) {
  const pos = screenToFlowCoordinate({ x: contextMenu.value.x, y: contextMenu.value.y })
  handleCreateNode(type, { x: pos.x, y: pos.y })
  closeContextMenu()
}

function handleMenuEdit() {
  if (contextMenu.value.nodeId) centerStage.openDetail(contextMenu.value.nodeId)
  closeContextMenu()
}

function handleMenuDuplicate() {
  const src = nodeRef(contextMenu.value.nodeId)
  if (src) {
    handleCreateNode(src.data.nodeType ?? (src.type as CreativeNodeType), {
      x: src.position.x + 40,
      y: src.position.y + 40,
    })
    const created = nodes.value[nodes.value.length - 1]
    if (created) {
      updateNodeData(created.id, {
        title: `${src.data.title} (copy)`,
        content: src.data.content,
      })
    }
  }
  closeContextMenu()
}

function handleMenuRemove() {
  if (contextMenu.value.type === 'edge') {
    if (contextMenu.value.edgeId) removeEdge(contextMenu.value.edgeId)
  } else if (contextMenu.value.nodeId) {
    removeNode(contextMenu.value.nodeId)
  }
  closeContextMenu()
}

function handleMenuSetColor(color: string) {
  if (contextMenu.value.edgeId) updateEdgeData(contextMenu.value.edgeId, { color })
  contextMenu.value.show = false
}

function handleMenuSetDashed(dashed: boolean) {
  if (contextMenu.value.edgeId) updateEdgeData(contextMenu.value.edgeId, { dashed })
  contextMenu.value.show = false
}

function quoteNodes(refs: { id: string; type: string; title: string }[]) {
  if (refs.length) composer.addReferences(refs)
}

function handleMenuQuote() {
  const src = nodeRef(contextMenu.value.nodeId)
  if (src) {
    quoteNodes([{ id: src.id, type: src.data.nodeType ?? src.type ?? 'idea', title: src.data.title }])
  }
  closeContextMenu()
}

/** Ctrl/Cmd+C：把当前多选的节点复制成引用卡片到底部对话框（改点 C）。 */
function handleCopyKey(event: KeyboardEvent) {
  if (!((event.ctrlKey || event.metaKey) && event.key === 'c')) return
  const selected = getSelectedNodes.value
  if (selected.length === 0) return
  event.preventDefault()
  quoteNodes(
    selected.map((node) => ({
      id: node.id,
      type: (node.data?.nodeType ?? node.type ?? 'idea') as string,
      title: node.data?.title || 'Untitled',
    })),
  )
}

/**
 * 更新画布节点选中态, 并按需聚焦视口。
 *
 * 视觉层面的选中标记由本组件维护; 业务侧的"当前选中"由 AppShell 经
 * props.selectedNodeId 推回, 形成单向数据流。
 *
 * Args:
 *   nodeId: 需要选中的节点 ID。
 *   shouldFocus: 是否将视口移动到该节点附近。
 */
 function selectNode(nodeId: string, shouldFocus = false) {
  for (const node of nodes.value) {
    if (node.data.isActive !== (node.id === nodeId)) {
      node.data.isActive = node.id === nodeId
    }
  }

  if (!shouldFocus) return

  const target = nodes.value.find((node) => node.id === nodeId)
  if (!target) return

  const centerX = target.position.x + 120
  const centerY = target.position.y + 70
  void nextTick(() => {
    void setCenter(centerX, centerY, { duration: 260 })
  })
}

/** 将 Vue Flow 节点点击事件上抛给 AppShell 维护全局选中对象。 */
function handleNodeClick(event: NodeMouseEvent) {
  skipNextFocus.value = true
  emit('nodeSelected', event.node.id)
}

/** 将 Vue Flow 连线点击事件上抛给 AppShell 维护全局选中对象。 */
function handleEdgeClick(event: { edge: Edge }) {
  skipNextFocus.value = true
  emit('edgeSelected', event.edge.id)
}

function handleFitView() {
  void fitView({ padding: 0.2, maxZoom: FIT_MAX_ZOOM, duration: 260 })
}

function handleZoomIn() {
  void zoomIn({ duration: 180 })
}

function handleZoomOut() {
  void zoomOut({ duration: 180 })
}

watch(
  () => props.selectedNodeId,
  (nodeId, oldNodeId) => {
    const fromCanvas = skipNextFocus.value
    skipNextFocus.value = false
    selectNode(nodeId, !fromCanvas && Boolean(oldNodeId && nodeId))
  },
  { immediate: true },
)

watch(
  () => props.graphVersion,
  () => {
    nodes.value = props.initialNodes.map((node) =>
      cloneNode(node, props.selectedNodeId, new Set(props.highlightedNodeIds)),
    )
    edges.value = props.initialEdges.map((edge) =>
      normalizeEdge(edge, new Set(props.highlightedEdgeIds)),
    )
    pendingFit.value = true
  },
)

watch(
  () => [props.highlightedNodeIds.join(','), props.highlightedEdgeIds.join(',')],
  () => {
    const highlightedNodes = new Set(props.highlightedNodeIds)
    const highlightedEdges = new Set(props.highlightedEdgeIds)

    for (const node of nodes.value) {
      const next = highlightedNodes.has(node.id) ? 'is-highlighted' : ''
      if (node.class !== next) {
        node.class = next
      }
    }

    edges.value.forEach((edge) => {
      const normalized = normalizeEdge(edge, highlightedEdges)
      edge.class = normalized.class
      const internal = findEdge(edge.id)
      if (internal) {
        internal.class = normalized.class
      }
    })
  },
)

watch(
  () => props.createNodeRequest?.nonce,
  () => {
    if (!props.createNodeRequest) return
    handleCreateNode(props.createNodeRequest.type)
  },
)
</script>

<template>
  <section class="canvas-workspace">
    <!-- 画布工具栏：只处理画布相关操作 -->
    <header class="canvas-toolbar">
      <div class="mode-actions" aria-label="canvas mode">
        <slot name="toolbar-start" />
        <button type="button" @click="handleAutoLayout">Auto layout</button>
      </div>

      <div class="canvas-actions" aria-label="canvas tools">
        <button type="button" title="Zoom in" @click="handleZoomIn">+</button>
        <button type="button" title="Zoom out" @click="handleZoomOut">-</button>
        <button type="button" @click="handleFitView">Fit</button>
        <button type="button" class="danger" @click="handleClearCanvas">Clear</button>
        <slot name="toolbar-status" />
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
        :edges-updatable="true"
        :connection-mode="ConnectionMode.Loose"
        :connect-on-click="false"
        :connection-radius="24"
        :fit-view-on-init="false"
        :snap-to-grid="SNAP_TO_GRID"
        :snap-grid="[16, 16]"
        :selection-key-code="'Shift'"
        :multi-selection-key-code="['Shift', 'Meta', 'Control']"
        :selection-mode="SelectionMode.Partial"
        @connect="handleConnect"
        @edge-update="handleEdgeUpdate"
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

        <template #edge-orthogonal="edgeProps">
          <OrthogonalEdge v-bind="edgeProps" />
        </template>
      </VueFlow>
    </div>

    <CanvasContextMenu
      :show="contextMenu.show"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :menu-type="contextMenu.type"
      :create-types="blankCreateTypes"
      @create="handleMenuCreate"
      @edit="handleMenuEdit"
      @duplicate="handleMenuDuplicate"
      @remove="handleMenuRemove"
      @quote="handleMenuQuote"
      @close="closeContextMenu"
      @set-color="handleMenuSetColor"
      @set-dashed="handleMenuSetDashed"
    />
  </section>
</template>

<style scoped src="./CanvasWorkspace.scoped.css"></style>
