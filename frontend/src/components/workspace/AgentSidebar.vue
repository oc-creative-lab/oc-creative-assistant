<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import {
  RELATION_TYPE_OPTIONS,
  type CreativeFlowEdge,
  type CreativeFlowNode,
  type CreativeNodeData,
  type CreativeRelationType,
} from '../../types/node'

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

// 自定义下拉框的状态
const isNodeStatusSelectOpen = ref(false)
const isEdgeRelationSelectOpen = ref(false)

// 点击外部关闭下拉框
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

function updateNodeData(partial: Partial<CreativeNodeData>) {
  if (!props.selectedNode) {
    return
  }

  // 右侧面板是节点完整内容的编辑入口，画布卡片只负责展示摘要。
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
  if (!props.selectedNode) {
    return
  }

  // 删除节点属于危险操作，实际级联删除相关连线由 AppShell 统一处理，避免右侧面板直接改全局 graph。
  emit('nodeDeleted', props.selectedNode.id)
}

function updateEdge(partial: Partial<CreativeFlowEdge['data']>) {
  if (!props.selectedEdge) {
    return
  }

  const data = {
    ...props.selectedEdge.data,
    ...partial,
  }

  // 修改关系标签后立即抛给 AppShell，随后由统一保存流程同步到后端。
  emit('edgeUpdated', {
    ...props.selectedEdge,
    label: data.label,
    data,
  })
}

function runAgentMock(type: 'inspiration' | 'research' | 'structure') {
  // Agent mock 只展示结构化占位结果，不自动写入节点正文，保留用户手动采纳边界。
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

watch(
  () => [props.selectedNode?.id, props.selectedEdge?.id],
  () => {
    agentResult.value = ''
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
              @click="updateEdge({ relationType: option.value as CreativeRelationType }); isEdgeRelationSelectOpen = false"
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
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  border-left: 1px solid var(--border);
  background: var(--panel);
  color: var(--text);
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
