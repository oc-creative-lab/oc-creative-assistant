<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ConnectionMode, VueFlow, useVueFlow } from '@vue-flow/core'
import type { Edge, NodeMouseEvent } from '@vue-flow/core'
import type {
  CreativeFlowEdge,
  CreativeFlowNode,
  CreativeGraphSnapshot,
  CreativeNodeType,
  CreativeRelationType,
} from '../../types/node'
import { RELATION_TYPE_OPTIONS } from '../../types/node'
import {
  DEFAULT_RELATION_TYPE,
  cloneNode,
  getRelationLabel,
  normalizeEdge,
} from '../../utils/canvasRelations'
import { useCanvasGraph } from '../../composables/useCanvasGraph'
import CharacterNode from '../nodes/CharacterNode.vue'
import IdeaNode from '../nodes/IdeaNode.vue'
import PlotNode from '../nodes/PlotNode.vue'
import ResearchNode from '../nodes/ResearchNode.vue'
import StructureNode from '../nodes/StructureNode.vue'
import WorldNode from '../nodes/WorldNode.vue'

const FLOW_ID = 'oc-main-flow'

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

function closeAllSelects(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-select-container')) {
    isRelationSelectOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeAllSelects)
})

onUnmounted(() => {
  document.removeEventListener('click', closeAllSelects)
})

const nodes = ref<CreativeFlowNode[]>(
  props.initialNodes.map((node) =>
    cloneNode(node, props.selectedNodeId, new Set(props.highlightedNodeIds)),
  ),
)
const edges = ref<CreativeFlowEdge[]>(
  props.initialEdges.map((edge) => normalizeEdge(edge, new Set(props.highlightedEdgeIds))),
)

/* 固定 flow id 确保工具栏操作绑定到当前画布实例, 不被页面上其他 Vue Flow 抢走 */
const { fitView, getViewport, setCenter, zoomIn, zoomOut, findEdge } = useVueFlow({ id: FLOW_ID })

const {
  handleAutoLayout,
  handleCreateNode,
  handleClearCanvas,
  handleConnect,
  handleNodeDragStop,
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
  const nextNodes: CreativeFlowNode[] = []

  for (const node of nodes.value) {
    nextNodes.push({
      ...node,
      data: { ...node.data, isActive: node.id === nodeId },
    })
  }

  nodes.value = nextNodes

  if (!shouldFocus) return

  const target = nodes.value.find((node) => node.id === nodeId)

  if (target) {
    const centerX = target.position.x + 120
    const centerY = target.position.y + 70
    /* 先等待选中态写入 DOM, 避免刚加载时聚焦到 Vue Flow 的旧布局位置 */
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

/** 将视口调整到完整 graph 范围, 便于节点变多后找回全局结构。 */
function handleFitView() {
  void fitView({ padding: 0.2, duration: 260 })
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
    /* 首次 immediate 只同步高亮; 后续外部选择再自动聚焦到节点 */
    selectNode(nodeId, Boolean(oldNodeId && nodeId))
  },
  { immediate: true },
)

watch(
  () => props.graphVersion,
  () => {
    /* 右侧详情编辑或后端恢复后, AppShell 会把新的权威快照推回画布 */
    nodes.value = props.initialNodes.map((node) =>
      cloneNode(node, props.selectedNodeId, new Set(props.highlightedNodeIds)),
    )
    edges.value = props.initialEdges.map((edge) =>
      normalizeEdge(edge, new Set(props.highlightedEdgeIds)),
    )
  },
)

watch(
  () => [props.highlightedNodeIds.join(','), props.highlightedEdgeIds.join(',')],
  () => {
    const highlightedNodes = new Set(props.highlightedNodeIds)
    const highlightedEdges = new Set(props.highlightedEdgeIds)

    nodes.value = nodes.value.map((node) => ({
      ...node,
      class: highlightedNodes.has(node.id) ? 'is-highlighted' : '',
    }))

    edges.value = edges.value.map((edge) => normalizeEdge(edge, highlightedEdges))

    edges.value.forEach((edge) => {
      const internal = findEdge(edge.id)
      if (internal) {
        internal.class = edge.class
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
      <div class="mode-actions" aria-label="画布模式">
        <span class="interaction-hint">点击节点选择，拖拽端点连线</span>
        <label class="relation-picker" for="new-edge-relation">
          新连线关系
          <div class="custom-select-container">
            <div
              class="custom-select-trigger"
              :class="{ 'is-open': isRelationSelectOpen }"
              @click="isRelationSelectOpen = !isRelationSelectOpen"
            >
              <span>{{ getRelationLabel(selectedRelationType) }}</span>
              <div class="custom-select-arrow"></div>
            </div>
            <ul class="custom-select-options" v-show="isRelationSelectOpen">
              <li
                v-for="option in RELATION_TYPE_OPTIONS"
                :key="option.value"
                class="custom-select-option"
                :class="{ 'is-selected': selectedRelationType === option.value }"
                @click="selectedRelationType = option.value; isRelationSelectOpen = false"
              >
                {{ option.label }}
              </li>
            </ul>
          </div>
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

<style scoped src="./CanvasWorkspace.scoped.css"></style>
