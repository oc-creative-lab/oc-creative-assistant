<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import {
  loadRagContext,
  type InspirationOutputDto,
  type RagContextResponseDto,
  type ResearchOutputDto,
  type StructureOutputDto,
} from '../../api/graphApi'
import {
  RELATION_TYPE_OPTIONS,
  type CreativeFlowEdge,
  type CreativeFlowNode,
  type CreativeNodeData,
  type CreativeNodeType,
  type CreativeRelationType,
} from '../../types/node'
import InspirationCard from '../agents/InspirationCard.vue'
import ResearchCard from '../agents/ResearchCard.vue'
import StructureCard from '../agents/StructureCard.vue'

type AgentType = 'inspiration' | 'research' | 'structure'

/**
 * 右侧详情面板。
 *
 * 编辑当前选中节点 / 连线, 并在同一面板内提供三类 Agent 调用入口和结构化结果展示。
 * 所有 graph 数据变更都通过事件交给上层容器统一落库, 组件只维护交互态。
 */
const props = defineProps<{
  selectedNode: CreativeFlowNode | null
  selectedEdge: CreativeFlowEdge | null
  nodes: CreativeFlowNode[]
  selectedNodeIds: string[]
}>()

const emit = defineEmits<{
  nodeUpdated: [node: CreativeFlowNode]
  nodeDeleted: [nodeId: string]
  edgeUpdated: [edge: CreativeFlowEdge]
  edgeDeleted: [edgeId: string]
  nodeCreated: [payload: { nodeType: CreativeNodeType; title: string; content: string; tags: string[] }]
  selectionAdded: [nodeId: string]
  selectionRemoved: [nodeId: string]
  selectionCleared: []
}>()

const ragQuery = ref('')
const ragResult = ref<RagContextResponseDto | null>(null)
const ragError = ref('')
const isRagLoading = ref(false)

/* Agent 调用结果按类型分别保存, 切换 Agent 类型时不会清空其他类型的上一次结果。 */
const lastAgentType = ref<AgentType | null>(null)
const inspirationOutput = ref<InspirationOutputDto | null>(null)
const researchOutput = ref<ResearchOutputDto | null>(null)
const structureOutput = ref<StructureOutputDto | null>(null)
const agentError = ref('')
const agentLoadingType = ref<AgentType | null>(null)

const isNodeStatusSelectOpen = ref(false)
const isEdgeRelationSelectOpen = ref(false)

function closeAllSelects(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-select-container')) {
    isNodeStatusSelectOpen.value = false
    isEdgeRelationSelectOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeAllSelects)
})

onUnmounted(() => {
  document.removeEventListener('click', closeAllSelects)
})

const selectedNodeTags = computed(() => props.selectedNode?.data.tags.join(', ') ?? '')

const sourceNodeTitle = computed(() => {
  if (!props.selectedEdge) {
    return ''
  }
  return props.nodes.find((node) => node.id === props.selectedEdge?.source)?.data.title ?? props.selectedEdge.source
})

const targetNodeTitle = computed(() => {
  if (!props.selectedEdge) {
    return ''
  }
  return props.nodes.find((node) => node.id === props.selectedEdge?.target)?.data.title ?? props.selectedEdge.target
})

/* 选区栏需要展示标题, 这里用 id -> 节点的快速查找避免每次循环全 nodes。 */
const nodeIndex = computed(() => {
  const map = new Map<string, CreativeFlowNode>()
  for (const node of props.nodes) {
    map.set(node.id, node)
  }
  return map
})

const selectedNodesPreview = computed(() => {
  return props.selectedNodeIds
    .map((id) => nodeIndex.value.get(id))
    .filter((node): node is CreativeFlowNode => Boolean(node))
})

const isCurrentNodeInSelection = computed(() => {
  return props.selectedNode ? props.selectedNodeIds.includes(props.selectedNode.id) : false
})

function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? '关联'
}

