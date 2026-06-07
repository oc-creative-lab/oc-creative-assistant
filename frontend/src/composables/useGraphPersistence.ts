import { ref } from 'vue'
import type { GraphDto, IndexingStatusDto, SaveGraphDto } from '../api/graphApi'
import { loadDefaultGraph, saveProjectGraph } from '../api/graphApi'
import type { CreativeFlowEdge, CreativeFlowNode, CreativeGraphSnapshot } from '../types/node'
import { graphDtoToSnapshot, snapshotToSaveDto } from '../utils/graphTransform'

const CANVAS_AUTO_SAVE_DELAY_MS = 1000

/**
 * Injectable load / save strategy (first_revision phase 3).
 *
 * By default it uses the default-project dimension (AppShell's original single-canvas behavior); the three workspace views
 * inject loadSubgraph / saveSubgraph at the sub-graph dimension, thereby reusing this composable's snapshot + debounced save logic.
 */
export interface GraphPersistenceLoaders {
  load: () => Promise<GraphDto>
  save: (dto: SaveGraphDto) => Promise<GraphDto>
}

/**
 * Maintains the load / save / auto-save semantics of the workspace graph.
 *
 * Every entry that actually mutates graphSnapshot goes through setGraphSnapshot; auto-save uses a single debounce
 * queue to avoid concurrent overwrites. After staging is accepted, clearAutoSave is called to drop stale pending snapshots,
 * preventing an old snapshot from overwriting the new nodes / new edges the backend just persisted.
 */
export function useGraphPersistence(
  applyIndexingStatus: (indexing?: IndexingStatusDto) => void,
  loaders?: GraphPersistenceLoaders,
) {
  const projectId = ref('')
  const projectName = ref('Loading project…')
  const graphSnapshot = ref<CreativeGraphSnapshot>({ nodes: [], edges: [] })
  const graphNodes = ref<CreativeFlowNode[]>([])
  const graphEdges = ref<CreativeFlowEdge[]>([])
  const graphVersion = ref(0)
  const isGraphReady = ref(false)
  const isSaving = ref(false)
  const saveState = ref('Loading…')

  let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

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
      saveState.value = 'Saving…'
      const saveDto = snapshotToSaveDto(graphSnapshot.value)
      const savedGraph = loaders
        ? await loaders.save(saveDto)
        : await saveProjectGraph(projectId.value, saveDto)
      if (refreshFromResponse) {
        setGraphSnapshot(graphDtoToSnapshot(savedGraph), true)
      }
      applyIndexingStatus(savedGraph.indexing)
      saveState.value = `Saved · ${new Date().toLocaleTimeString()}`
    } catch (error) {
      saveState.value = error instanceof Error ? `Save failed: ${error.message}` : 'Save failed'
    } finally {
      isSaving.value = false
    }
  }

  function scheduleAutoSave(delayMs = CANVAS_AUTO_SAVE_DELAY_MS) {
    if (!isGraphReady.value || !projectId.value) {
      return
    }
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer)
    }
    saveState.value = 'Unsaved changes'
    autoSaveTimer = setTimeout(() => {
      void persistGraph(false)
    }, delayMs)
  }

  function clearAutoSave() {
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer)
      autoSaveTimer = null
    }
  }

  async function loadGraph(): Promise<{ initialNodeId: string }> {
    try {
      saveState.value = 'Loading…'
      const graph = loaders ? await loaders.load() : await loadDefaultGraph()
      const snapshot = graphDtoToSnapshot(graph)
      projectId.value = graph.project.id
      projectName.value = graph.project.name
      setGraphSnapshot(snapshot, true)
      isGraphReady.value = true
      saveState.value = 'Loaded'
      applyIndexingStatus(graph.indexing)
      return { initialNodeId: snapshot.nodes[0]?.id ?? '' }
    } catch (error) {
      isGraphReady.value = false
      saveState.value =
        error instanceof Error ? `Load failed: ${error.message}` : 'Load failed'
      return { initialNodeId: '' }
    }
  }

  function handleGraphChanged(snapshot: CreativeGraphSnapshot) {
    setGraphSnapshot(snapshot)
    scheduleAutoSave(CANVAS_AUTO_SAVE_DELAY_MS)
  }

  async function handleSaveGraph() {
    clearAutoSave()
    await persistGraph(true)
  }

  return {
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
  }
}