import { inject, provide, ref, type InjectionKey, type Ref } from 'vue'

export const WORKSPACE_SELECTED_NODE_IDS_KEY: InjectionKey<Ref<string[]>> = Symbol(
  'workspaceSelectedNodeIds',
)

type GraphRefreshRegistry = {
  register: (fn: () => void | Promise<void>) => void
  trigger: () => Promise<void>
}

export const WORKSPACE_GRAPH_REFRESH_KEY: InjectionKey<GraphRefreshRegistry> = Symbol(
  'workspaceGraphRefresh',
)

type GraphSaveRegistry = {
  register: (fn: () => void | Promise<void>) => void
  trigger: () => Promise<void>
  isSaving: Ref<boolean>
}

export const WORKSPACE_GRAPH_SAVE_KEY: InjectionKey<GraphSaveRegistry> = Symbol(
  'workspaceGraphSave',
)

/** WorkspaceShell 提供：FloatingChatDock 读取选中节点、触发画布刷新。 */
export function provideWorkspaceChatContext() {
  const selectedNodeIds = ref<string[]>([])
  let refreshFn: (() => void | Promise<void>) | null = null

  const graphRefreshRegistry: GraphRefreshRegistry = {
    register(fn) {
      refreshFn = fn
    },
    async trigger() {
      if (refreshFn) {
        await refreshFn()
      }
    },
  }

  let saveFn: (() => void | Promise<void>) | null = null
  const isSaving = ref(false)
  const graphSaveRegistry: GraphSaveRegistry = {
    register(fn) {
      saveFn = fn
    },
    async trigger() {
      if (saveFn) await saveFn()
    },
    isSaving,
  }
  provide(WORKSPACE_GRAPH_SAVE_KEY, graphSaveRegistry)
  provide(WORKSPACE_SELECTED_NODE_IDS_KEY, selectedNodeIds)
  provide(WORKSPACE_GRAPH_REFRESH_KEY, graphRefreshRegistry)

  return {
    selectedNodeIds,
    triggerGraphRefresh: () => graphRefreshRegistry.trigger(),
    triggerGraphSave: () => graphSaveRegistry.trigger(),
    isSaving,
  }
}

export function injectWorkspaceSelectedNodeIds() {
  return inject(WORKSPACE_SELECTED_NODE_IDS_KEY, ref<string[]>([]))
}

export function injectWorkspaceGraphRefresh() {
  return inject(WORKSPACE_GRAPH_REFRESH_KEY, null)
}

export function injectWorkspaceGraphSave() {
  return inject(WORKSPACE_GRAPH_SAVE_KEY, null)
}