<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'

/**
 * 工作台左侧导航（first_revision 阶段 3）。
 *
 * 从上到下：返回项目库、项目名 + 简介、三视图导航（故事线 / 角色卡 / 世界观）、
 * 种子版本。导航用 router-link，子视图按各自 graph_id 加载。
 */
const props = defineProps<{ projectId: string }>()

const projectStore = useProjectStore()
const { detail } = storeToRefs(projectStore)

const seedLabel = computed(() => {
  const seed = detail.value?.latest_seed
  if (!seed) return 'Seed — not generated'
  const time = seed.created_at ? new Date(seed.created_at) : null
  const timeLabel = time && !Number.isNaN(time.getTime()) ? ` · ${time.toLocaleString()}` : ''
  return `Seed v${seed.version}${timeLabel}`
})

const navItems = computed(() => [
  { to: `/workspace/${props.projectId}/overview`, icon: '◷', label: 'Overview' },
  { to: `/workspace/${props.projectId}/plot`, icon: '❧', label: 'Story' },
  { to: `/workspace/${props.projectId}/characters`, icon: '✦', label: 'Characters' },
  { to: `/workspace/${props.projectId}/world`, icon: '◍', label: 'Worldbuilding' },
])
</script>

<template>
  <aside class="workspace-sidebar">
    <router-link class="workspace-sidebar__back" to="/library">← Library</router-link>

    <div class="workspace-sidebar__meta">
      <h2 class="workspace-sidebar__name">{{ detail?.name ?? 'Loading…' }}</h2>
      <p class="workspace-sidebar__desc">{{ detail?.description || 'No description yet.' }}</p>
    </div>

    <nav class="workspace-sidebar__nav">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="workspace-sidebar__link"
        active-class="is-active"
      >
        <span class="workspace-sidebar__icon">{{ item.icon }}</span>
        {{ item.label }}
      </router-link>
    </nav>

    <div class="workspace-sidebar__seed">{{ seedLabel }}</div>
  </aside>
</template>

<style scoped>
.workspace-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 14px;
  border-right: 1px solid var(--border);
  background:
    radial-gradient(circle at 20% 0%, rgba(167, 139, 250, 0.1), transparent 60%),
    var(--panel);
  overflow: auto;
}
.workspace-sidebar__back {
  font-size: 13px;
  color: var(--muted);
  text-decoration: none;
  transition: color 0.15s;
}
.workspace-sidebar__back:hover {
  color: var(--accent);
}
.workspace-sidebar__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.workspace-sidebar__name {
  font-size: 16px;
  font-weight: 700;
}
.workspace-sidebar__desc {
  font-size: 12px;
  color: var(--muted, #888);
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.workspace-sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.workspace-sidebar__link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 11px;
  text-decoration: none;
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
  transition: background 0.16s, color 0.16s, transform 0.16s;
}
.workspace-sidebar__link:hover {
  background: var(--accent-soft);
  color: var(--accent-deep);
  transform: translateX(2px);
}
.workspace-sidebar__link.is-active {
  background: var(--grad-pill);
  color: #fff;
  box-shadow: 0 6px 16px rgba(139, 92, 246, 0.32);
}
.workspace-sidebar__icon {
  font-size: 16px;
}
.workspace-sidebar__seed {
  margin-top: auto;
  font-size: 12px;
  color: var(--muted, #aaa);
  padding: 8px 10px;
}
</style>
