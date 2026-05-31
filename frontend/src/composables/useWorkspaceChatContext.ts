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

  provide(WORKSPACE_SELECTED_NODE_IDS_KEY, selectedNodeIds)
  provide(WORKSPACE_GRAPH_REFRESH_KEY, graphRefreshRegistry)

  return {
    selectedNodeIds,
    triggerGraphRefresh: () => graphRefreshRegistry.trigger(),
  }
}

export function injectWorkspaceSelectedNodeIds() {
  return inject(WORKSPACE_SELECTED_NODE_IDS_KEY, ref<string[]>([]))
}

export function injectWorkspaceGraphRefresh() {
  return inject(WORKSPACE_GRAPH_REFRESH_KEY, null)
}
