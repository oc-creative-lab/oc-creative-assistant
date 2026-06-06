<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'
import { useGraphStore } from '../../stores/useGraphStore'
import { deleteNode as apiDeleteNode } from '../../api/projectApi'

/**
 * Characters列表。
 *
 * Notion 风格卡片网格，数据源为 character sub-graph 的节点；角色关系不画 Vue Flow
 * 连线，改在详情页以标签展示。点击卡片进入 CharacterCardDetail。
 */
const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const graphStore = useGraphStore()
const { characterGraphId } = storeToRefs(projectStore)
const { nodes, isLoading, error } = storeToRefs(graphStore)

watch(
  characterGraphId,
  (id) => {
    if (id) void graphStore.load(id, true)
  },
  { immediate: true },
)

function openCharacter(charId: string) {
  router.push(`/workspace/${route.params.projectId}/characters/${charId}`)
}

async function removeCharacter(nodeId: string) {
  if (!window.confirm('Delete this character? This cannot be undone.')) return
  try {
    await apiDeleteNode(String(route.params.projectId), nodeId)
  } catch (e) {
    console.error('Failed to delete character', e)
  } finally {
    if (characterGraphId.value) await graphStore.load(characterGraphId.value, true)
  }
}
</script>

<template>
  <section class="card-list">
    <header class="card-list__header">
      <h2>Characters</h2>
      <span class="card-list__hint">Relations show as tags · open a card to edit fields</span>
    </header>

    <p v-if="error" class="card-list__error">{{ error }}</p>
    <p v-else-if="isLoading" class="card-list__hint">Loading…</p>
    <p v-else-if="nodes.length === 0" class="card-list__hint">
      No characters yet — extract them in chat, or add from Story / Worldbuilding.
    </p>

    <div v-else class="card-list__grid">
      <article
        v-for="node in nodes"
        :key="node.id"
        class="char-card"
        @click="openCharacter(node.id)"
      >
        <button
          type="button"
          class="char-card__delete"
          title="Delete character"
          @click.stop="removeCharacter(node.id)"
        >
          ✕
        </button>
        <h3 class="char-card__name">{{ node.title }}</h3>
        <p class="char-card__content">{{ node.content || 'No summary' }}</p>
        <footer v-if="node.tags && node.tags.length" class="char-card__tags">
          <span v-for="tag in node.tags" :key="tag" class="char-card__tag">{{ tag }}</span>
        </footer>
      </article>
    </div>
  </section>
</template>

<style scoped>
.card-list {
  padding: 24px;
  min-height: 100%;
  box-sizing: border-box;
  background:
    radial-gradient(circle at 20% 0%, rgba(167, 139, 250, 0.1), transparent 60%),
    var(--panel);
}
.card-list__header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 18px;
}
.card-list__hint {
  color: var(--muted, #888);
  font-size: 13px;
}
.card-list__error {
  color: #dc2626;
}
.card-list__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.char-card {
  position: relative;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 120px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.char-card__delete {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted, #888);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}
.char-card:hover .char-card__delete {
  opacity: 1;
}
.char-card__delete:hover {
  background: #fee2e2;
  color: #dc2626;
}
.char-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.12);
}
.char-card__name {
  font-size: 16px;
  font-weight: 600;
}
.char-card__content {
  flex: 1;
  color: #666;
  font-size: 13px;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
}
.char-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.char-card__tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-deep);
}
</style>
