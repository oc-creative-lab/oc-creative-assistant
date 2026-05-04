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

<style scoped>
.creative-node {
  width: 250px;
  padding: 12px;
  border: 1px solid #d4dae5;
  border-left: 4px solid #475467;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(31, 41, 51, 0.1);
}

.creative-node.selected {
  border-color: #475467;
  box-shadow: 0 0 0 2px rgba(71, 84, 103, 0.18), 0 14px 28px rgba(31, 41, 51, 0.14);
}

.node-type,
h3,
.node-summary {
  margin: 0;
}

.node-type {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #475467;
  font-size: 0.74rem;
  font-weight: 800;
}

h3 {
  margin-top: 6px;
  color: #1f2933;
  font-size: 1rem;
}

.node-summary {
  display: -webkit-box;
  margin-top: 8px;
  overflow: hidden;
  color: #667085;
  font-size: 0.82rem;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
</style>
