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
    return 'No content'
  }

  return content.length > 72 ? `${content.slice(0, 72)}...` : content
}

function getNodeTypeLabel(type: string) {
  return nodeTypeOptions.find((option) => option.type === type)?.label ?? type
}

function getMemorySourceLabel(source: string) {
  if (source === 'both') {
    return 'Graph + Semantic'
  }

  return source === 'graph' ? 'Graph' : 'Semantic similarity'
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
    relatedMemoryError.value = error instanceof Error ? error.message : 'Failed to load related memory'
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
    memorySearchError.value = 'Please enter the memory question to search'
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
    memorySearchError.value = error instanceof Error ? error.message : 'Failed to search memory'
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
      <h2>Node types</h2>
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
      <h2>Memory list</h2>
      <p v-if="memoryGroups.length === 0" class="empty-copy">No nodes yet, create a creative memory first from above.</p>
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
          <span>{{ node.data.status }} · {{ node.data.tags.join(' / ') || 'No tags' }}</span>
          <p>{{ summarizeContent(node.data.content) }}</p>
        </button>
      </details>
    </section>

    <section class="sidebar-section">
      <h2>Current related memory</h2>
      <template v-if="selectedNode">
        <p class="context-copy">View graph relations and semantic similar memories around "{{ selectedNode.data.title }}".</p>
        <button type="button" class="secondary-button" :disabled="isRelatedMemoryLoading" @click="handleLoadRelatedMemory">
          {{ isRelatedMemoryLoading ? 'Loading...' : 'View related memory' }}
        </button>
        <p v-if="relatedMemoryError" class="memory-error">{{ relatedMemoryError }}</p>
        <p v-else-if="relatedMemoryItems.length === 0" class="empty-copy">Click the button to show the related memory for the current node.</p>
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
      <p v-else class="empty-copy">Select a node here to display related memory.</p>
    </section>

    <section class="sidebar-section">
      <h2>Project memory search</h2>
      <div class="memory-search">
        <input
          v-model="memorySearchQuery"
          type="text"
          placeholder="For example: Who is related to the Shibuya station line?"
          @keydown.enter.prevent="handleSearchMemory"
        />
        <div class="custom-select-container">
          <div
            class="custom-select-trigger"
            :class="{ 'is-open': isMemorySearchTypeSelectOpen }"
            @click="isMemorySearchTypeSelectOpen = !isMemorySearchTypeSelectOpen"
          >
            <span>{{ memorySearchType === 'all' ? 'All types' : (nodeTypeOptions.find(opt => opt.type === memorySearchType)?.label || memorySearchType) }}</span>
            <div class="custom-select-arrow"></div>
          </div>
          <ul class="custom-select-options" v-show="isMemorySearchTypeSelectOpen">
            <li
              class="custom-select-option"
              :class="{ 'is-selected': memorySearchType === 'all' }"
              @click="memorySearchType = 'all'; isMemorySearchTypeSelectOpen = false"
            >
              All types
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
          {{ isMemorySearching ? 'Searching...' : 'Search memory' }}
        </button>
      </div>
      <p v-if="memorySearchError" class="memory-error">{{ memorySearchError }}</p>
      <p v-else-if="memorySearchItems.length === 0" class="empty-copy">Enter a question to search for existing lore within the current project.</p>
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

<style scoped src="./ProjectSidebar.scoped.css"></style>
