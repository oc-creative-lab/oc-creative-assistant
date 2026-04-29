<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { loadDefaultGraph, saveProjectGraph } from '../../api/graphApi'
import { mockWorkspaceStatus } from '../../mocks/workspaceMock'
import type { CreativeFlowEdge, CreativeFlowNode, CreativeGraphSnapshot, CreativeNodeType } from '../../types/node'
import type { WorkspaceStatus } from '../../types/workspace'
import { graphDtoToSnapshot, snapshotToSaveDto } from '../../utils/graphTransform'
import AgentSidebar from './AgentSidebar.vue'
import CanvasWorkspace from '../canvas/CanvasWorkspace.vue'
import ProjectSidebar from './ProjectSidebar.vue'
import StatusBar from './StatusBar.vue'
import TopToolbar from './TopToolbar.vue'

// AppShell 是工作区状态中枢：负责后端加载/保存，以及画布、左侧工具栏、右侧详情之间的同步。
const projectId = ref('')
const projectName = ref('正在加载项目...')
const graphNodes = ref<CreativeFlowNode[]>([])
const graphEdges = ref<CreativeFlowEdge[]>([])
const graphSnapshot = ref<CreativeGraphSnapshot>({ nodes: [], edges: [] })
// graphVersion 用作重载信号：右侧编辑或后端恢复后通知 CanvasWorkspace 接受新的权威快照。
const graphVersion = ref(0)
const selectedNodeId = ref('')
const selectedEdgeId = ref('')
const isGraphReady = ref(false)
const isSaving = ref(false)
const saveState = ref('正在从本地后端加载...')
const createNodeRequest = ref<{ type: CreativeNodeType; nonce: number } | null>(null)
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

const selectedNode = computed(() => {
  return graphSnapshot.value.nodes.find((node) => node.id === selectedNodeId.value) ?? null
})

const selectedEdge = computed(() => {
  return graphSnapshot.value.edges.find((edge) => edge.id === selectedEdgeId.value) ?? null
})

const workspaceStatus = computed<WorkspaceStatus>(() => ({
  ...mockWorkspaceStatus,
  saveState: saveState.value,
}))

function setGraphSnapshot(snapshot: CreativeGraphSnapshot, shouldPushToCanvas = false) {
  graphSnapshot.value = snapshot
  graphNodes.value = snapshot.nodes
  graphEdges.value = snapshot.edges

  if (shouldPushToCanvas) {
    graphVersion.value += 1
  }
}

async function persistGraph(refreshFromResponse = false) {
  if (!projectId.value) {
    return
  }

  if (isSaving.value) {
    if (!refreshFromResponse) {
      scheduleAutoSave()
    }
    return
  }

  try {
    isSaving.value = true
    saveState.value = '正在保存到 SQLite...'
    const savedGraph = await saveProjectGraph(projectId.value, snapshotToSaveDto(graphSnapshot.value))

    if (refreshFromResponse) {
      setGraphSnapshot(graphDtoToSnapshot(savedGraph), true)
    }

    saveState.value = `已保存：${new Date().toLocaleTimeString()}`
  } catch (error) {
    saveState.value = error instanceof Error ? `保存失败：${error.message}` : '保存失败'
  } finally {
    isSaving.value = false
  }
}

function scheduleAutoSave() {
  if (!isGraphReady.value || !projectId.value) {
    return
  }

  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
  }

  saveState.value = '有未保存的画布修改'
  autoSaveTimer = setTimeout(() => {
    // 画布和右侧详情都走同一份快照保存，确保节点内容和连线标签能一起恢复。
    void persistGraph(false)
  }, 600)
}

