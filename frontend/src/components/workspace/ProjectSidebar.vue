<script setup lang="ts">
import { computed } from 'vue'
import type { CreativeFlowNode, CreativeNodeType } from '../../types/node'
import { nodeTypeOptions } from '../../utils/nodeFactory'

const props = defineProps<{
  projectName: string
  saveState: string
  nodes: CreativeFlowNode[]
}>()

const emit = defineEmits<{
  createNode: [nodeType: CreativeNodeType]
}>()

const loreCounts = computed(() => ({
  worldbuilding: props.nodes.filter((node) => node.data.nodeType === 'worldbuilding').length,
  characters: props.nodes.filter((node) => node.data.nodeType === 'character').length,
  plot: props.nodes.filter((node) => node.data.nodeType === 'plot').length,
}))

function handleCreateNode(nodeType: CreativeNodeType) {
  // PoC 阶段左侧只负责创建本地节点入口，不触发 Agent、RAG 或后端 LLM 调用。
  emit('createNode', nodeType)
}
</script>

<template>
  <aside class="project-sidebar">
    <header class="sidebar-header">
      <strong>OC Creative Assistant</strong>
    </header>

    <section class="sidebar-section">
      <h2>当前项目</h2>
      <dl class="project-meta">
        <div>
          <dt>项目名称</dt>
          <dd>{{ projectName }}</dd>
        </div>
        <div>
          <dt>保存状态</dt>
          <dd>{{ saveState }}</dd>
        </div>
      </dl>
    </section>

    <section class="sidebar-section">
      <h2>节点类型</h2>
      <div class="node-type-list">
        <button
          v-for="option in nodeTypeOptions"
          :key="option.type"
          type="button"
          class="node-type-button"
          @click="handleCreateNode(option.type)"
        >
          <span class="node-icon">{{ option.icon }}</span>
          <span>
            <strong>{{ option.label }}</strong>
            <small>{{ option.description }}</small>
          </span>
        </button>
      </div>
    </section>

    <section class="sidebar-section">
      <h2>Lore Memory 占位</h2>
      <ul class="memory-list">
        <li>Worldbuilding: {{ loreCounts.worldbuilding }} items</li>
        <li>Characters: {{ loreCounts.characters }} items</li>
        <li>Plot: {{ loreCounts.plot }} items</li>
        <li>Status: 未接入 RAG</li>
      </ul>
    </section>

    <section class="sidebar-section">
      <h2>筛选占位</h2>
      <label><input type="checkbox" disabled /> 只看角色</label>
      <label><input type="checkbox" disabled /> 只看剧情</label>
      <label><input type="checkbox" disabled /> 只看世界观</label>
    </section>
  </aside>
</template>

<style scoped>
.project-sidebar {
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  border-right: 1px solid var(--border);
  background: var(--panel);
}

.sidebar-header,
.sidebar-section {
  padding: 16px;
  border-bottom: 1px solid var(--border);
}

.sidebar-header strong {
  font-size: 1rem;
}

h2 {
  margin: 0 0 10px;
  color: var(--text);
  font-size: 0.9rem;
}

.project-meta {
  display: grid;
  gap: 10px;
  margin: 0;
}

.project-meta div {
  display: grid;
  gap: 4px;
}

dt {
  color: var(--muted);
  font-size: 0.76rem;
}

dd {
  margin: 0;
  color: var(--text);
  font-size: 0.88rem;
}

.node-type-list {
  display: grid;
  gap: 8px;
}

.node-type-button {
  width: 100%;
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel-strong);
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.node-type-button:hover {
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

.node-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--panel);
}

.node-type-button strong,
.node-type-button small {
  display: block;
}

.node-type-button small {
  margin-top: 2px;
  color: var(--muted);
  font-size: 0.75rem;
  line-height: 1.35;
}

.memory-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  color: var(--muted);
  font-size: 0.84rem;
  list-style: none;
}

label {
  display: block;
  color: var(--muted);
  font-size: 0.84rem;
}

label + label {
  margin-top: 8px;
}

@media (max-width: 920px) {
  .project-sidebar {
    max-height: 420px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
}
</style>
