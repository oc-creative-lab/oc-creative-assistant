<script setup lang="ts">
import { computed } from 'vue'
import type { AgentStagingItemDto } from '../../api/chatApi'

/**
 * staging 单项卡片。
 *
 * 展示 Agent 提议的画布变更, 用户选择 accept / reject 推进状态机。
 * payload 渲染逻辑只覆盖 create_node 这一最常见类型, 其它类型用 JSON 兜底。
 */
const props = defineProps<{
  item: AgentStagingItemDto
}>()

const emit = defineEmits<{
  resolve: [stagingId: string, action: 'accept' | 'reject']
}>()

const CHANGE_TYPE_LABELS: Record<string, string> = {
  create_node: 'New node',
  create_edge: 'New relation',
  update_node: 'Update node',
  delete_node: 'Delete node',
  delete_edge: 'Delete relation',
}

const titleHint = computed(() => {
  const type = props.item.change_type
  if (type === 'create_node') {
    const payload = props.item.payload as { title?: string; node_type?: string }
    const title = payload.title ?? 'Untitled node'
    return payload.node_type ? `${title} · ${payload.node_type}` : title
  }
  return CHANGE_TYPE_LABELS[type] ?? type
})

const contentPreview = computed(() => {
  const item = props.item
  const payload = (item.payload ?? {}) as Record<string, unknown>

  if (item.change_type === 'create_node') {
    return (payload.content as string | undefined) ?? ''
  }

  if (item.change_type === 'create_edge') {
    const source = (payload.source as string | undefined) ?? '?'
    const target = (payload.target as string | undefined) ?? '?'
    const relation = (payload.relation_type as string | undefined) ?? 'related to'
    return `${source}  →  ${target}\nRelation: ${relation}`
  }

  if (item.change_type === 'update_node') {
    const fields = ['title', 'content', 'node_type']
      .filter((key) => payload[key] !== undefined)
      .map((key) => `${key}: ${payload[key]}`)
    return fields.join('\n')
  }

  if (item.change_type === 'delete_node') {
    return item.target_id ? `Target node ID: ${item.target_id}` : ''
  }

  if (item.change_type === 'delete_edge') {
    if (item.target_id) {
      return `Target relation ID: ${item.target_id}`
    }
    const source = (payload.source as string | undefined) ?? '?'
    const target = (payload.target as string | undefined) ?? '?'
    return `${source}  →  ${target}`
  }

  return ''
})

const isPending = computed(() => props.item.status === 'pending')
</script>

<template>
  <article class="staging-item" :class="item.status">
    <header class="staging-item__head">
      <span class="staging-item__type">{{ item.change_type }}</span>
      <span class="staging-item__status">{{ item.status }}</span>
    </header>
    <h4 class="staging-item__title">{{ titleHint }}</h4>
    <p v-if="contentPreview" class="staging-item__content">{{ contentPreview }}</p>
    <p v-if="item.reasoning" class="staging-item__reason">{{ item.reasoning }}</p>

    <footer v-if="isPending" class="staging-item__actions">
      <button type="button" class="accept" @click="emit('resolve', item.id, 'accept')">
        Accept
      </button>
      <button type="button" class="reject" @click="emit('resolve', item.id, 'reject')">
        Reject
      </button>
    </footer>
  </article>
</template>

<style scoped>
.staging-item {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--panel);
}

.staging-item.accepted {
  background: #f0fdfa;
  border-color: #ccfbf1;
}

.staging-item.rejected {
  background: #f9fafb;
  border-color: #e5e7eb;
  opacity: 0.7;
}

.staging-item__head {
  display: flex;
  justify-content: space-between;
  font-size: 0.74rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.staging-item__title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
}

.staging-item__content {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.staging-item__reason {
  margin: 0;
  padding-top: 6px;
  border-top: 1px dashed rgba(0, 0, 0, 0.06);
  font-size: 0.78rem;
  color: var(--muted);
}

.staging-item__actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.staging-item__actions button {
  flex: 1;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.84rem;
  font-weight: 500;
  cursor: pointer;
}

.staging-item__actions .accept {
  color: #0f766e;
  border-color: #99f6e4;
  background: #ecfdf5;
}

.staging-item__actions .accept:hover {
  background: #d1fae5;
}

.staging-item__actions .reject {
  color: #b91c1c;
  border-color: #fecaca;
  background: #fef2f2;
}

.staging-item__actions .reject:hover {
  background: #fee2e2;
}
</style>