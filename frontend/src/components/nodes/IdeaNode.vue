<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { CreativeNodeData } from '../../types/node'
import NodeHandles from './NodeHandles.vue'

/**
 * Idea node card.
 *
 * Idea nodes capture scattered brainstorms; the canvas only shows a summary, while the full content is edited in the right-side detail panel.
 */
defineProps<NodeProps<CreativeNodeData>>()
</script>

<template>
  <article class="creative-node idea" :class="{ selected: selected || data.isActive }">
    <NodeHandles :connectable="connectable" />
    <p class="node-type"><span>{{ data.icon }}</span>{{ data.typeLabel }}</p>
    <h3>{{ data.title }}</h3>
    <p class="node-summary">{{ data.content }}</p>
  </article>
</template>
