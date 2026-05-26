<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { loadRagContext, type RagContextResponseDto } from '../../api/graphApi'
import {
  RELATION_TYPE_OPTIONS,
  type CreativeFlowEdge,
  type CreativeFlowNode,
  type CreativeNodeData,
  type CreativeRelationType,
} from '../../types/node'

/**
 * 右侧详情面板。
 *
 * 本组件负责展示并编辑当前选中的节点或连线，所有 graph 数据变更都通过事件交给
 * 上层容器统一落库。组件内只维护面板交互状态和 RAG 调试预览，不直接保存后端数据。
 */
const props = defineProps<{
  selectedNode: CreativeFlowNode | null
  selectedEdge: CreativeFlowEdge | null
  nodes: CreativeFlowNode[]
}>()

const emit = defineEmits<{
  nodeUpdated: [node: CreativeFlowNode]
  nodeDeleted: [nodeId: string]
  edgeUpdated: [edge: CreativeFlowEdge]
  edgeDeleted: [edgeId: string]
}>()

const agentResult = ref('')
const ragQuery = ref('')
const ragResult = ref<RagContextResponseDto | null>(null)
const ragError = ref('')
const isRagLoading = ref(false)

/* 自定义下拉没有使用原生 select，需要在组件内维护展开状态和外部点击收起行为。 */
const isNodeStatusSelectOpen = ref(false)
const isEdgeRelationSelectOpen = ref(false)

/**
 * 处理自定义下拉框的外部点击。
 *
 * 监听挂在 document 上，避免下拉选项溢出当前面板时无法可靠收起。
 *
 * Args:
 *   e: document click 事件。
 */
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

function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? '关联'
}

/**
 * 提交节点数据的局部更新。
 *
 * 右侧面板是节点完整内容的编辑入口，画布卡片只负责展示摘要；实际保存和全局
 * graph 一致性由上层容器处理。
 *
 * Args:
 *   partial: 需要合并到当前节点 data 的字段。
 */
function updateNodeData(partial: Partial<CreativeNodeData>) {
  if (!props.selectedNode) {
    return
  }

  emit('nodeUpdated', {
    ...props.selectedNode,
    data: {
      ...props.selectedNode.data,
      ...partial,
    },
  })
}

/**
 * 将输入框中的逗号分隔文本转换为节点标签。
 *
 * Args:
 *   rawValue: 用户在标签输入框中输入的原始文本。
 */
function updateNodeTags(rawValue: string) {
  const tags = rawValue
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)

  updateNodeData({ tags })
}

/**
 * 请求删除当前节点。
 *
 * 删除节点会影响相关连线，因此这里只发出意图事件，级联清理由 AppShell 统一执行。
 */
function handleDeleteNode() {
  if (!props.selectedNode) {
    return
  }

  emit('nodeDeleted', props.selectedNode.id)
}

/**
 * 提交连线数据的局部更新。
 *
 * 连线标签同时写入 Vue Flow 的顶层 label 和业务 data，保证画布展示与后端 payload
 * 使用同一份关系文本。
 *
 * Args:
 *   partial: 需要合并到当前连线 data 的字段。
 */
function updateEdge(partial: Partial<CreativeFlowEdge['data']>) {
  if (!props.selectedEdge) {
    return
  }

  const data = {
    ...props.selectedEdge.data,
    ...partial,
  }

  emit('edgeUpdated', {
    ...props.selectedEdge,
    label: data.label,
    data,
  })
}

function updateEdgeRelation(relationType: CreativeRelationType) {
  updateEdge({
    relationType,
    label: getRelationLabel(relationType),
  })
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

/**
 * 生成 Agent 占位结果。
 *
 * 当前 mock 只用于确认侧边栏交互和结果展示形态，不自动写入节点正文，保留用户
 * 手动采纳生成内容的产品边界。
 *
 * Args:
 *   type: 需要预览的 Agent 类型。
 */
function runAgentMock(type: 'inspiration' | 'research' | 'structure') {
  if (type === 'inspiration') {
    agentResult.value = JSON.stringify(
      {
        type: 'inspiration',
        suggestions: [
          '这个角色的核心欲望是什么？',
          '这个设定会和哪个已有世界观节点发生冲突？',
          '是否需要补充一个事件节点解释其背景？',
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
        summary: '这里将来会展示 RAG 或资料查询结果。',
        status: 'RAG 尚未接入',
      },
      null,
      2,
    )
    return
  }

  agentResult.value = JSON.stringify(
    {
      type: 'structure',
      summary: '这里将来会把多个节点整理成角色卡、关系图或剧情框架。',
      status: 'Structure Agent 尚未接入',
    },
    null,
    2,
  )
}

/**
 * 截断长文本用于上下文卡片预览。
 *
 * Args:
 *   content: 原始节点内容。
 *
 * Returns:
 *   适合在侧边栏卡片展示的摘要文本。
 */
function summarizeContent(content: string) {
  return content.length > 120 ? `${content.slice(0, 120)}...` : content
}

/**
 * 加载当前节点的 RAG 调试上下文。
 *
 * 该请求只展示后端检索到的图关系、向量上下文和最终 prompt，不调用 LLM，
 * 也不会把结果写回节点内容。
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

/* 切换选中对象时清空临时预览，避免把上一节点的 Agent/RAG 结果误认为当前上下文。 */
watch(
  () => [props.selectedNode?.id, props.selectedEdge?.id],
  () => {
    agentResult.value = ''
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
        <h3>Agent Actions 占位</h3>
        <div class="agent-actions">
          <button type="button" @click="runAgentMock('inspiration')">灵感引导</button>
          <button type="button" @click="runAgentMock('research')">资料查询</button>
          <button type="button" @click="runAgentMock('structure')">结构整理</button>
        </div>
        <pre v-if="agentResult" class="agent-result">{{ agentResult }}</pre>
      </section>

      <section class="detail-panel rag-panel">
        <h3>RAG / Agent 调试</h3>
        <label for="rag-query">用户请求</label>
        <div class="input-wrapper">
          <textarea
            id="rag-query"
            rows="3"
            v-model="ragQuery"
            placeholder="留空时使用当前节点标题和内容作为检索 query"
          />
        </div>
        <!-- 当前按钮只查看上下文，不调用 LLM，也不会把结果写入节点正文。 -->
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
            <!-- 先让用户看到 AI 将接收的上下文，便于验证检索和拼接是否合理。 -->
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
</style>