function updateNodeData(partial: Partial<CreativeNodeData>) {
  if (!props.selectedNode) {
    return
  }
  emit('nodeUpdated', {
    ...props.selectedNode,
    data: { ...props.selectedNode.data, ...partial },
  })
}

function updateNodeTags(rawValue: string) {
  const tags = rawValue.split(',').map((tag) => tag.trim()).filter(Boolean)
  updateNodeData({ tags })
}

function handleDeleteNode() {
  if (props.selectedNode) {
    emit('nodeDeleted', props.selectedNode.id)
  }
}

function updateEdge(partial: Partial<CreativeFlowEdge['data']>) {
  if (!props.selectedEdge) {
    return
  }
  const data = { ...props.selectedEdge.data, ...partial }
  emit('edgeUpdated', { ...props.selectedEdge, label: data.label, data })
}

function updateEdgeRelation(relationType: CreativeRelationType) {
  updateEdge({ relationType, label: getRelationLabel(relationType) })
}

function reverseSelectedEdge() {
  if (!props.selectedEdge) {
    return
  }
  emit('edgeUpdated', {
    ...props.selectedEdge,
    source: props.selectedEdge.target,
    target: props.selectedEdge.source,
    sourceHandle: props.selectedEdge.targetHandle,
    targetHandle: props.selectedEdge.sourceHandle,
  })
}

function summarizeContent(content: string) {
  return content.length > 120 ? `${content.slice(0, 120)}...` : content
}

/**
 * 调用指定类型的 Agent。
 *
 * inspiration / research 走单节点入口, 必须先选中节点;
 * structure 走多节点入口, 必须先把至少 2 个节点加入选区。
 */
async function runAgent(type: AgentType) {
  if (type === 'structure') {
    if (props.selectedNodeIds.length < 2) {
      agentError.value = 'Structure Agent 至少需要 2 个选区节点。'
      return
    }
  } else if (!props.selectedNode) {
    agentError.value = '请先在画布上选择一个节点。'
    return
  }

  try {
    agentLoadingType.value = type
    agentError.value = ''

    const response = await loadRagContext({
      node_id: type === 'structure' ? null : props.selectedNode!.id,
      node_ids: type === 'structure' ? props.selectedNodeIds : [],
      query: ragQuery.value,
      agent_type: type,
      top_k: 5,
    })

    ragResult.value = response
    lastAgentType.value = type

    if (type === 'inspiration') {
      inspirationOutput.value = response.inspiration_output
    } else if (type === 'research') {
      researchOutput.value = response.research_output
    } else {
      structureOutput.value = response.structure_output
    }

    /* 结构化输出为空通常意味着 LLM 没成功调用 tool, 给出可读提示而不是静默。 */
    const empty =
      (type === 'inspiration' && !response.inspiration_output) ||
      (type === 'research' && !response.research_output) ||
      (type === 'structure' && !response.structure_output)

    if (empty) {
      agentError.value = 'LLM 本次没有返回结构化输出, 请稍后重试或切换模型。'
    }
  } catch (error) {
    agentError.value = error instanceof Error ? error.message : 'Agent 调用失败'
  } finally {
    agentLoadingType.value = null
  }
}

/**
 * 加载当前节点的 RAG 调试上下文。
 *
 * 该按钮只展示后端检索到的图关系、向量上下文和最终 prompt, 不调用 LLM,
 * 用来验证 RAG 链路, 不影响 Agent 卡片展示。
 */
async function handleLoadRagContext() {
  if (!props.selectedNode) {
    return
  }
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
    ragError.value = error instanceof Error ? error.message : 'RAG 上下文加载失败'
  } finally {
    isRagLoading.value = false
  }
}

function handleToggleSelectionForCurrent() {
  if (!props.selectedNode) {
    return
  }
  if (isCurrentNodeInSelection.value) {
    emit('selectionRemoved', props.selectedNode.id)
  } else {
    emit('selectionAdded', props.selectedNode.id)
  }
}

