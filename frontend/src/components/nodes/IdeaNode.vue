<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { CreativeNodeData } from '../../types/node'
import NodeHandles from './NodeHandles.vue'

/**
 * 灵感节点卡片。
 *
 * 灵感节点用于承接零散脑洞；画布上只展示摘要，完整内容由右侧详情面板编辑。
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
