<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { loadRagContext, type RagContextResponseDto } from '../../api/graphApi'
import type { CreativeFlowNode, CreativeNodeData } from '../../types/node'

/**
 * Node detail panel.
 *
 * Hosts node field editing, the Agent mock placeholder, and the RAG debug view at
 * once; all three only make sense when "a single node is selected", so they are
 * merged into the same child component, and switching nodes clears the temporary
 * preview via watch(props.selectedNode.id).
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

/* The custom dropdown does not use a native select, so the component must track the
   open state itself and collapse on outside clicks. */
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
 * Generate a placeholder Agent result.
 *
 * The current mock only confirms the sidebar interaction and result presentation;
 * it does not auto-write into the node body, preserving the product boundary where
 * the user manually adopts generated content.
 */
function runAgentMock(type: 'inspiration' | 'research' | 'structure') {
  if (type === 'inspiration') {
    agentResult.value = JSON.stringify(
      {
        type: 'inspiration',
        suggestions: [
          'What is this character\'s core desire?',
          'Which existing worldbuilding node would this setting conflict with?',
          'Do we need an event node to explain its background?',
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
        summary: 'RAG or research lookup results will appear here in the future.',
        status: 'RAG not yet connected',
      },
      null,
      2,
    )
    return
  }

  agentResult.value = JSON.stringify(
    {
      type: 'structure',
      summary: 'In the future this will organize multiple nodes into character cards, relationship graphs, or plot frameworks.',
      status: 'Structure Agent not yet connected',
    },
    null,
    2,
  )
}

function summarizeContent(content: string) {
  return content.length > 120 ? `${content.slice(0, 120)}...` : content
}

/**
 * Load the RAG debug context for the current node.
 *
 * Only displays the graph relations, vector context, and final prompt retrieved by
 * the backend; it does not call the LLM, nor does it write results back into the
 * node content.
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

/* Clear the temporary preview when switching nodes, so the previous node's Agent/RAG
   results aren't mistaken for the current context. */
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
          placeholder="Comma-separated, e.g. protagonist, act one"
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
          placeholder="Leave empty to use the current node's title and content as the search query"
        />
      </div>
      <!-- This button only inspects the context; it does not call the LLM, nor does it write results into the node body. -->
      <button type="button" :disabled="isRagLoading" @click="handleLoadRagContext">
        {{ isRagLoading ? 'Loading RAG context…' : 'View RAG context' }}
      </button>
      <p v-if="ragError" class="rag-error">{{ ragError }}</p>

      <div v-if="ragResult" class="rag-result">
        <details open>
          <summary>Current Node</summary>
          <div class="rag-card">
            <strong>{{ ragResult.current_node.title }}</strong>
            <span>{{ ragResult.current_node.type }}</span>
            <p>{{ ragResult.current_node.content }}</p>
          </div>
        </details>

        <details open>
          <summary>Graph Context</summary>
          <p v-if="ragResult.graph_context.length === 0" class="rag-empty">No directly connected related nodes yet</p>
          <article v-for="item in ragResult.graph_context" :key="item.id" class="rag-card">
            <strong>{{ item.relation_label }} / {{ item.relation_type }}</strong>
            <span>{{ item.direction }} · {{ item.type }} · {{ item.title }}</span>
            <p>{{ summarizeContent(item.content) }}</p>
          </article>
        </details>

        <details open>
          <summary>Vector Context</summary>
          <p v-if="ragResult.vector_context.length === 0" class="rag-empty">No vector search results yet</p>
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
          <summary>Final Prompt</summary>
          <!-- Show the user the context the AI will receive first, to help verify that retrieval and assembly are reasonable. -->
          <pre class="prompt-preview">{{ ragResult.prompt }}</pre>
        </details>
      </div>
    </section>
  </div>
</template>

<style scoped src="./AgentSidebar.scoped.css"></style>