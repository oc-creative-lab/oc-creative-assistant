<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { loadSubgraph, saveSubgraph } from '../../api/graphApi'
import { rebuildProjectSeed } from '../../api/projectApi'
import { useGraphMutations } from '../../composables/useGraphMutations'
import { useGraphPersistence } from '../../composables/useGraphPersistence'
import { useIndexingStatus } from '../../composables/useIndexingStatus'
import {
  injectWorkspaceGraphRefresh,
  injectWorkspaceGraphSave,
  injectWorkspaceSelectedNodeIds,
} from '../../composables/useWorkspaceChatContext'
import { useProjectStore } from '../../stores/useProjectStore'
import { useCenterStageStore } from '../../stores/useCenterStageStore'
import { nodeTypeOptions } from '../../utils/nodeFactory'
import type { CreativeNodeType } from '../../types/node'
import CanvasWorkspace from '../canvas/CanvasWorkspace.vue'
import NodeDetailView from './NodeDetailView.vue'

// 工作台保存后 debounce 30s 触发种子重建。
const SEED_REBUILD_DEBOUNCE_MS = 30000
const HIGHLIGHT_DURATION_MS = 2600

/**
 * 单 sub-graph 画布。
 *
 * 复用现有 CanvasWorkspace（Vue Flow）+ AgentSidebar（节点/边详情编辑）+
 * useGraphPersistence/useGraphMutations，仅把加载/保存注入为 sub-graph 维度。
 * 不修改这些组件/composable 的内部逻辑，只组合它们并绑定到 graphId。
 */
const props = defineProps<{
  graphId: string
  /** 该视图允许新建的节点类型（故事线只建 plot、世界观只建 worldbuilding）。 */
  createTypes: CreativeNodeType[]
}>()

const { applyIndexingStatus } = useIndexingStatus()
const projectStore = useProjectStore()
const centerStage = useCenterStageStore()
const workspaceSelectedNodeIds = injectWorkspaceSelectedNodeIds()
const graphRefresh = injectWorkspaceGraphRefresh()
const graphSave = injectWorkspaceGraphSave()

let seedTimer: ReturnType<typeof setTimeout> | null = null
let highlightClearTimer: ReturnType<typeof setTimeout> | null = null

/** 保存成功后排程一次种子重建；连续保存只保留最后一次。 */
function scheduleSeedRebuild() {
  const projectId = projectStore.detail?.id
  if (!projectId) return
  if (seedTimer) clearTimeout(seedTimer)
  seedTimer = setTimeout(() => {
    void rebuildProjectSeed(projectId)
      .then(() => projectStore.loadProject(projectId, true))
      .catch(() => {})
  }, SEED_REBUILD_DEBOUNCE_MS)
}

const {
  graphSnapshot,
  graphNodes,
  graphEdges,
  graphVersion,
  isSaving,
  saveState,
  setGraphSnapshot,
  scheduleAutoSave,
  clearAutoSave,
  loadGraph,
  handleGraphChanged,
  handleSaveGraph,
} = useGraphPersistence(applyIndexingStatus, {
  load: () => loadSubgraph(props.graphId),
  save: async (dto) => {
    const saved = await saveSubgraph(props.graphId, dto)
    scheduleSeedRebuild()
    return saved
  },
})

watch(isSaving, (v) => {
  if (graphSave) graphSave.isSaving.value = v
})

const selectedNodeId = ref('')
const selectedEdgeId = ref('')
const createNodeRequest = ref<{ type: CreativeNodeType; nonce: number } | null>(null)
const highlightedNodeIds = ref<string[]>([])
const highlightedEdgeIds = ref<string[]>([])

const { handleGlobalKeydown } = useGraphMutations({
  graphSnapshot,
  selectedNodeId,
  selectedEdgeId,
  setGraphSnapshot,
  scheduleAutoSave,
})

const TYPE_LABEL_EN: Record<string, string> = {
  character: 'Character',
  worldbuilding: 'Worldbuilding',
  plot: 'Story node',
  idea: 'Idea',
  research: 'Research',
  structure: 'Structure',
}
const createButtons = computed(() =>
  props.createTypes.map((type) => ({
    type,
    label: TYPE_LABEL_EN[type] ?? nodeTypeOptions.find((o) => o.type === type)?.label ?? type,
  })),
)

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
  selectedEdgeId.value = ''
}

function selectEdge(edgeId: string) {
  selectedEdgeId.value = edgeId
  selectedNodeId.value = ''
}

