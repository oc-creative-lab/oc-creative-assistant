<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  loadRagContext,
  searchProjectMemory,
  type IndexingStatusDto,
  type MemorySearchItemDto,
  type RagMergedContextItemDto,
} from '../../api/graphApi'
import type { CreativeFlowNode, CreativeNodeType } from '../../types/node'
import { nodeTypeOptions } from '../../utils/nodeFactory'

/**
 * 左侧项目栏。
 *
 * 本组件负责展示可创建的节点类型、项目记忆导航和轻量检索入口；graph 写入仍由
 * AppShell 统一处理，左侧只上抛创建和选中意图。
 */
const props = defineProps<{
  projectId: string
  nodes: CreativeFlowNode[]
  selectedNode: CreativeFlowNode | null
  indexingStatus?: IndexingStatusDto
}>()

const emit = defineEmits<{
  createNode: [nodeType: CreativeNodeType]
  nodeSelected: [nodeId: string]
}>()

type MemoryFilterType = CreativeNodeType | 'all'

const memorySearchQuery = ref('')
const memorySearchType = ref<MemoryFilterType>('all')
const memorySearchItems = ref<MemorySearchItemDto[]>([])
const memorySearchError = ref('')
const isMemorySearching = ref(false)
const isMemorySearchTypeSelectOpen = ref(false)
const relatedMemoryItems = ref<RagMergedContextItemDto[]>([])
const relatedMemoryError = ref('')
const isRelatedMemoryLoading = ref(false)

function closeAllSelects(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-select-container')) {
    isMemorySearchTypeSelectOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeAllSelects)
})

onUnmounted(() => {
  document.removeEventListener('click', closeAllSelects)
})


const memoryGroups = computed(() =>
  nodeTypeOptions
    .map((option) => ({
      ...option,
      nodes: props.nodes.filter((node) => node.data.nodeType === option.type),
    }))
    .filter((group) => group.nodes.length > 0),
)


/**
 * 截断节点正文，避免左侧记忆列表被长设定挤占。
 *
 * Args:
 *   content: 节点完整正文。
 *
 * Returns:
 *   用于卡片预览的短摘要。
 */
function summarizeContent(content: string) {
  if (!content.trim()) {
    return '暂无正文'
  }

  return content.length > 72 ? `${content.slice(0, 72)}...` : content
}

function getNodeTypeLabel(type: string) {
  return nodeTypeOptions.find((option) => option.type === type)?.label ?? type
}

function getMemorySourceLabel(source: string) {
  if (source === 'both') {
    return '图关系 + 语义'
  }

  return source === 'graph' ? '图关系' : '语义相似'
}

/**
 * 请求创建指定类型的节点。
 *
 * Args:
 *   nodeType: 用户在左侧工具栏选择的节点类型。
 */
function handleCreateNode(nodeType: CreativeNodeType) {
  emit('createNode', nodeType)
}

function handleSelectNode(nodeId: string) {
  emit('nodeSelected', nodeId)
}

/**
 * 加载当前选中节点的相关记忆。
 *
 * 左侧只展示合并后的简洁记忆卡片；完整 prompt 和向量调试信息继续留在右侧面板。
 */
async function handleLoadRelatedMemory() {
  if (!props.selectedNode) {
    return
  }

  try {
    isRelatedMemoryLoading.value = true
    relatedMemoryError.value = ''
    const result = await loadRagContext({
      node_id: props.selectedNode.id,
      query: '',
      agent_type: 'inspiration',
      top_k: 5,
    })

    relatedMemoryItems.value = result.merged_context
  } catch (error) {
    relatedMemoryItems.value = []
    relatedMemoryError.value = error instanceof Error ? error.message : '相关记忆加载失败'
  } finally {
    isRelatedMemoryLoading.value = false
  }
}

/**
 * 在项目级记忆中做语义搜索。
 *
 * 该入口不依赖当前节点，适合用户直接按问题查找已有 lore；索引错误只展示短提示。
 */
async function handleSearchMemory() {
  const query = memorySearchQuery.value.trim()

  if (!props.projectId || !query) {
    memorySearchError.value = '请输入要搜索的记忆问题'
    return
  }

  try {
    isMemorySearching.value = true
    memorySearchError.value = ''
    const result = await searchProjectMemory(props.projectId, {
      query,
      node_type: memorySearchType.value === 'all' ? null : memorySearchType.value,
      top_k: 6,
    })

    memorySearchItems.value = result.items
    if (result.debug.vector_error) {
      memorySearchError.value = result.debug.vector_error
    }
  } catch (error) {
    memorySearchItems.value = []
    memorySearchError.value = error instanceof Error ? error.message : '记忆搜索失败'
  } finally {
    isMemorySearching.value = false
  }
}

