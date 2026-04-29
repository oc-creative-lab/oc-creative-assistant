<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import type { NodeProps } from '@vue-flow/core'
import type { CreativeNodeData } from '../../types/node'

// 资料节点是 RAG 的前端入口占位，当前只保存摘要和来源说明。
defineProps<NodeProps<CreativeNodeData>>()
</script>

<template>
  <article class="creative-node research" :class="{ selected: selected || data.isActive }">
    <Handle type="target" :position="Position.Left" :connectable="connectable" />
    <p class="node-type"><span>{{ data.icon }}</span>{{ data.typeLabel }}</p>
    <h3>{{ data.title }}</h3>
    <p class="node-summary">{{ data.content }}</p>
    <Handle type="source" :position="Position.Right" :connectable="connectable" />
  </article>
</template>

<style scoped>
.creative-node {
  width: 240px;
  padding: 12px;
  border: 1px solid #d4dae5;
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(31, 41, 51, 0.1);
}

.creative-node.selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18), 0 14px 28px rgba(31, 41, 51, 0.14);
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
  color: #2563eb;
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
