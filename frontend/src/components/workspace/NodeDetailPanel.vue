<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { loadRagContext, type RagContextResponseDto } from '../../api/graphApi'
import type { CreativeFlowNode, CreativeNodeData } from '../../types/node'

/**
 * 节点详情面板。
 *
 * 同时承载节点字段编辑、Agent mock 占位和 RAG 调试视图; 三块功能都只在
 * "当前选中一个节点"时才有意义, 因此合并在同一个子组件里, 切换节点时
 * 通过 watch(props.selectedNode.id) 清空临时预览。
 */
const props = defineProps<{
  selectedNode: CreativeFlowNode
}>()

const emit = defineEmits<{
  nodeUpdated: [node: CreativeFlowNode]
  nodeDeleted: [nodeId: string]
}>()

const agentResult = ref('')
const ragQuery = ref('')
const ragResult = ref<RagContextResponseDto | null>(null)
const ragError = ref('')
const isRagLoading = ref(false)

/* 自定义下拉没有使用原生 select, 需要在组件内维护展开状态和外部点击收起 */
const isNodeStatusSelectOpen = ref(false)

function closeAllSelects(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-select-container')) {
    isNodeStatusSelectOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeAllSelects)
})

onUnmounted(() => {
  document.removeEventListener('click', closeAllSelects)
})

const selectedNodeTags = computed(() => props.selectedNode.data.tags.join(', '))

function updateNodeData(partial: Partial<CreativeNodeData>) {
  emit('nodeUpdated', {
    ...props.selectedNode,
    data: {
      ...props.selectedNode.data,
      ...partial,
    },
  })
}

function updateNodeTags(rawValue: string) {
  const tags = rawValue
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
  updateNodeData({ tags })
}

function handleDeleteNode() {
  emit('nodeDeleted', props.selectedNode.id)
}

/**
 * 生成 Agent 占位结果。
 *
 * 当前 mock 只用于确认侧边栏交互和结果展示形态, 不自动写入节点正文,
 * 保留用户手动采纳生成内容的产品边界。
 */
function runAgentMock(type: 'inspiration' | 'research' | 'structure') {
  if (type === 'inspiration') {
    agentResult.value = JSON.stringify(
      {
        type: 'inspiration',
        suggestions: [
          'What is the core desire of this character?',
          'What setting will conflict with which existing worldview node?',
          'Is it necessary to supplement an event node to explain its background?',
        ],
      },
      null,
      2,
    )
    return
  }

  if (type === 'research') {
    agentResult.value = JSON.stringify(
      {
        type: 'research',
        summary: 'RAG or research results will appear here.',
        status: 'RAG is not yet connected',
      },
      null,
      2,
    )
    return
  }

  agentResult.value = JSON.stringify(
    {
      type: 'structure',
      summary: 'This will organize nodes into character cards, relationship maps, or plot frames.',
      status: 'Structure Agent not connected yet',
    },
    null,
    2,
  )
}

function summarizeContent(content: string) {
  return content.length > 120 ? `${content.slice(0, 120)}...` : content
}

/**
 * 加载当前节点的 RAG 调试上下文。
 *
 * 只展示后端检索到的图关系、向量上下文和最终 prompt, 不调用 LLM,
 * 也不会把结果写回节点内容。
 */
async function handleLoadRagContext() {
  try {
    isRagLoading.value = true
    ragError.value = ''
    ragResult.value = await loadRagContext({
      node_id: props.selectedNode.id,
      query: ragQuery.value,
      agent_type: 'inspiration',
      top_k: 5,
    })
  } catch (error) {
    ragResult.value = null
    ragError.value = error instanceof Error ? error.message : 'Failed to load RAG context'
  } finally {
    isRagLoading.value = false
  }
}

/* 切换选中节点时清空临时预览, 避免把上一节点的 Agent/RAG 结果误认为当前上下文 */
watch(
  () => props.selectedNode.id,
  () => {
    agentResult.value = ''
    ragResult.value = null
    ragError.value = ''
  },
)
</script>