watch(
  () => props.selectedNode?.id,
  () => {
    relatedMemoryItems.value = []
    relatedMemoryError.value = ''
  },
)
</script>

<template>
  <!-- 左侧栏：负责节点类型、项目记忆导航和轻量检索入口 -->
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

    <!-- <section class="sidebar-section"> -->
      <!-- <div class="section-header">
        <h2>Lore Memory</h2>
        <span class="memory-health" :class="memoryHealth.tone">{{ memoryHealth.label }}</span>
      </div>
      <div class="memory-stats">
        <article v-for="stat in memoryStats" :key="stat.type" class="memory-stat">
          <span>{{ stat.icon }}</span>
          <strong>{{ stat.count }}</strong>
          <small>{{ stat.label }}</small>
        </article>
      </div> -->
    <!-- </section> -->

    <section class="sidebar-section">
      <h2>记忆列表</h2>
      <p v-if="memoryGroups.length === 0" class="empty-copy">还没有节点，先从上方创建一个创作记忆。</p>
      <details v-for="group in memoryGroups" :key="group.type" class="memory-group" open>
        <summary>
          <span>{{ group.icon }} {{ group.label }}</span>
          <small>{{ group.nodes.length }}</small>
        </summary>
        <button
          v-for="node in group.nodes"
          :key="node.id"
          type="button"
          class="memory-card"
          :class="{ 'is-active': selectedNode?.id === node.id }"
          @click="handleSelectNode(node.id)"
        >
          <strong>{{ node.data.title }}</strong>
          <span>{{ node.data.status }} · {{ node.data.tags.join(' / ') || '无标签' }}</span>
          <p>{{ summarizeContent(node.data.content) }}</p>
        </button>
      </details>
    </section>

    <section class="sidebar-section">
      <h2>当前相关记忆</h2>
      <template v-if="selectedNode">
        <p class="context-copy">围绕「{{ selectedNode.data.title }}」查看图关系和语义相似记忆。</p>
        <button type="button" class="secondary-button" :disabled="isRelatedMemoryLoading" @click="handleLoadRelatedMemory">
          {{ isRelatedMemoryLoading ? '加载中...' : '查看相关记忆' }}
        </button>
        <p v-if="relatedMemoryError" class="memory-error">{{ relatedMemoryError }}</p>
        <p v-else-if="relatedMemoryItems.length === 0" class="empty-copy">点击按钮后展示与当前节点相关的记忆。</p>
        <button
          v-for="item in relatedMemoryItems"
          :key="item.id"
          type="button"
          class="memory-card compact"
          @click="handleSelectNode(item.id)"
        >
          <strong>{{ item.title }}</strong>
          <span>{{ getMemorySourceLabel(item.source) }} · {{ getNodeTypeLabel(item.type) }}</span>
          <p>{{ summarizeContent(item.content) }}</p>
        </button>
      </template>
      <p v-else class="empty-copy">选择一个节点后，这里会显示相关记忆。</p>
    </section>

    <section class="sidebar-section">
      <h2>项目记忆搜索</h2>
      <div class="memory-search">
        <input
          v-model="memorySearchQuery"
          type="text"
          placeholder="例如：谁和涉谷站线有关？"
          @keydown.enter.prevent="handleSearchMemory"
        />
        <div class="custom-select-container">
          <div
            class="custom-select-trigger"
            :class="{ 'is-open': isMemorySearchTypeSelectOpen }"
            @click="isMemorySearchTypeSelectOpen = !isMemorySearchTypeSelectOpen"
          >
            <span>{{ memorySearchType === 'all' ? '全部类型' : (nodeTypeOptions.find(opt => opt.type === memorySearchType)?.label || memorySearchType) }}</span>
            <div class="custom-select-arrow"></div>
          </div>
          <ul class="custom-select-options" v-show="isMemorySearchTypeSelectOpen">
            <li
              class="custom-select-option"
              :class="{ 'is-selected': memorySearchType === 'all' }"
              @click="memorySearchType = 'all'; isMemorySearchTypeSelectOpen = false"
            >
              全部类型
            </li>
            <li
              v-for="option in nodeTypeOptions"
              :key="option.type"
              class="custom-select-option"
              :class="{ 'is-selected': memorySearchType === option.type }"
              @click="memorySearchType = option.type; isMemorySearchTypeSelectOpen = false"
            >
              {{ option.label }}
            </li>
          </ul>
        </div>
        <button type="button" :disabled="isMemorySearching" @click="handleSearchMemory">
          {{ isMemorySearching ? '搜索中...' : '搜索记忆' }}
        </button>
      </div>
      <p v-if="memorySearchError" class="memory-error">{{ memorySearchError }}</p>
      <p v-else-if="memorySearchItems.length === 0" class="empty-copy">输入问题后，在当前项目内检索已有 lore。</p>
      <button
        v-for="item in memorySearchItems"
        :key="item.id"
        type="button"
        class="memory-card compact"
        @click="handleSelectNode(item.id)"
      >
        <strong>{{ item.title }}</strong>
        <span>score {{ item.score.toFixed(2) }} · {{ getNodeTypeLabel(item.type) }}</span>
        <p>{{ summarizeContent(item.content) }}</p>
      </button>
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.section-header h2 {
  margin-bottom: 0;
}

