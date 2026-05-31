<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { CreativeNodeData } from '../../types/node'
import NodeHandles from './NodeHandles.vue'

/**
 * 结构整理节点卡片。
 *
 * 结构节点用于把多个素材整理成角色卡、关系摘要或剧情框架；当前只负责画布展示。
 */
defineProps<NodeProps<CreativeNodeData>>()
</script>

<template>
  <article class="creative-node structure" :class="{ selected: selected || data.isActive }">
    <NodeHandles :connectable="connectable" />
    <p class="node-type"><span>{{ data.icon }}</span>{{ data.typeLabel }}</p>
    <h3>{{ data.title }}</h3>
    <p class="node-summary">{{ data.content }}</p>
  </article>
</template>
