<script setup lang="ts">
import { computed } from 'vue'
import type { InspirationOutputDto, SuggestedNodeDto } from '../../api/graphApi'
import type { CreativeNodeType } from '../../types/node'

const props = defineProps<{
  output: InspirationOutputDto
}>()

const emit = defineEmits<{
  createNode: [payload: { nodeType: CreativeNodeType; title: string; content: string; tags: string[] }]
}>()

/* Agent schema 用宽松的 string 类型, 这里把它收敛回前端业务枚举, 未识别值降级为 idea。 */
const VALID_NODE_TYPES: ReadonlyArray<CreativeNodeType> = [
  'character', 'plot', 'worldbuilding', 'idea', 'research', 'structure',
]

function normalizeNodeType(raw: string): CreativeNodeType {
  return VALID_NODE_TYPES.includes(raw as CreativeNodeType) ? (raw as CreativeNodeType) : 'idea'
}

function handleAdopt(suggested: SuggestedNodeDto) {
  emit('createNode', {
    nodeType: normalizeNodeType(suggested.nodeType),
    title: suggested.title,
    content: suggested.reason,
    tags: ['AI 建议', 'Inspiration'],
  })
}

const hasContent = computed(
  () => props.output.summary || props.output.questions.length || props.output.missing_parts.length,
)
</script>

<template>
  <article class="agent-card inspiration">
    <header class="agent-card__header">
      <span class="agent-card__badge">💡 Inspiration</span>
      <h4>引导式提问</h4>
    </header>

    <p v-if="output.summary" class="agent-card__summary">{{ output.summary }}</p>

    <section v-if="output.questions.length" class="agent-card__section">
      <h5>引导你思考</h5>
      <ul class="agent-card__questions">
        <li v-for="(q, idx) in output.questions" :key="idx">{{ q }}</li>
      </ul>
    </section>

    <section v-if="output.missing_parts.length" class="agent-card__section">
      <h5>可能缺失的要素</h5>
      <ul class="agent-card__missing">
        <li v-for="(part, idx) in output.missing_parts" :key="idx">{{ part }}</li>
      </ul>
    </section>

    <section v-if="output.suggested_nodes.length" class="agent-card__section">
      <h5>建议补充的节点</h5>
      <ul class="agent-card__suggestions">
        <li v-for="(node, idx) in output.suggested_nodes" :key="idx">
          <div class="agent-card__suggestion-meta">
            <strong>{{ node.title }}</strong>
            <span class="agent-card__suggestion-type">{{ node.nodeType }}</span>
          </div>
          <p class="agent-card__suggestion-reason">{{ node.reason }}</p>
          <button type="button" class="agent-card__adopt" @click="handleAdopt(node)">
            + 添加到画布
          </button>
        </li>
      </ul>
    </section>

    <p v-if="!hasContent" class="agent-card__empty">本次 Agent 没有返回有效内容。</p>

    <footer v-if="output.boundary_notice" class="agent-card__footer">
      {{ output.boundary_notice }}
    </footer>
  </article>
</template>

<style scoped>
.agent-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--panel-strong);
}

.agent-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-card__header h4 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
}

.agent-card__badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 0.72rem;
  font-weight: 600;
}

.agent-card.inspiration .agent-card__badge {
  background: #fef3c7;
  color: #92400e;
}

.agent-card__summary {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--app-bg);
  color: var(--text);
  font-size: 0.86rem;
  line-height: 1.55;
}

.agent-card__section h5 {
  margin: 0 0 6px;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.agent-card__questions,
.agent-card__missing,
.agent-card__suggestions {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-card__questions li,
.agent-card__missing li {
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--app-bg);
  color: var(--text);
  font-size: 0.85rem;
  line-height: 1.5;
}

.agent-card__questions li::before {
  content: '? ';
  color: var(--accent);
  font-weight: 700;
}

.agent-card__missing li::before {
  content: '! ';
  color: #b45309;
  font-weight: 700;
}

.agent-card__suggestions li {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #ffffff;
}

.agent-card__suggestion-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.agent-card__suggestion-meta strong {
  color: var(--text);
  font-size: 0.9rem;
}

.agent-card__suggestion-type {
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.72rem;
  font-weight: 600;
}

.agent-card__suggestion-reason {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.5;
}

.agent-card__adopt {
  align-self: flex-start;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--accent-border);
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: none;
}

.agent-card__adopt:hover {
  background: #ffffff;
  border-color: var(--accent);
}

.agent-card__empty {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.agent-card__footer {
  margin: 0;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  color: var(--muted);
  font-size: 0.74rem;
  line-height: 1.45;
}
</style>