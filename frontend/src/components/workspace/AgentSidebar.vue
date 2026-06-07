<script setup lang="ts">
import type { CreativeFlowEdge, CreativeFlowNode } from '../../types/node'
import EdgeDetailPanel from './EdgeDetailPanel.vue'
import NodeDetailPanel from './NodeDetailPanel.vue'

/**
 * Thin routing container for the right-hand detail panel.
 *
 * Mounts NodeDetailPanel when a node is selected; EdgeDetailPanel when an edge
 * is selected; otherwise shows an empty state. All edit events are re-emitted
 * as-is, and the actual persistence is handled by the parent AppShell.
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
      <p>Nothing selected</p>
      <span>Select a node to edit its content, or select an edge to edit its relation label.</span>
    </section>
  </aside>
</template>

<style scoped src="./AgentSidebar.scoped.css"></style>