function requestCreateNode(nodeType: CreativeNodeType) {
  createNodeRequest.value = { type: nodeType, nonce: Date.now() }
}

async function reload() {
  clearAutoSave()
  const { initialNodeId } = await loadGraph()
  selectedNodeId.value = initialNodeId
  selectedEdgeId.value = ''
}

async function handleGraphRefreshNeeded() {
  clearAutoSave()

  const prevNodeIds = new Set(graphSnapshot.value.nodes.map((node) => node.id))
  const prevEdgeIds = new Set(graphSnapshot.value.edges.map((edge) => edge.id))

  await reload()

  const newNodeIds = graphSnapshot.value.nodes
    .map((node) => node.id)
    .filter((id) => !prevNodeIds.has(id))
  const newEdgeIds = graphSnapshot.value.edges
    .map((edge) => edge.id)
    .filter((id) => !prevEdgeIds.has(id))

  if (newNodeIds.length === 0 && newEdgeIds.length === 0) {
    return
  }

  highlightedNodeIds.value = newNodeIds
  highlightedEdgeIds.value = newEdgeIds

  if (highlightClearTimer) {
    clearTimeout(highlightClearTimer)
  }
  highlightClearTimer = setTimeout(() => {
    highlightedNodeIds.value = []
    highlightedEdgeIds.value = []
  }, HIGHLIGHT_DURATION_MS)
}

watch(selectedNodeId, (nodeId) => {
  workspaceSelectedNodeIds.value = nodeId ? [nodeId] : []
})

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown, true)
  graphRefresh?.register(handleGraphRefreshNeeded)
  graphSave?.register(handleSaveGraph)
  centerStage.returnToCanvas() // 进入画布视图时复位，避免残留上一个视图的详情态
  void reload()
})

// 从节点详情返回画布时重新加载，确保详情页的编辑已反映到画布。
watch(
  () => centerStage.mode,
  (mode, old) => {
    if (mode === 'canvas' && old === 'detail') void reload()
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown, true)
  graphRefresh?.register(async () => {})
  graphSave?.register(async () => {})
  clearAutoSave()
  if (seedTimer) clearTimeout(seedTimer)
  if (highlightClearTimer) clearTimeout(highlightClearTimer)
})

// 在同一 WorkspaceShell 内切换 plot↔world 时 graphId 变化，需要重新加载。
watch(
  () => props.graphId,
  () => {
    centerStage.returnToCanvas()
    void reload()
  },
)
</script>

<template>
  <transition name="stage" mode="out-in">
  <NodeDetailView
    v-if="centerStage.mode === 'detail' && centerStage.detailNodeId"
    :node-id="centerStage.detailNodeId"
    @return="centerStage.returnToCanvas()"
  />
  <div v-else class="subgraph-canvas">
    <CanvasWorkspace
      :selected-node-id="selectedNodeId"
      :initial-nodes="graphNodes"
      :initial-edges="graphEdges"
      :graph-version="graphVersion"
      :create-node-request="createNodeRequest"
      :highlighted-node-ids="highlightedNodeIds"
      :highlighted-edge-ids="highlightedEdgeIds"
      :create-types="createTypes"
      @node-selected="selectNode"
      @edge-selected="selectEdge"
      @graph-changed="handleGraphChanged"
    >
      <template #toolbar-start>
        <button
          v-for="button in createButtons"
          :key="button.type"
          type="button"
          class="subgraph-canvas__create"
          @click="requestCreateNode(button.type)"
        >
          + New {{ button.label }}
        </button>
      </template>
      <template #toolbar-status>
        <span class="subgraph-canvas__save">
          <span
            v-if="!isSaving && saveState.startsWith('Saved')"
            class="subgraph-canvas__save-dot"
          ></span>
          {{ isSaving ? 'Saving…' : saveState }}
        </span>
      </template>
    </CanvasWorkspace>
  </div>
  </transition>
</template>

<style scoped>
.subgraph-canvas {
  height: 100%;
  display: grid;
  grid-template-rows: minmax(0, 1fr);
}
.subgraph-canvas__create {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  color: var(--accent);
  background: var(--app-bg, #fff);
  cursor: pointer;
  font-size: 13px;
}
.subgraph-canvas__save {
  margin-left: 8px;
  font-size: 12px;
  color: var(--muted, #888);
}
.subgraph-canvas__save-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 50%;
  background: #22c55e;
  vertical-align: middle;
}
</style>
