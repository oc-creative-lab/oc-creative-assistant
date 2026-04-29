<script setup lang="ts">
import type { ProjectGroup } from '../../types/workspace'

defineProps<{
  // groups 由 AppShell 从当前 graph nodes 派生，左侧不维护独立副本。
  groups: ProjectGroup[]
  selectedNodeId: string
}>()

defineEmits<{
  // 点击条目只上抛 id，选中态统一交给 AppShell 更新。
  selectNode: [nodeId: string]
}>()
</script>

<template>
  <aside class="project-sidebar">
    <header class="sidebar-header">
      <h2>&#39033;&#30446;&#38754;&#26495;</h2>
      <input
        type="search"
        placeholder="&#25628;&#32034;&#35282;&#33394;&#12289;&#21095;&#24773;&#12289;&#36164;&#26009;..."
        aria-label="&#25628;&#32034;&#39033;&#30446;&#20869;&#23481;"
      />
    </header>

    <section class="group-list" aria-label="&#39033;&#30446;&#20998;&#32452;">
      <article v-for="group in groups" :key="group.id" class="project-group">
        <h3>{{ group.title }}</h3>
        <button
          v-for="item in group.items"
          :key="item.id"
          class="project-item"
          :class="{ active: item.id === selectedNodeId }"
          type="button"
          @click="$emit('selectNode', item.id)"
        >
          <span>{{ item.title }}</span>
          <small>{{ item.meta }}</small>
        </button>
      </article>
    </section>
  </aside>
</template>

<style scoped>
.project-sidebar {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--panel);
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
}

h2,
h3 {
  margin: 0;
}

h2 {
  font-size: 1rem;
}

input {
  width: 100%;
  min-height: 34px;
  margin-top: 12px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel-strong);
  color: var(--text);
}

.group-list {
  min-height: 0;
  overflow: auto;
  padding: 12px;
}

.project-group + .project-group {
  margin-top: 16px;
}

h3 {
  padding: 0 4px 8px;
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 700;
}

.project-item {
  width: 100%;
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.project-item:hover,
.project-item.active {
  border-color: var(--accent-border);
  background: var(--accent-soft);
}

.project-item span {
  font-weight: 650;
}

.project-item small {
  color: var(--muted);
  font-size: 0.76rem;
}

@media (max-width: 920px) {
  .project-sidebar {
    max-height: 300px;
    border-right: 0;
    border-bottom: 1px solid var(--border);
  }
}
</style>