<template>
  <div class="node-detail-panel">
    <section class="detail-header">
      <p>Current node</p>
      <h2>{{ selectedNode.data.icon }} {{ selectedNode.data.title }}</h2>
      <span class="status-badge" :class="selectedNode.data.status">{{ selectedNode.data.status }}</span>
    </section>

    <section class="detail-panel">
      <label for="node-type">Node type</label>
      <div class="input-wrapper">
        <input id="node-type" type="text" :value="selectedNode.data.typeLabel" disabled />
      </div>

      <label for="node-title">Node title</label>
      <div class="input-wrapper">
        <input
          id="node-title"
          type="text"
          :value="selectedNode.data.title"
          @input="updateNodeData({ title: ($event.target as HTMLInputElement).value })"
        />
      </div>

      <label for="node-content">Node content</label>
      <div class="input-wrapper">
        <textarea
          id="node-content"
          rows="4"
          :value="selectedNode.data.content"
          @input="updateNodeData({ content: ($event.target as HTMLTextAreaElement).value })"
        />
      </div>

      <label for="node-tags">Tags</label>
      <div class="input-wrapper">
        <input
          id="node-tags"
          type="text"
          :value="selectedNodeTags"
          placeholder="Separate with commas, e.g. protagonist, first act"
          @input="updateNodeTags(($event.target as HTMLInputElement).value)"
        />
      </div>

      <label for="node-status">Status</label>
      <div class="custom-select-container">
        <div
          class="custom-select-trigger"
          :class="{ 'is-open': isNodeStatusSelectOpen }"
          @click="isNodeStatusSelectOpen = !isNodeStatusSelectOpen"
        >
          <span>{{ selectedNode.data.status }}</span>
          <div class="custom-select-arrow"></div>
        </div>
        <ul class="custom-select-options" v-show="isNodeStatusSelectOpen">
          <li
            v-for="status in ['draft', 'synced', 'outdated']"
            :key="status"
            class="custom-select-option"
            :class="{ 'is-selected': selectedNode.data.status === status }"
            @click="updateNodeData({ status: status as CreativeNodeData['status'] }); isNodeStatusSelectOpen = false"
          >
            {{ status }}
          </li>
        </ul>
      </div>

      <button type="button" class="danger" @click="handleDeleteNode">Delete node</button>
    </section>

    <section class="detail-panel">
      <h3>Agent Actions placeholder</h3>
      <div class="agent-actions">
        <button type="button" @click="runAgentMock('inspiration')">Inspiration</button>
        <button type="button" @click="runAgentMock('research')">Research</button>
        <button type="button" @click="runAgentMock('structure')">Structure</button>
      </div>
      <pre v-if="agentResult" class="agent-result">{{ agentResult }}</pre>
    </section>

    <section class="detail-panel rag-panel">
      <h3>RAG / Agent Debug</h3>
      <label for="rag-query">User request</label>
      <div class="input-wrapper">
        <textarea
          id="rag-query"
          rows="3"
          v-model="ragQuery"
          placeholder="When empty, use the current node title and content as the search query"
        />
      </div>
      <!-- 当前按钮只查看上下文，不调用 LLM，也不会把结果写入节点正文。 -->
      <button type="button" :disabled="isRagLoading" @click="handleLoadRagContext">
        {{ isRagLoading ? 'Loading RAG context...' : 'View RAG context' }}
      </button>
      <p v-if="ragError" class="rag-error">{{ ragError }}</p>

      <div v-if="ragResult" class="rag-result">
        <details open>
          <summary>Current node</summary>
          <div class="rag-card">
            <strong>{{ ragResult.current_node.title }}</strong>
            <span>{{ ragResult.current_node.type }}</span>
            <p>{{ ragResult.current_node.content }}</p>
          </div>
        </details>

        <details open>
          <summary>Graph context</summary>
          <p v-if="ragResult.graph_context.length === 0" class="rag-empty">No related nodes directly connected</p>
          <article v-for="item in ragResult.graph_context" :key="item.id" class="rag-card">
            <strong>{{ item.relation_label }} / {{ item.relation_type }}</strong>
            <span>{{ item.direction }} · {{ item.type }} · {{ item.title }}</span>
            <p>{{ summarizeContent(item.content) }}</p>
          </article>
        </details>

        <details open>
          <summary>Vector search context</summary>
          <p v-if="ragResult.vector_context.length === 0" class="rag-empty">No vector search results</p>
          <article v-for="item in ragResult.vector_context" :key="item.id" class="rag-card">
            <strong>score {{ item.score.toFixed(2) }}</strong>
            <span>{{ item.type }} · {{ item.title }}</span>
            <p>{{ summarizeContent(item.content) }}</p>
          </article>
          <p class="rag-debug-line">
            vector_store: {{ ragResult.debug.vector_store }}
            <span v-if="ragResult.debug.vector_error"> / {{ ragResult.debug.vector_error }}</span>
          </p>
        </details>

        <details>
          <summary>Final prompt</summary>
          <!-- 先让用户看到 AI 将接收的上下文，便于验证检索和拼接是否合理。 -->
          <pre class="prompt-preview">{{ ragResult.prompt }}</pre>
        </details>
      </div>
    </section>
  </div>
</template>

<style scoped src="./AgentSidebar.scoped.css"></style>