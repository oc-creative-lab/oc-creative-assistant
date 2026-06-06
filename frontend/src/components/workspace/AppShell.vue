<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useGraphMutations } from '../../composables/useGraphMutations'
import { useGraphPersistence } from '../../composables/useGraphPersistence'
import { useIndexingStatus } from '../../composables/useIndexingStatus'
import { mockWorkspaceStatus } from '../../mocks/workspaceMock'
import type { CreativeNodeType } from '../../types/node'
import type { WorkspaceStatus } from '../../types/workspace'
import AgentSidebar from './AgentSidebar.vue'
import CanvasWorkspace from '../canvas/CanvasWorkspace.vue'
import FloatingChatDock from '../chat/FloatingChatDock.vue'
import ProjectSidebar from './ProjectSidebar.vue'
import StatusBar from './StatusBar.vue'
import TopToolbar from './TopToolbar.vue'

const HIGHLIGHT_DURATION_MS = 2600

/**
 * 工作区状态中枢。
 *
 * 三个 composable 各自负责: 索引状态翻译 (useIndexingStatus)、graph 加载与
 * 防抖保存 (useGraphPersistence)、详情面板编辑与键盘删除 (useGraphMutations)。
 * AppShell 只组合它们, 维护选中态、staging 接受后的高亮态和顶层模板。
 */
const {
  indexingStatus,
  indexingAlert,
  indexState,
  applyIndexingStatus,
  dismissAlert,
} = useIndexingStatus()

const {
  projectId,
  projectName,
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
} = useGraphPersistence(applyIndexingStatus)

const selectedNodeId = ref('')
const selectedEdgeId = ref('')
const createNodeRequest = ref<{ type: CreativeNodeType; nonce: number } | null>(null)
const highlightedNodeIds = ref<string[]>([])
const highlightedEdgeIds = ref<string[]>([])
let highlightClearTimer: ReturnType<typeof setTimeout> | null = null

const {
  handleNodeUpdated,
  handleEdgeUpdated,
  handleNodeDeleted,
  handleEdgeDeleted,
  handleGlobalKeydown,
} = useGraphMutations({
  graphSnapshot,
  selectedNodeId,
  selectedEdgeId,
  setGraphSnapshot,
  scheduleAutoSave,
})

const selectedNode = computed(() =>
  graphSnapshot.value.nodes.find((node) => node.id === selectedNodeId.value) ?? null,
)

const selectedEdge = computed(() =>
  graphSnapshot.value.edges.find((edge) => edge.id === selectedEdgeId.value) ?? null,
)

const selectedNodeIds = computed(() =>
  selectedNodeId.value ? [selectedNodeId.value] : [],
)

const workspaceStatus = computed<WorkspaceStatus>(() => ({
  ...mockWorkspaceStatus,
  saveState: saveState.value,
  indexState: indexState.value,
}))

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
  selectedEdgeId.value = ''
}

function selectEdge(edgeId: string) {
  selectedEdgeId.value = edgeId
  selectedNodeId.value = ''
}

function requestCreateNode(nodeType: CreativeNodeType) {
  createNodeRequest.value = {
    type: nodeType,
    nonce: Date.now(),
  }
}

async function refreshGraphSelection() {
  const { initialNodeId } = await loadGraph()
  selectedNodeId.value = initialNodeId
  selectedEdgeId.value = ''
}

async function handleGraphRefreshNeeded() {
  /* staging 接受后, 后端已经写好新节点/新边; 此刻本地 snapshot 还停留在"接受前"。
     如果在等待面板时用户碰过画布, autoSaveTimer 已经排上 — 必须直接丢弃,
     绝对不能再 persistGraph(旧 snapshot), 否则新 edge 会被全量覆盖回退。
     loadGraph 完了之后用户再动画布, 会基于新 snapshot 重新触发 auto-save。 */
  clearAutoSave()

  const prevNodeIds = new Set(graphSnapshot.value.nodes.map((node) => node.id))
  const prevEdgeIds = new Set(graphSnapshot.value.edges.map((edge) => edge.id))

  await refreshGraphSelection()

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

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown, true)
  void refreshGraphSelection()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown, true)
  clearAutoSave()
  if (highlightClearTimer) {
    clearTimeout(highlightClearTimer)
  }
})
</script>

<template>
  <div class="app-shell">
    <TopToolbar :project-name="projectName" :is-saving="isSaving" @save="handleSaveGraph" />

    <div class="indexing-alert" :class="{ 'is-hidden': !indexingAlert }" role="alert" aria-live="polite">
      <template v-if="indexingAlert">
        <span>{{ indexingAlert }}</span>
        <button type="button" class="indexing-alert__close" @click="dismissAlert">Dismiss</button>
      </template>
    </div>

    <main class="workspace-grid">
      <ProjectSidebar
        :project-id="projectId"
        :nodes="graphNodes"
        :selected-node="selectedNode"
        :indexing-status="indexingStatus"
        @create-node="requestCreateNode"
        @node-selected="selectNode"
      />
      <CanvasWorkspace
        :selected-node-id="selectedNodeId"
        :initial-nodes="graphNodes"
        :initial-edges="graphEdges"
        :graph-version="graphVersion"
        :create-node-request="createNodeRequest"
        :highlighted-node-ids="highlightedNodeIds"
        :highlighted-edge-ids="highlightedEdgeIds"
        @node-selected="selectNode"
        @edge-selected="selectEdge"
        @graph-changed="handleGraphChanged"
      />
      <AgentSidebar
        :selected-node="selectedNode"
        :selected-edge="selectedEdge"
        :nodes="graphNodes"
        @node-updated="handleNodeUpdated"
        @node-deleted="handleNodeDeleted"
        @edge-updated="handleEdgeUpdated"
        @edge-deleted="handleEdgeDeleted"
      />
    </main>

    <StatusBar :status="workspaceStatus" />

    <FloatingChatDock
      v-if="projectId"
      :project-id="projectId"
      :selected-node-ids="selectedNodeIds"
      @graph-refresh-needed="handleGraphRefreshNeeded"
    />
  </div>
</template>

<style scoped src="./AppShell.scoped.css"></style>