.memory-health {
  flex: 0 0 auto;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--panel-strong);
  color: var(--muted);
  font-size: 0.72rem;
  font-weight: 500;
}

.memory-health.ready {
  background: #ecfdf5;
  color: #047857;
}

.memory-health.warning {
  background: #fffbeb;
  color: #b45309;
}

.memory-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.memory-stat {
  min-width: 0;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 2px 8px;
  align-items: center;
  padding: 10px;
  border-radius: 8px;
  background: var(--panel-strong);
}

.memory-stat strong {
  color: var(--text);
  font-size: 1rem;
}

.memory-stat small {
  grid-column: 2;
  color: var(--muted);
  font-size: 0.72rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.memory-group {
  border-radius: 10px;
  background: var(--panel-strong);
  overflow: hidden;
}

.memory-group + .memory-group {
  margin-top: 8px;
}

.memory-group summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  color: var(--text);
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 600;
}

.memory-group summary small {
  color: var(--muted);
}

.memory-card {
  width: calc(100% - 16px);
  display: block;
  margin: 0 8px 8px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.memory-card:hover,
.memory-card.is-active {
  border-color: var(--accent-border);
  background: var(--app-bg);
}

.memory-card.compact {
  width: 100%;
  margin: 8px 0 0;
}

.memory-card strong,
.memory-card span,
.memory-card p {
  display: block;
}

.memory-card strong {
  font-size: 0.86rem;
  line-height: 1.3;
}

.memory-card span {
  margin-top: 3px;
  color: var(--muted);
  font-size: 0.72rem;
}

.memory-card p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.45;
}

.context-copy,
.empty-copy,
.memory-error {
  margin: 0 0 10px;
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.5;
}

.memory-error {
  color: #b45309;
}

.secondary-button,
.memory-search button {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--accent-border);
  border-radius: 8px;
  background: var(--panel-strong);
  color: var(--accent);
  cursor: pointer;
}

.secondary-button:disabled,
.memory-search button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.memory-search {
  display: grid;
  gap: 8px;
}

.memory-search input {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-strong);
  color: var(--text);
  font-size: 0.82rem;
}

/* 自定义下拉框组件样式 (与右侧边栏一致) */
.custom-select-container {
  position: relative;
  width: 100%;
  user-select: none;
}

.custom-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 36px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background-color: var(--panel-strong);
  color: var(--text);
  font-size: 0.82rem;
  line-height: 1.5;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.custom-select-trigger:hover {
  border-color: var(--accent-border);
}

.custom-select-trigger.is-open {
  border-color: var(--accent);
  background-color: #ffffff;
  box-shadow: 0 0 0 3px var(--accent-soft), 0 1px 2px rgba(0, 0, 0, 0.02);
}

.custom-select-arrow {
  width: 10px;
  height: 6px;
  background-color: var(--muted);
  clip-path: polygon(100% 0%, 0 0%, 50% 100%);
  transition: transform 0.2s ease;
}

.custom-select-trigger.is-open .custom-select-arrow {
  transform: rotate(180deg);
}

.custom-select-options {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 100;
  max-height: 240px;
  overflow-y: auto;
  margin: 0;
  padding: 6px;
  list-style: none;
  background-color: #ffffff;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08), 0 2px 4px rgba(0, 0, 0, 0.04);
  animation: dropdownFadeIn 0.15s ease-out forwards;
}

@keyframes dropdownFadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.custom-select-option {
  padding: 8px 12px;
  border-radius: 6px;
  color: var(--text);
  font-size: 0.82rem;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.custom-select-option:hover {
  background-color: var(--app-bg);
}

.custom-select-option.is-selected {
  background-color: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

@media (max-width: 920px) {
  .project-sidebar {
    max-height: 420px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
}
</style>
