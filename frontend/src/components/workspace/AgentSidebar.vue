<script setup lang="ts">
import type { CreativeFlowEdge, CreativeFlowNode } from '../../types/node'
import EdgeDetailPanel from './EdgeDetailPanel.vue'
import NodeDetailPanel from './NodeDetailPanel.vue'

/**
 * 右侧详情面板的薄路由容器。
 *
 * 选中节点时挂载 NodeDetailPanel; 选中连线时挂载 EdgeDetailPanel; 否则
 * 显示空状态。所有编辑事件原样上抛, 真正的落库由上层 AppShell 处理。
 */
defineProps<{
  selectedNode: CreativeFlowNode | null
  selectedEdge: CreativeFlowEdge | null
  nodes: CreativeFlowNode[]
}>()

defineEmits<{
  nodeUpdated: [node: CreativeFlowNode]
  nodeDeleted: [nodeId: string]
  edgeUpdated: [edge: CreativeFlowEdge]
  edgeDeleted: [edgeId: string]
}>()
</script>

<template>
  <aside class="detail-sidebar">
    <NodeDetailPanel
      v-if="selectedNode"
      :selected-node="selectedNode"
      @node-updated="(node) => $emit('nodeUpdated', node)"
      @node-deleted="(id) => $emit('nodeDeleted', id)"
    />

    <EdgeDetailPanel
      v-else-if="selectedEdge"
      :selected-edge="selectedEdge"
      :nodes="nodes"
      @edge-updated="(edge) => $emit('edgeUpdated', edge)"
      @edge-deleted="(id) => $emit('edgeDeleted', id)"
    />

    <section v-else class="empty-state">
      <p>未选择对象</p>
      <span>选择一个节点编辑内容，或选择一条连线编辑关系标签。</span>
    </section>
  </aside>
</template>

<style scoped src="./AgentSidebar.scoped.css"></style>