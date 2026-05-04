<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { HandleConnectable } from '@vue-flow/core'

defineProps<{
  connectable: HandleConnectable
}>()

const handlePositions = [
  { id: 'top', position: Position.Top },
  { id: 'right', position: Position.Right },
  { id: 'bottom', position: Position.Bottom },
  { id: 'left', position: Position.Left },
]
</script>

<template>
  <!-- Loose 连接模式下，一个端点既能发起连线，也能作为连线落点。 -->
  <Handle
    v-for="handle in handlePositions"
    :id="handle.id"
    :key="handle.id"
    type="source"
    :position="handle.position"
    :connectable="connectable"
    :connectable-start="true"
    :connectable-end="true"
    :class="['node-handle', `node-handle--${handle.id}`, 'nodrag', 'nopan']"
  />
</template>

<style scoped>
.node-handle {
  width: 10px;
  height: 10px;
  border: 2px solid #ffffff;
  background: #667085;
  opacity: 0.72;
  transition:
    background-color 140ms ease,
    opacity 140ms ease,
    transform 140ms ease;
}

.node-handle:hover {
  background: var(--accent);
  opacity: 1;
  transform: scale(1.22);
}
</style>
