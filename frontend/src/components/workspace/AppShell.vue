<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { loadDefaultGraph, saveProjectGraph } from '../../api/graphApi'
import { mockWorkspaceStatus } from '../../mocks/workspaceMock'
import type { CreativeFlowEdge, CreativeFlowNode, CreativeGraphSnapshot } from '../../types/node'
import type { ProjectGroup, ProjectItem, WorkspaceStatus } from '../../types/workspace'
import { buildProjectGroupsFromNodes } from '../../utils/nodeFactory'
import { graphDtoToSnapshot, snapshotToSaveDto } from '../../utils/graphTransform'
import AgentSidebar from './AgentSidebar.vue'
import CanvasWorkspace from '../canvas/CanvasWorkspace.vue'
import ProjectSidebar from './ProjectSidebar.vue'
import StatusBar from './StatusBar.vue'
import TopToolbar from './TopToolbar.vue'

// AppShell 是工作区状态中枢：负责后端加载/保存，以及三栏组件之间的选中态同步。
const projectId = ref('')
const projectName = ref('\u6b63\u5728\u52a0\u8f7d\u9879\u76ee...')
const projectGroups = ref<ProjectGroup[]>([])
const graphNodes = ref<CreativeFlowNode[]>([])
const graphEdges = ref<CreativeFlowEdge[]>([])
// graphSnapshot 始终保存“当前画布可提交版本”，保存按钮只读取这份数据。
const graphSnapshot = ref<CreativeGraphSnapshot>({ nodes: [], edges: [] })
// graphVersion 用作重载信号：后端数据保存/加载后通知 CanvasWorkspace 重新接受初始数据。
const graphVersion = ref(0)
const selectedNodeId = ref('')
const isGraphReady = ref(false)
const isSaving = ref(false)
const saveState = ref('\u6b63\u5728\u4ece\u672c\u5730\u540e\u7aef\u52a0\u8f7d...')

// 右侧 sidebar 使用统一的当前节点对象；还没加载完成时显示轻量占位。
const selectedNode = computed<ProjectItem>(() => {
  const node = projectGroups.value
    .flatMap((group) => group.items)
    .find((item) => item.id === selectedNodeId.value)

  return (
    node ?? {
      id: '',
      title: '\u672a\u9009\u62e9\u8282\u70b9',
      kind: '\u5360\u4f4d',
      summary: '\u4ece\u5de6\u4fa7\u9879\u76ee\u9762\u677f\u6216\u4e2d\u95f4\u753b\u5e03\u9009\u62e9\u8282\u70b9\u3002',
      meta: '\u7b49\u5f85\u9009\u62e9',
    }
  )
})

const workspaceStatus = computed<WorkspaceStatus>(() => ({
  ...mockWorkspaceStatus,
  saveState: saveState.value,
}))

// 从后端加载默认项目 graph，并用返回数据初始化画布和左侧分组。
async function loadGraph() {
  try {
    saveState.value = '\u6b63\u5728\u4ece SQLite \u52a0\u8f7d...'
    const graph = await loadDefaultGraph()
    const snapshot = graphDtoToSnapshot(graph)

    projectId.value = graph.project.id
    projectName.value = graph.project.name
    graphNodes.value = snapshot.nodes
    graphEdges.value = snapshot.edges
    graphSnapshot.value = snapshot
    projectGroups.value = buildProjectGroupsFromNodes(snapshot.nodes)
    selectedNodeId.value = snapshot.nodes[0]?.id ?? ''
    isGraphReady.value = true
    graphVersion.value += 1
    saveState.value = '\u5df2\u4ece SQLite \u52a0\u8f7d'
  } catch (error) {
    isGraphReady.value = false
    saveState.value =
      error instanceof Error
        ? `\u540e\u7aef\u52a0\u8f7d\u5931\u8d25\uff1a${error.message}`
        : '\u540e\u7aef\u52a0\u8f7d\u5931\u8d25'
  }
}

// 左侧点击和画布点击最终都更新同一个 selectedNodeId。
function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
}

// 画布编辑后同步最新快照，保存按钮会使用这份数据提交到后端。
function handleGraphChanged(snapshot: CreativeGraphSnapshot) {
  graphSnapshot.value = snapshot
  projectGroups.value = buildProjectGroupsFromNodes(snapshot.nodes)

  if (isGraphReady.value && !isSaving.value) {
    saveState.value = '\u6709\u672a\u4fdd\u5b58\u7684\u753b\u5e03\u4fee\u6539'
  }
}

// 顶部保存按钮触发手动保存，后端会整体替换该项目 graph。
async function handleSaveGraph() {
  if (!projectId.value || isSaving.value) {
    return
  }

  try {
    isSaving.value = true
    saveState.value = '\u6b63\u5728\u4fdd\u5b58\u5230 SQLite...'
    const savedGraph = await saveProjectGraph(projectId.value, snapshotToSaveDto(graphSnapshot.value))
    const snapshot = graphDtoToSnapshot(savedGraph)

    graphNodes.value = snapshot.nodes
    graphEdges.value = snapshot.edges
    graphSnapshot.value = snapshot
    projectGroups.value = buildProjectGroupsFromNodes(snapshot.nodes)
    // 保存后重置画布来源数据，避免 CanvasWorkspace 继续持有旧初始 props。
    graphVersion.value += 1
    saveState.value = `\u5df2\u4fdd\u5b58\uff1a${new Date().toLocaleTimeString()}`
  } catch (error) {
    saveState.value =
      error instanceof Error ? `\u4fdd\u5b58\u5931\u8d25\uff1a${error.message}` : '\u4fdd\u5b58\u5931\u8d25'
  } finally {
    isSaving.value = false
  }
}

onMounted(() => {
  void loadGraph()
})
</script>

<template>
  <div class="app-shell">
    <TopToolbar :project-name="projectName" :is-saving="isSaving" @save="handleSaveGraph" />

    <main class="workspace-grid">
      <ProjectSidebar
        :groups="projectGroups"
        :selected-node-id="selectedNode.id"
        @select-node="selectNode"
      />
      <CanvasWorkspace
        :selected-node-id="selectedNode.id"
        :initial-nodes="graphNodes"
        :initial-edges="graphEdges"
        :graph-version="graphVersion"
        @node-selected="selectNode"
        @graph-changed="handleGraphChanged"
      />
      <AgentSidebar :current-node="selectedNode" />
    </main>

    <StatusBar :status="workspaceStatus" />
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: 56px minmax(0, 1fr) 30px;
  background: var(--app-bg);
  color: var(--text);
}

.workspace-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: 280px minmax(420px, 1fr) 340px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

@media (max-width: 1120px) {
  .workspace-grid {
    grid-template-columns: 240px minmax(360px, 1fr) 300px;
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
