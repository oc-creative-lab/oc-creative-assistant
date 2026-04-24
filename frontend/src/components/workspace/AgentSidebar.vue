<script setup lang="ts">
import { computed, ref } from 'vue'
import { mockAgentSuggestions } from '../../mocks/workspaceMock'
import type { AgentMode, ProjectItem } from '../../types/workspace'

defineProps<{
  currentNode: ProjectItem
}>()

const modes: Array<{ id: AgentMode; label: string }> = [
  { id: 'inspiration', label: '\u7075\u611f\u5f15\u5bfc' },
  { id: 'research', label: '\u8d44\u6599\u67e5\u8be2' },
  { id: 'structure', label: '\u7ed3\u6784\u7f16\u6392' },
]

const activeMode = ref<AgentMode>('inspiration')
const suggestions = computed(() => mockAgentSuggestions[activeMode.value])
</script>

<template>
  <aside class="agent-sidebar">
    <section class="current-node-card">
      <p>&#24403;&#21069;&#33410;&#28857;</p>
      <h2>{{ currentNode.title }}</h2>
      <span>{{ currentNode.kind }} / {{ currentNode.meta }}</span>
    </section>

    <section class="agent-panel">
      <div class="agent-tabs" aria-label="AI Agent &#27169;&#24335;">
        <button
          v-for="mode in modes"
          :key="mode.id"
          type="button"
          :class="{ active: mode.id === activeMode }"
          @click="activeMode = mode.id"
        >
          {{ mode.label }}
        </button>
      </div>

      <div class="suggestion-list">
        <article v-for="suggestion in suggestions" :key="suggestion.id" class="suggestion-card">
          <h3>{{ suggestion.title }}</h3>
          <p>{{ suggestion.body }}</p>
        </article>
      </div>
    </section>

    <footer class="agent-actions">
      <button type="button">&#37319;&#32435;&#20026;&#26032;&#33410;&#28857;</button>
      <button type="button">&#20889;&#20837;&#24403;&#21069;&#33410;&#28857;</button>
      <button type="button">&#24573;&#30053;</button>
    </footer>
  </aside>
</template>

<style scoped>
.agent-sidebar {
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  border-left: 1px solid var(--border);
  background: var(--panel);
}

.current-node-card,
.agent-panel,
.agent-actions {
  padding: 16px;
}

.current-node-card {
  border-bottom: 1px solid var(--border);
  background: var(--panel-strong);
}

.current-node-card p,
.current-node-card h2 {
  margin: 0;
}

.current-node-card p {
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 700;
}

.current-node-card h2 {
  margin-top: 8px;
  font-size: 1.2rem;
}

.current-node-card span {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: 0.86rem;
}

.agent-panel {
  min-height: 0;
  overflow: auto;
}

.agent-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.agent-tabs button,
.agent-actions button {
  min-height: 32px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel-strong);
  color: var(--text);
  cursor: pointer;
}

.agent-tabs button {
  padding: 0 6px;
  color: var(--muted);
  font-size: 0.82rem;
}

.agent-tabs button.active {
  border-color: var(--accent-border);
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 700;
}

.suggestion-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.suggestion-card {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel-strong);
}

.suggestion-card h3,
.suggestion-card p {
  margin: 0;
}

.suggestion-card h3 {
  font-size: 0.96rem;
}

.suggestion-card p {
  margin-top: 6px;
  color: var(--muted);
  font-size: 0.88rem;
}

.agent-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  border-top: 1px solid var(--border);
  background: var(--panel-strong);
}

@media (max-width: 920px) {
  .agent-sidebar {
    border-left: 0;
    border-top: 1px solid var(--border);
  }
}
</style>
