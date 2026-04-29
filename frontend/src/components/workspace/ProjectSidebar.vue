<script setup lang="ts">
import { computed } from 'vue'
import type { CreativeFlowNode, CreativeNodeType } from '../../types/node'
import { nodeTypeOptions } from '../../utils/nodeFactory'

const props = defineProps<{
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
  <!-- 左侧栏：负责节点类型和创作资源 -->
  <aside class="project-sidebar">
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
        <li>
          <span class="memory-label">Worldbuilding</span>
          <span class="memory-value">{{ loreCounts.worldbuilding }}</span>
        </li>
        <li>
          <span class="memory-label">Characters</span>
          <span class="memory-value">{{ loreCounts.characters }}</span>
        </li>
        <li>
          <span class="memory-label">Plot</span>
          <span class="memory-value">{{ loreCounts.plot }}</span>
        </li>
        <li class="status-item">
          <span class="status-dot"></span>
          未接入 RAG
        </li>
      </ul>
    </section>

    <section class="sidebar-section">
      <h2>视图筛选</h2>
      <div class="filter-list">
        <label class="filter-item">
          <input type="checkbox" disabled />
          只看角色
        </label>
        <label class="filter-item">
          <input type="checkbox" disabled />
          只看剧情
        </label>
        <label class="filter-item">
          <input type="checkbox" disabled />
          只看世界观
        </label>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.project-sidebar {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  border-right: 1px solid var(--border);
  background: var(--panel);
}

/* 自定义滚动条样式 */
.project-sidebar::-webkit-scrollbar {
  width: 6px;
}

.project-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.project-sidebar::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.4);
  border-radius: 4px;
}

.project-sidebar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.7);
}

.sidebar-section {
  padding: 20px;
  border-bottom: 1px solid var(--border);
}

h2 {
  margin: 0 0 14px;
  color: var(--text);
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.node-type-list {
  display: grid;
  gap: 8px;
}

.node-type-button {
  width: 100%;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-strong);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

.node-type-button:hover {
  border-color: var(--accent-border);
  background: var(--app-bg);
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.04);
}

.node-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--panel);
  font-size: 1.1rem;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.1);
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
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.memory-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--panel-strong);
  font-size: 0.85rem;
  transition: background-color 0.2s ease;
}

.memory-list li:hover:not(.status-item) {
  background: var(--app-bg);
}

.memory-label {
  color: var(--text);
  font-weight: 500;
}

.memory-value {
  background: var(--panel);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  color: var(--muted);
  font-weight: 600;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.04);
}

.status-item {
  justify-content: flex-start !important;
  gap: 8px;
  color: var(--muted);
  background: transparent !important;
  padding-left: 4px !important;
  margin-top: 4px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted);
  opacity: 0.5;
}

.filter-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-size: 0.85rem;
  cursor: not-allowed;
  opacity: 0.7;
}

.filter-item input {
  margin: 0;
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
  cursor: not-allowed;
}

@media (max-width: 920px) {
  .project-sidebar {
    max-height: 420px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
}
</style>
