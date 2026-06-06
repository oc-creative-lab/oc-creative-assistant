import type { Ref } from 'vue'
import type { CreativeFlowEdge, CreativeFlowNode, CreativeGraphSnapshot } from '../types/node'

const FORM_AUTO_SAVE_DELAY_MS = 3000
const QUICK_AUTO_SAVE_DELAY_MS = 300

interface Options {
  graphSnapshot: Ref<CreativeGraphSnapshot>
  selectedNodeId: Ref<string>
  selectedEdgeId: Ref<string>
  setGraphSnapshot: (snapshot: CreativeGraphSnapshot, shouldPushToCanvas?: boolean) => void
  scheduleAutoSave: (delayMs?: number) => void
}

/**
 * 集中右侧详情面板与键盘快捷键触发的 graph 变更。
 *
 * 所有变更经 setGraphSnapshot 进主流程, 触发统一的防抖自动保存; 删除节点
 * 时同步移除相关连线, 与后端 ondelete=CASCADE 行为对齐。键盘快捷键在输入
 * 控件内保留默认文本编辑语义。
 */
export function useGraphMutations(options: Options) {
  const { graphSnapshot, selectedNodeId, selectedEdgeId, setGraphSnapshot, scheduleAutoSave } = options

  function handleNodeUpdated(updatedNode: CreativeFlowNode) {
    const nextSnapshot: CreativeGraphSnapshot = {
      nodes: graphSnapshot.value.nodes.map((node) => (node.id === updatedNode.id ? updatedNode : node)),
      edges: graphSnapshot.value.edges,
    }
    setGraphSnapshot(nextSnapshot, true)
    scheduleAutoSave(FORM_AUTO_SAVE_DELAY_MS)
  }

  function handleEdgeUpdated(updatedEdge: CreativeFlowEdge) {
    const nextSnapshot: CreativeGraphSnapshot = {
      nodes: graphSnapshot.value.nodes,
      edges: graphSnapshot.value.edges.map((edge) => (edge.id === updatedEdge.id ? updatedEdge : edge)),
    }
    setGraphSnapshot(nextSnapshot, true)
    scheduleAutoSave(FORM_AUTO_SAVE_DELAY_MS)
  }

  function handleNodeDeleted(nodeId: string) {
    const node = graphSnapshot.value.nodes.find((item) => item.id === nodeId)
    if (!node) {
      return
    }
    const confirmed = window.confirm(`Delete node "${node.data.title}"? Connected edges will be removed too.`)
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
    scheduleAutoSave(QUICK_AUTO_SAVE_DELAY_MS)
  }

  function handleEdgeDeleted(edgeId: string) {
    const nextSnapshot: CreativeGraphSnapshot = {
      nodes: graphSnapshot.value.nodes,
      edges: graphSnapshot.value.edges.filter((edge) => edge.id !== edgeId),
    }
    selectedEdgeId.value = ''
    setGraphSnapshot(nextSnapshot, true)
    scheduleAutoSave(QUICK_AUTO_SAVE_DELAY_MS)
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

  return {
    handleNodeUpdated,
    handleEdgeUpdated,
    handleNodeDeleted,
    handleEdgeDeleted,
    handleGlobalKeydown,
  }
}