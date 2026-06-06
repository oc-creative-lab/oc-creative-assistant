<script setup lang="ts">
import { inject } from 'vue'
import type { NodeProps } from '@vue-flow/core'
import type { CreativeNodeData } from '../../types/node'
import NodeHandles from './NodeHandles.vue'
import InlineEditableText from '../canvas/InlineEditableText.vue'

/**
 * 角色节点卡片。
 *
 * 标题与简介支持 inline edit（second_revision 改点 A），保存时通过 CanvasWorkspace
 * provide 的 updateNodeData 写回并触发自动保存；无需切右栏。
 */
const props = defineProps<NodeProps<CreativeNodeData>>()
const updateNodeData = inject<(id: string, patch: { title?: string; content?: string }) => void>(
  'updateNodeData',
)
</script>

<template>
  <article class="creative-node character" :class="{ selected: selected || data.isActive }">
    <NodeHandles :connectable="connectable" />
    <p class="node-type"><span>{{ data.icon }}</span>{{ data.typeLabel }}</p>
    <h3>
      <InlineEditableText
        :model-value="data.title"
        placeholder="Untitled character"
        @save="(v) => updateNodeData?.(props.id, { title: v })"
      />
    </h3>
    <p class="node-summary">
      <InlineEditableText
        :model-value="data.content"
        placeholder="Add a short summary"
        multiline
        @save="(v) => updateNodeData?.(props.id, { content: v })"
      />
    </p>
  </article>
</template>

<style scoped>
.creative-node {
  width: 184px;
  padding: 10px 12px;
  border: 1px solid #d4dae5;
  border-left: 4px solid #2764c5;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(31, 41, 51, 0.1);
}

.creative-node.selected {
  border-color: #2764c5;
  box-shadow: 0 0 0 2px rgba(39, 100, 197, 0.18), 0 14px 28px rgba(31, 41, 51, 0.14);
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
  color: #2764c5;
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
  line-clamp: 3;
}
</style>
