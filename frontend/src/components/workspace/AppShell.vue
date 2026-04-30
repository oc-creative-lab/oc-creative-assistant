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

/**
 * 工作区状态中枢。
 *
 * AppShell 负责从后端加载和保存 graph，并协调画布、左侧工具栏、右侧详情面板
 * 之间的状态同步。子组件只提交用户意图，权威 graph 快照由这里维护。
 */
const projectId = ref('')
const projectName = ref('正在加载项目...')
const graphNodes = ref<CreativeFlowNode[]>([])
const graphEdges = ref<CreativeFlowEdge[]>([])
const graphSnapshot = ref<CreativeGraphSnapshot>({ nodes: [], edges: [] })
/* graphVersion 是传给 CanvasWorkspace 的重载信号，用于接收后端恢复或右侧编辑后的权威快照。 */
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

/**
 * 写入当前权威 graph 快照。
 *
 * Args:
 *   snapshot: 已完成业务转换的前端 graph 快照。
 *   shouldPushToCanvas: 是否通知画布接受这份外部快照。
 */
function setGraphSnapshot(snapshot: CreativeGraphSnapshot, shouldPushToCanvas = false) {
  graphSnapshot.value = snapshot
  graphNodes.value = snapshot.nodes
  graphEdges.value = snapshot.edges

  if (shouldPushToCanvas) {
    graphVersion.value += 1
  }
}

/**
 * 保存当前 graph 到后端。
 *
 * 自动保存只提交当前快照；手动保存可选择使用后端响应刷新本地状态，保证前端与
 * SQLite 最终落库结果一致。
 *
 * Args:
 *   refreshFromResponse: 是否用后端返回的 graph 覆盖本地快照。
 */
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

/**
 * 安排一次防抖自动保存。
 *
 * 画布拖拽、连线和右侧详情编辑都进入同一保存队列，避免并发请求覆盖较新的快照。
 */
function scheduleAutoSave() {
  if (!isGraphReady.value || !projectId.value) {
    return
  }

  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
  }

  saveState.value = '有未保存的画布修改'
  autoSaveTimer = setTimeout(() => {
    void persistGraph(false)
  }, 600)
}

/**
 * 从后端加载默认项目 graph。
 *
 * 后端会在首次访问默认项目时初始化示例数据；前端拿到 DTO 后转换为 Vue Flow
 * 可直接渲染的快照。
 */
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

/**
 * 接收画布内部产生的 graph 变更。
 *
 * Args:
 *   snapshot: CanvasWorkspace 清理过运行时字段后的可保存快照。
 */
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

/**
 * 接收右侧详情面板的节点编辑结果。
 *
 * Args:
 *   updatedNode: 合并过表单字段的完整节点。
 */
function handleNodeUpdated(updatedNode: CreativeFlowNode) {
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes.map((node) => (node.id === updatedNode.id ? updatedNode : node)),
    edges: graphSnapshot.value.edges,
  }

  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

/**
 * 接收右侧详情面板的连线编辑结果。
 *
 * Args:
 *   updatedEdge: 同步过顶层 label 与 data 的完整连线。
 */
function handleEdgeUpdated(updatedEdge: CreativeFlowEdge) {
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes,
    edges: graphSnapshot.value.edges.map((edge) => (edge.id === updatedEdge.id ? updatedEdge : edge)),
  }

  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

/**
 * 删除节点并同步移除相关连线。
 *
 * Args:
 *   nodeId: 需要删除的节点 ID。
 */
function handleNodeDeleted(nodeId: string) {
  const node = graphSnapshot.value.nodes.find((item) => item.id === nodeId)

  if (!node) {
    return
  }

  const confirmed = window.confirm(`确定要删除节点「${node.data.title}」吗？相关连线也会一并删除。`)

  if (!confirmed) {
    return
  }

  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes.filter((item) => item.id !== nodeId),
    edges: graphSnapshot.value.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
  }

  selectedNodeId.value = ''
  selectedEdgeId.value = ''
  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

/**
 * 删除连线。
 *
 * 删除连线只影响关系本身，不修改两端节点；随后复用统一持久化流程。
 *
 * Args:
 *   edgeId: 需要删除的连线 ID。
 */
function handleEdgeDeleted(edgeId: string) {
  const nextSnapshot: CreativeGraphSnapshot = {
    nodes: graphSnapshot.value.nodes,
    edges: graphSnapshot.value.edges.filter((edge) => edge.id !== edgeId),
  }

  selectedEdgeId.value = ''
  setGraphSnapshot(nextSnapshot, true)
  scheduleAutoSave()
}

/**
 * 判断键盘事件是否发生在文本编辑区域。
 *
 * Args:
 *   target: 原始事件目标。
 *
 * Returns:
 *   在输入控件或可编辑区域内时返回 true。
 */
function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false
  }

  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
}

/**
 * 处理工作区级删除快捷键。
 *
 * Delete/Backspace 作为画布快捷键时只删除当前选中对象；输入框内按键保留文本编辑语义。
 *
 * Args:
 *   event: 全局 keydown 事件。
 */
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

/**
 * 执行手动保存。
 *
 * 手动保存会清掉等待中的自动保存，并使用后端响应刷新本地快照。
 */
async function handleSaveGraph() {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }

  await persistGraph(true)
}

onMounted(() => {
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
