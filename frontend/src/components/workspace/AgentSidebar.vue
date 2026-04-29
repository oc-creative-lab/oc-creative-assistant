<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
  edgeUpdated: [edge: CreativeFlowEdge]
  edgeDeleted: [edgeId: string]
}>()

const agentResult = ref('')

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
        <label>
          节点类型
          <input type="text" :value="selectedNode.data.typeLabel" disabled />
        </label>

        <label>
          节点标题
          <input
            type="text"
            :value="selectedNode.data.title"
            @input="updateNodeData({ title: ($event.target as HTMLInputElement).value })"
          />
        </label>

        <label>
          节点内容
          <textarea
            rows="4"
            :value="selectedNode.data.content"
            @input="updateNodeData({ content: ($event.target as HTMLTextAreaElement).value })"
          />
        </label>

        <label>
          标签
          <input
            type="text"
            :value="selectedNodeTags"
            placeholder="用逗号分隔，例如：主角, 第一幕"
            @input="updateNodeTags(($event.target as HTMLInputElement).value)"
          />
        </label>

        <label>
          状态
          <select
            :value="selectedNode.data.status"
            @change="updateNodeData({ status: ($event.target as HTMLSelectElement).value as CreativeNodeData['status'] })"
          >
            <option value="draft">draft</option>
            <option value="synced">synced</option>
            <option value="outdated">outdated</option>
          </select>
        </label>
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

        <label>
          连线关系类型
          <select
            :value="selectedEdge.data.relationType"
            @change="updateEdge({ relationType: ($event.target as HTMLSelectElement).value as CreativeRelationType })"
          >
            <option
              v-for="option in RELATION_TYPE_OPTIONS"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <label>
          连线标签
          <input
            type="text"
            :value="selectedEdge.data.label"
            @input="updateEdge({ label: ($event.target as HTMLInputElement).value })"
          />
        </label>

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
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: auto;
  border-left: 1px solid var(--border);
  background: var(--panel);
}

.detail-header,
.detail-panel,
.empty-state {
  padding: 20px;
}

.detail-header {
  border-bottom: 1px solid var(--border);
  background: var(--panel-strong);
}

.detail-header p,
.detail-header h2,
h3 {
  margin: 0;
}

.detail-header p {
  color: var(--muted);
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-header h2 {
  margin-top: 10px;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text);
}

.status-badge {
  display: inline-flex;
  margin-top: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.status-badge.outdated {
  background: rgba(180, 83, 9, 0.12);
  color: #b45309;
}

.status-badge.synced {
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
}

.detail-panel {
  display: grid;
  gap: 16px;
}

.detail-panel + .detail-panel {
  border-top: 1px solid var(--border);
}

label {
  display: grid;
  gap: 8px;
  color: var(--text);
  font-size: 0.85rem;
  font-weight: 600;
}

input,
textarea,
select {
  width: 100%;
  min-height: 38px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background-color: var(--app-bg);
  color: var(--text);
  font: inherit;
  font-size: 0.9rem;
  transition: all 0.2s ease;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.02);
}

select option {
  background-color: var(--panel);
  color: var(--text);
  padding: 8px;
  font-size: 0.9rem;
}

input:focus,
textarea:focus,
select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  background-color: #ffffff;
}

textarea {
  resize: vertical;
  line-height: 1.5;
}

.agent-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

button {
  min-height: 38px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

button:hover {
  border-color: var(--accent-border);
  background: var(--app-bg);
  color: var(--accent);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
}

button:active {
  transform: translateY(1px);
  box-shadow: none;
}

button.danger {
  color: #b42318;
  border-color: rgba(180, 35, 24, 0.2);
  background: rgba(180, 35, 24, 0.05);
}

button.danger:hover {
  background: rgba(180, 35, 24, 0.1);
  border-color: rgba(180, 35, 24, 0.3);
}

.agent-result {
  margin: 0;
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #f8fafc;
  color: var(--text);
  font-size: 0.85rem;
  line-height: 1.5;
  white-space: pre-wrap;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04);
}

.edge-meta {
  display: grid;
  gap: 10px;
  margin: 0;
}

.edge-meta div {
  display: grid;
  gap: 4px;
}

dt {
  color: var(--muted);
  font-size: 0.76rem;
}

dd {
  margin: 0;
}

.empty-state {
  align-self: start;
  color: var(--muted);
}

.empty-state p {
  margin: 0 0 6px;
  color: var(--text);
  font-weight: 700;
}

@media (max-width: 920px) {
  .detail-sidebar {
    border-left: 0;
    border-top: 1px solid var(--border);
  }
}
</style>