function handleClearSelection() {
  emit('selectionCleared')
}

function handleAgentCreateNode(
  payload: { nodeType: CreativeNodeType; title: string; content: string; tags: string[] },
) {
  emit('nodeCreated', payload)
}

/* 切换选中对象时清空 RAG 调试预览, 但保留 Agent 卡片(用户可能在不同节点间来回查看上次结果)。 */
watch(
  () => [props.selectedNode?.id, props.selectedEdge?.id],
  () => {
    ragResult.value = null
    ragError.value = ''
  },
)
</script>

<template>
  <!-- 右侧属性面板：编辑当前选中节点 -->
  <aside class="detail-sidebar">
    <template v-if="selectedNode">
      <section class="detail-header">
        <p>当前节点</p>
        <h2>{{ selectedNode.data.icon }} {{ selectedNode.data.title }}</h2>
        <span class="status-badge" :class="selectedNode.data.status">{{ selectedNode.data.status }}</span>
      </section>

      <section class="detail-panel">
        <label for="node-type">节点类型</label>
        <div class="input-wrapper">
          <input id="node-type" type="text" :value="selectedNode.data.typeLabel" disabled />
        </div>

        <label for="node-title">节点标题</label>
        <div class="input-wrapper">
          <input
            id="node-title"
            type="text"
            :value="selectedNode.data.title"
            @input="updateNodeData({ title: ($event.target as HTMLInputElement).value })"
          />
        </div>

        <label for="node-content">节点内容</label>
        <div class="input-wrapper">
          <textarea
            id="node-content"
            rows="4"
            :value="selectedNode.data.content"
            @input="updateNodeData({ content: ($event.target as HTMLTextAreaElement).value })"
          />
        </div>

        <label for="node-tags">标签</label>
        <div class="input-wrapper">
          <input
            id="node-tags"
            type="text"
            :value="selectedNodeTags"
            placeholder="用逗号分隔，例如：主角, 第一幕"
            @input="updateNodeTags(($event.target as HTMLInputElement).value)"
          />
        </div>

        <label for="node-status">状态</label>
        <div class="custom-select-container">
          <div
            class="custom-select-trigger"
            :class="{ 'is-open': isNodeStatusSelectOpen }"
            @click="isNodeStatusSelectOpen = !isNodeStatusSelectOpen; isEdgeRelationSelectOpen = false"
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

        <button type="button" class="danger" @click="handleDeleteNode">删除节点</button>
      </section>

      <section class="detail-panel">
        <header class="agent-section-header">
          <h3>Agent Actions</h3>
          <button
            v-if="selectedNodeIds.length > 0"
            type="button"
            class="text-button"
            @click="handleClearSelection"
          >
            清空选区
          </button>
        </header>

        <div class="selection-bar" v-if="selectedNodeIds.length > 0 || selectedNode">
          <p class="selection-bar__count">
            当前选区：<strong>{{ selectedNodeIds.length }}</strong> 个节点
            <span class="selection-bar__hint">（Structure Agent 需要至少 2 个）</span>
          </p>
          <ul v-if="selectedNodesPreview.length" class="selection-bar__list">
            <li v-for="node in selectedNodesPreview" :key="node.id">
              {{ node.data.icon }} {{ node.data.title }}
            </li>
          </ul>
          <button
            v-if="selectedNode"
            type="button"
            class="selection-bar__toggle"
            @click="handleToggleSelectionForCurrent"
          >
            {{ isCurrentNodeInSelection ? '− 从选区移除当前节点' : '+ 把当前节点加入选区' }}
          </button>
        </div>

        <label for="agent-query">附加请求（可选）</label>
        <div class="input-wrapper">
          <textarea
            id="agent-query"
            rows="2"
            v-model="ragQuery"
            placeholder="留空时 Agent 会基于当前节点 / 选区自动推断"
          />
        </div>

        <div class="agent-actions">
          <button
            type="button"
            :disabled="!selectedNode || agentLoadingType !== null"
            @click="runAgent('inspiration')"
          >
            {{ agentLoadingType === 'inspiration' ? '生成中...' : '💡 灵感引导' }}
          </button>
          <button
            type="button"
            :disabled="!selectedNode || agentLoadingType !== null"
            @click="runAgent('research')"
          >
            {{ agentLoadingType === 'research' ? '检索中...' : '📚 资料查询' }}
          </button>
          <button
            type="button"
            :disabled="selectedNodeIds.length < 2 || agentLoadingType !== null"
            @click="runAgent('structure')"
          >
            {{ agentLoadingType === 'structure' ? '整理中...' : '🗂 结构整理' }}
          </button>
        </div>

        <p v-if="agentError" class="agent-error">{{ agentError }}</p>

        <div class="agent-output" v-if="lastAgentType">
          <InspirationCard
            v-if="lastAgentType === 'inspiration' && inspirationOutput"
            :output="inspirationOutput"
            @create-node="handleAgentCreateNode"
          />
          <ResearchCard
            v-else-if="lastAgentType === 'research' && researchOutput"
            :output="researchOutput"
          />
          <StructureCard
            v-else-if="lastAgentType === 'structure' && structureOutput"
            :output="structureOutput"
            @create-node="handleAgentCreateNode"
          />
        </div>
      </section>

      <section class="detail-panel rag-panel">
        <h3>RAG 检索调试</h3>
        <p class="rag-hint">仅查看后端检索到的图关系、向量结果和最终 prompt, 不调用 LLM。</p>
        <button type="button" :disabled="isRagLoading" @click="handleLoadRagContext">
          {{ isRagLoading ? '加载 RAG 上下文...' : '查看 RAG 上下文' }}
        </button>
        <p v-if="ragError" class="rag-error">{{ ragError }}</p>

        <div v-if="ragResult" class="rag-result">
          <details open>
            <summary>当前节点 Current Node</summary>
            <div class="rag-card">
              <strong>{{ ragResult.current_node.title }}</strong>
              <span>{{ ragResult.current_node.type }}</span>
              <p>{{ ragResult.current_node.content }}</p>
            </div>
          </details>

          <details open>
            <summary>图关系上下文 Graph Context</summary>
            <p v-if="ragResult.graph_context.length === 0" class="rag-empty">暂无直接连接的相关节点</p>
            <article v-for="item in ragResult.graph_context" :key="item.id" class="rag-card">
              <strong>{{ item.relation_label }} / {{ item.relation_type }}</strong>
              <span>{{ item.direction }} · {{ item.type }} · {{ item.title }}</span>
              <p>{{ summarizeContent(item.content) }}</p>
            </article>
          </details>

          <details open>
            <summary>向量检索上下文 Vector Context</summary>
            <p v-if="ragResult.vector_context.length === 0" class="rag-empty">暂无向量检索结果</p>
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
            <summary>最终 Prompt</summary>
            <pre class="prompt-preview">{{ ragResult.prompt }}</pre>
          </details>
        </div>
      </section>
    </template>

    <template v-else-if="selectedEdge">
      <section class="detail-header">
        <p>当前连线</p>
        <h2>{{ selectedEdge.data.label }}</h2>
      </section>

      <section class="detail-panel">
        <dl class="edge-meta">
          <div>
            <dt>起点节点</dt>
            <dd>{{ sourceNodeTitle }}</dd>
          </div>
          <div>
            <dt>终点节点</dt>
            <dd>{{ targetNodeTitle }}</dd>
          </div>
        </dl>

        <label for="edge-relation">连线关系类型</label>
        <div class="custom-select-container">
          <div
            class="custom-select-trigger"
            :class="{ 'is-open': isEdgeRelationSelectOpen }"
            @click="isEdgeRelationSelectOpen = !isEdgeRelationSelectOpen; isNodeStatusSelectOpen = false"
          >
            <span>{{ RELATION_TYPE_OPTIONS.find(opt => opt.value === selectedEdge?.data.relationType)?.label || selectedEdge.data.relationType }}</span>
            <div class="custom-select-arrow"></div>
          </div>
          <ul class="custom-select-options" v-show="isEdgeRelationSelectOpen">
            <li
              v-for="option in RELATION_TYPE_OPTIONS"
              :key="option.value"
              class="custom-select-option"
              :class="{ 'is-selected': selectedEdge.data.relationType === option.value }"
              @click="updateEdgeRelation(option.value as CreativeRelationType); isEdgeRelationSelectOpen = false"
            >
              {{ option.label }}
            </li>
          </ul>
        </div>

        <label for="edge-label">连线标签</label>
        <div class="input-wrapper">
          <input
            id="edge-label"
            type="text"
            :value="selectedEdge.data.label"
            @input="updateEdge({ label: ($event.target as HTMLInputElement).value })"
          />
        </div>

        <button type="button" class="secondary-action" @click="reverseSelectedEdge">反转方向</button>
        <button type="button" class="danger" @click="$emit('edgeDeleted', selectedEdge.id)">删除连线</button>
      </section>
    </template>

    <section v-else class="empty-state">
      <p>未选择对象</p>
      <span>选择一个节点编辑内容，或选择一条连线编辑关系标签。</span>
    </section>
  </aside>