async function loadGraph() {
  try {
    saveState.value = '正在从 SQLite 加载...'
    const graph = await loadDefaultGraph()
    const snapshot = graphDtoToSnapshot(graph)

    projectId.value = graph.project.id
    projectName.value = graph.project.name
    setGraphSnapshot(snapshot, true)
    selectedNodeId.value = snapshot.nodes[0]?.id ?? ''
    selectedEdgeId.value = ''
    isGraphReady.value = true
    saveState.value = '已从 SQLite 加载'
  } catch (error) {
    isGraphReady.value = false
    saveState.value =
      error instanceof Error
        ? `后端加载失败：${error.message}`
        : '后端加载失败'
  }
}

function handleGraphChanged(snapshot: CreativeGraphSnapshot) {
  setGraphSnapshot(snapshot)
  scheduleAutoSave()
}

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

function handleNodeUpdated(updatedNode: CreativeFlowNode) {
  // 右侧详情编辑节点后更新全局快照，再推回画布并触发自动保存。
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes.map((node) => (node.id === updatedNode.id ? updatedNode : node)),
    edges: graphSnapshot.value.edges,
  }

  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

function handleEdgeUpdated(updatedEdge: CreativeFlowEdge) {
  // 右侧详情编辑连线后要同步 label/data，画布上才能立即显示新的创作关系。
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes,
    edges: graphSnapshot.value.edges.map((edge) => (edge.id === updatedEdge.id ? updatedEdge : edge)),
  }

  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

function handleNodeDeleted(nodeId: string) {
  const node = graphSnapshot.value.nodes.find((item) => item.id === nodeId)

  if (!node) {
    return
  }

  const confirmed = window.confirm(`确定要删除节点「${node.data.title}」吗？相关连线也会一并删除。`)

  if (!confirmed) {
    return
  }

  // 删除节点时必须同步删除所有相关连线，否则后端保存会因为 edge 端点缺失而校验失败。
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes.filter((item) => item.id !== nodeId),
    edges: graphSnapshot.value.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
  }

  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

function handleEdgeDeleted(edgeId: string) {
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes,
    edges: graphSnapshot.value.edges.filter((edge) => edge.id !== edgeId),
  }

  // 删除连线只影响关系本身，不修改两端节点；随后复用统一持久化流程。
  selectedEdgeId.value = ''
  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false
  }

  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if (event.key !== 'Delete' && event.key !== 'Backspace') {
    return
  }

  if (isTypingTarget(event.target)) {
    return
  }

  if (selectedNodeId.value) {
    event.preventDefault()
    event.stopPropagation()
    handleNodeDeleted(selectedNodeId.value)
    return
  }

  if (selectedEdgeId.value) {
    event.preventDefault()
    event.stopPropagation()
    handleEdgeDeleted(selectedEdgeId.value)
  }
}

async function handleSaveGraph() {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }

  await persistGraph(true)
}

onMounted(() => {
  // Delete/Backspace 作为画布快捷键时，只删除当前选中对象；输入框内按键仍保留文本编辑语义。
  window.addEventListener('keydown', handleGlobalKeydown, true)
  void loadGraph()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown, true)

  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
  }
})
</script>

<template>
  <div class="app-shell">
    <TopToolbar :project-name="projectName" :is-saving="isSaving" @save="handleSaveGraph" />

    <main class="workspace-grid">
      <ProjectSidebar
        :nodes="graphNodes"
        @create-node="requestCreateNode"
      />
      <CanvasWorkspace
        :selected-node-id="selectedNodeId"
        :initial-nodes="graphNodes"
        :initial-edges="graphEdges"
        :graph-version="graphVersion"
        :create-node-request="createNodeRequest"
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
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: grid;
  grid-template-rows: 56px minmax(0, 1fr) 30px;
  background: var(--app-bg);
  color: var(--text);
  overflow: hidden;
}

.workspace-grid {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-columns: 300px minmax(420px, 1fr) 360px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  overflow: hidden;
}

@media (max-width: 1120px) {
  .workspace-grid {
    grid-template-columns: 260px minmax(360px, 1fr) 320px;
  }
}

@media (max-width: 920px) {
  .app-shell {
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }
}
</style>
