<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { NodeProps } from '@vue-flow/core'
import type { CreativeNodeData } from '../../types/node'

defineProps<NodeProps<CreativeNodeData>>()
</script>

<template>
  <article class="creative-node plot" :class="{ selected: selected || data.isActive }">
    <Handle type="target" :position="Position.Left" :connectable="connectable" />
    <p class="node-type">{{ data.typeLabel }}</p>
    <h3>{{ data.title }}</h3>
    <p class="node-summary">{{ data.summary }}</p>
    <Handle type="source" :position="Position.Right" :connectable="connectable" />
  </article>
</template>

<style scoped>
.creative-node {
  width: 250px;
  padding: 12px;
  border: 1px solid #d4dae5;
  border-left: 4px solid #b45309;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(31, 41, 51, 0.1);
}

.creative-node.selected {
  border-color: #b45309;
  box-shadow: 0 0 0 2px rgba(180, 83, 9, 0.18), 0 14px 28px rgba(31, 41, 51, 0.14);
}

.node-type,
h3,
.node-summary {
  margin: 0;
}

.node-type {
  color: #b45309;
  font-size: 0.74rem;
  font-weight: 800;
}

h3 {
  margin-top: 6px;
  color: #1f2933;
  font-size: 1rem;
}

.node-summary {
  margin-top: 8px;
  color: #667085;
  font-size: 0.82rem;
  line-height: 1.45;
}
</style>