</template>

<style scoped>
.detail-sidebar {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  border-left: 1px solid var(--border);
  background: var(--panel);
  color: var(--text);
}

/* 自定义滚动条样式 */
.detail-sidebar::-webkit-scrollbar {
  width: 6px;
}

.detail-sidebar::-webkit-scrollbar-track {
  background: transparent;
}

.detail-sidebar::-webkit-scrollbar-thumb {
  background-color: rgba(156, 163, 175, 0.4);
  border-radius: 4px;
}

.detail-sidebar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(156, 163, 175, 0.7);
}

/* 头部区域 */
.detail-header {
  padding: 24px 20px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-strong);
  position: sticky;
  top: 0;
  z-index: 10;
}

.detail-header p {
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.detail-header h2 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 状态徽章 */
.status-badge {
  display: inline-flex;
  align-items: center;
  margin-top: 14px;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.status-badge.outdated {
  background: #fffbeb;
  color: #b45309;
  border-color: #fef3c7;
}

.status-badge.synced {
  background: #f0fdfa;
  color: #0f766e;
  border-color: #ccfbf1;
}

/* 面板区块 */
.detail-panel {
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
}

.detail-panel + .detail-panel {
  border-top: 1px solid var(--border);
}

.detail-panel h3 {
  margin: 0 0 4px;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
}

/* 表单元素 */
label {
  display: block;
  margin-bottom: 8px;
  color: var(--text);
  font-size: 0.85rem;
  font-weight: 500;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

input,
textarea {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background-color: var(--app-bg);
  color: var(--text);
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1.5;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
}

input:disabled {
  background-color: var(--panel-strong);
  color: var(--muted);
  cursor: not-allowed;
}

input:focus:not(:disabled),
textarea:focus:not(:disabled) {
  outline: none;
  border-color: var(--accent);
  background-color: #ffffff;
  box-shadow: 0 0 0 3px var(--accent-soft), 0 1px 2px rgba(0, 0, 0, 0.02);
}

input::placeholder,
textarea::placeholder {
  color: #9ca3af;
}

textarea {
  resize: vertical;
  min-height: 80px;
}

/* 自定义下拉框组件样式 */
.custom-select-container {
  position: relative;
  width: 100%;
  margin-bottom: 16px;
  user-select: none;
}

.custom-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 38px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background-color: var(--app-bg);
  color: var(--text);
  font-size: 0.9rem;
  line-height: 1.5;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
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
  font-size: 0.9rem;
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

/* 按钮样式 */
button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #ffffff;
  color: var(--text);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

button:hover {
  background: var(--app-bg);
  border-color: #d1d5db;
  transform: translateY(-1px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
}

button:active {
  transform: translateY(0);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

button.danger {
  color: #dc2626;
  border-color: #fecaca;
  background: #fef2f2;
  box-shadow: none;
}

button.danger:hover {
  background: #fee2e2;
  border-color: #fca5a5;
}

button.secondary-action {
  margin-bottom: 10px;
  color: var(--accent);
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

/* Agent Actions 区块 */
.agent-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 10px;
  margin-top: 8px;
}

.agent-result {
  margin: 8px 0 0;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  color: #374151;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-x: auto;
}

.rag-panel {
  gap: 12px;
}

.rag-error {
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #b42318;
  font-size: 0.84rem;
}

.rag-result {
  display: grid;
  gap: 10px;
}

.rag-result details {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-strong);
}

.rag-result summary {
  padding: 10px 12px;
  color: var(--text);
  font-size: 0.86rem;
  font-weight: 700;
  cursor: pointer;
}

.rag-card {
  display: grid;
  gap: 5px;
  margin: 0 10px 10px;
  padding: 10px;
  border-radius: 8px;
  background: var(--app-bg);
}

.rag-card strong {
  font-size: 0.88rem;
}

.rag-card span,
.rag-debug-line,
.rag-empty {
  color: var(--muted);
  font-size: 0.78rem;
}

.rag-card p,
.rag-empty,
.rag-debug-line {
  margin: 0;
  line-height: 1.45;
}

.rag-debug-line,
.rag-empty {
  padding: 0 12px 12px;
}

.prompt-preview {
  max-height: 360px;
  margin: 0 10px 10px;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: #111827;
  color: #f9fafb;
  font-size: 0.76rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

/* 连线元数据 */
.edge-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 0;
  padding: 16px;
  background: var(--app-bg);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.edge-meta div {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.edge-meta dt {
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.edge-meta dd {
  margin: 0;
  color: var(--text);
  font-size: 0.95rem;
  font-weight: 500;
  word-break: break-word;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px 20px;
  text-align: center;
  color: var(--muted);
}

.empty-state p {
  margin: 0 0 12px;
  color: var(--text);
  font-size: 1.1rem;
  font-weight: 600;
}

.empty-state span {
  font-size: 0.9rem;
  line-height: 1.5;
  max-width: 240px;
}

@media (max-width: 920px) {
  .detail-sidebar {
    border-left: none;
    border-top: 1px solid var(--border);
  }
}

.agent-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.agent-section-header h3 {
  margin: 0;
}

.text-button {
  min-height: auto;
  padding: 4px 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: 0.78rem;
  cursor: pointer;
  box-shadow: none;
}

.text-button:hover {
  color: var(--text);
  background: var(--app-bg);
  border-color: var(--border);
  transform: none;
}

.selection-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  background: var(--panel-strong);
}

.selection-bar__count {
  margin: 0;
  color: var(--text);
  font-size: 0.82rem;
}

.selection-bar__count strong {
  color: var(--accent);
}

.selection-bar__hint {
  color: var(--muted);
  font-size: 0.74rem;
}

.selection-bar__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.selection-bar__list li {
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--app-bg);
  color: var(--text);
  font-size: 0.76rem;
}

.selection-bar__toggle {
  align-self: flex-start;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: #ffffff;
  color: var(--text);
  font-size: 0.78rem;
  cursor: pointer;
  box-shadow: none;
}

.selection-bar__toggle:hover {
  background: var(--app-bg);
}

.agent-error {
  margin: 8px 0 0;
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fef2f2;
  color: #b42318;
  font-size: 0.82rem;
}

.agent-output {
  margin-top: 14px;
}

.rag-hint {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.45;
}
</style>
