<script setup lang="ts">
import type { ResearchOutputDto } from '../../api/graphApi'

defineProps<{
  output: ResearchOutputDto
}>()
</script>

<template>
  <article class="agent-card research">
    <header class="agent-card__header">
      <span class="agent-card__badge">📚 Research</span>
      <h4>资料检索</h4>
    </header>

    <p v-if="output.summary" class="agent-card__summary">{{ output.summary }}</p>

    <section v-if="output.references.length" class="agent-card__section">
      <h5>引用条目</h5>
      <ul class="agent-card__references">
        <li v-for="(ref, idx) in output.references" :key="idx">
          <header>
            <strong>{{ ref.title }}</strong>
            <span class="agent-card__ref-source">{{ ref.source }}</span>
          </header>
          <p class="agent-card__ref-snippet">"{{ ref.snippet }}"</p>
          <p v-if="ref.relevance" class="agent-card__ref-relevance">{{ ref.relevance }}</p>
        </li>
      </ul>
    </section>

    <section v-if="output.suggested_tags.length" class="agent-card__section">
      <h5>建议补充的标签</h5>
      <div class="agent-card__tags">
        <span v-for="(tag, idx) in output.suggested_tags" :key="idx" class="agent-card__tag">
          {{ tag }}
        </span>
      </div>
    </section>

    <p v-if="!output.references.length && !output.suggested_tags.length" class="agent-card__empty">
      项目内还没有可引用的资料。先创建 research 节点或继续完善已有内容。
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
  background: #dbeafe;
  color: #1e40af;
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

.agent-card__references {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-card__references li {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #ffffff;
}

.agent-card__references header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.agent-card__ref-source {
  padding: 2px 8px;
  border-radius: 6px;
  background: #dbeafe;
  color: #1e40af;
  font-size: 0.72rem;
  font-weight: 600;
}

.agent-card__ref-snippet {
  margin: 0;
  color: var(--text);
  font-size: 0.84rem;
  line-height: 1.5;
  font-style: italic;
}

.agent-card__ref-relevance {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.agent-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.agent-card__tag {
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 0.78rem;
  font-weight: 600;
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