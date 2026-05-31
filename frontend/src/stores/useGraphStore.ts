import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { GraphEdgeDto, GraphNodeDto } from '../api/graphApi'
import { loadSubgraph } from '../api/graphApi'

/**
 * 当前打开的 sub-graph store（first_revision 决策 6 / 阶段 3）。
 *
 * 主要服务角色卡两路由（CharacterCardList ↔ CharacterCardDetail）共享同一份
 * sub-graph 数据，避免详情页二次全量拉取。Plot/World 画布走 useGraphPersistence
 * 的注入式加载，不依赖本 store。
 */
export const useGraphStore = defineStore('graph', () => {
  const graphId = ref('')
  const nodes = ref<GraphNodeDto[]>([])
  const edges = ref<GraphEdgeDto[]>([])
  const isLoading = ref(false)
  const error = ref('')

  /** 按 graph_id 加载 sub-graph；已是当前 graph 时可强制刷新。 */
  async function load(targetGraphId: string, force = false): Promise<void> {
    if (!force && graphId.value === targetGraphId && nodes.value.length > 0) return
    isLoading.value = true
    error.value = ''
    try {
      const graph = await loadSubgraph(targetGraphId)
      graphId.value = targetGraphId
      nodes.value = graph.nodes
      edges.value = graph.edges
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'sub-graph 加载失败'
      nodes.value = []
      edges.value = []
    } finally {
      isLoading.value = false
    }
  }

  /** 取单个节点（详情页用）。 */
  function getNode(nodeId: string): GraphNodeDto | undefined {
    return nodes.value.find((node) => node.id === nodeId)
  }

  /** 取某节点的出边（角色关系，以标签形式展示，不画线）。 */
  function outgoingEdges(nodeId: string): GraphEdgeDto[] {
    return edges.value.filter((edge) => edge.source === nodeId)
  }

  return { graphId, nodes, edges, isLoading, error, load, getNode, outgoingEdges }
})
