<script setup lang="ts">
import { computed } from 'vue'
import type { CharacterCardDto, StructureOutputDto } from '../../api/graphApi'

const props = defineProps<{
  output: StructureOutputDto
}>()

const emit = defineEmits<{
  createNode: [payload: { nodeType: 'character'; title: string; content: string; tags: string[] }]
}>()

const sortedPlot = computed(() => {
  return [...props.output.plot_outline].sort((a, b) => a.order - b.order)
})

function handleAdoptCharacter(card: CharacterCardDto) {
  /* 角色节点正文沿用 one_liner + motivation, 关系单独写在末尾, 便于用户继续编辑。 */
  const relationshipsText = card.key_relationships.length
    ? `\n\n关键关系：${card.key_relationships.join('、')}`
    : ''
  const content = `${card.one_liner}\n\n动机：${card.motivation}${relationshipsText}`

  emit('createNode', {
    nodeType: 'character',
    title: card.name,
    content,
    tags: ['AI 整理', '角色'],
  })
}
</script>

<template>
  <article class="agent-card structure">
    <header class="agent-card__header">
      <span class="agent-card__badge">🗂 Structure</span>
      <h4>多节点结构整理</h4>
    </header>

    <p v-if="output.summary" class="agent-card__summary">{{ output.summary }}</p>

    <section v-if="output.character_cards.length" class="agent-card__section">
      <h5>角色卡</h5>
      <ul class="agent-card__characters">
        <li v-for="(card, idx) in output.character_cards" :key="idx">
          <header>
            <strong>{{ card.name }}</strong>
            <button type="button" class="agent-card__adopt" @click="handleAdoptCharacter(card)">
              + 添加为角色节点
            </button>
          </header>
          <p class="agent-card__char-line">{{ card.one_liner }}</p>
          <dl class="agent-card__char-detail">
            <div>
              <dt>动机</dt>
              <dd>{{ card.motivation }}</dd>
            </div>
            <div v-if="card.key_relationships.length">
              <dt>关键关系</dt>
              <dd>{{ card.key_relationships.join('、') }}</dd>
            </div>
          </dl>
        </li>
      </ul>
    </section>

    <section v-if="output.relationship_graph.length" class="agent-card__section">
      <h5>关系图</h5>
      <ul class="agent-card__relations">
        <li v-for="(rel, idx) in output.relationship_graph" :key="idx">
          <span class="agent-card__rel-node">{{ rel.source }}</span>
          <span class="agent-card__rel-arrow">→ {{ rel.relation }} →</span>
          <span class="agent-card__rel-node">{{ rel.target }}</span>
        </li>
      </ul>
    </section>

    <section v-if="sortedPlot.length" class="agent-card__section">
      <h5>剧情大纲</h5>
      <ol class="agent-card__plot">
        <li v-for="beat in sortedPlot" :key="beat.order">
          <header>
            <strong>{{ beat.title }}</strong>
            <span v-if="beat.involved_characters.length" class="agent-card__plot-cast">
              {{ beat.involved_characters.join('、') }}
            </span>
          </header>
          <p>{{ beat.summary }}</p>
        </li>
      </ol>
    </section>

    <p
      v-if="!output.character_cards.length && !output.relationship_graph.length && !sortedPlot.length"
      class="agent-card__empty"
    >
      没有可以整理的内容，请先在画布上多选若干节点。
    </p>

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
  background: #ede9fe;
  color: #5b21b6;
  font-size: 0.72rem;
  font-weight: 600;
}

.agent-card__summary {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--app-bg);
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

.agent-card__characters {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-card__characters li {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #ffffff;
}

.agent-card__characters header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.agent-card__char-line {
  margin: 0 0 8px;
  color: var(--text);
  font-size: 0.86rem;
  line-height: 1.5;
}

.agent-card__char-detail {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.agent-card__char-detail div {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 8px;
  align-items: baseline;
}

.agent-card__char-detail dt {
  margin: 0;
  color: var(--muted);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.agent-card__char-detail dd {
  margin: 0;
  color: var(--text);
  font-size: 0.82rem;
  line-height: 1.5;
}

.agent-card__adopt {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--accent-border);
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: none;
}

.agent-card__adopt:hover {
  background: #ffffff;
  border-color: var(--accent);
}

.agent-card__relations {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.agent-card__relations li {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--app-bg);
  font-size: 0.82rem;
}

.agent-card__rel-node {
  font-weight: 600;
  color: var(--text);
}

.agent-card__rel-arrow {
  color: #5b21b6;
  font-weight: 600;
  font-size: 0.78rem;
}

.agent-card__plot {
  margin: 0;
  padding: 0 0 0 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-card__plot li {
  padding-left: 4px;
}

.agent-card__plot header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.agent-card__plot-cast {
  color: var(--muted);
  font-size: 0.74rem;
}

.agent-card__plot p {
  margin: 0;
  color: var(--text);
  font-size: 0.82rem;
  line-height: 1.5;
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