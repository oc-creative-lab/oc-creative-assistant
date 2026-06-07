<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { loadSubgraph, saveSubgraph } from '../../api/graphApi'
import { useProjectStore } from '../../stores/useProjectStore'
import { useGraphStore } from '../../stores/useGraphStore'
import { graphDtoToSnapshot, snapshotToSaveDto } from '../../utils/graphTransform'
import { createCreativeNode } from '../../utils/nodeFactory'

/**
 * Characters list (first_revision decision 2, a user-approved deviation from the proposal).
 *
 * A Notion-style card grid sourced from the nodes of the character sub-graph;
 * character relations are not drawn as Vue Flow connecting lines but shown as
 * tags on the detail page. Clicking a card opens CharacterCardDetail.
 */
const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const graphStore = useGraphStore()
const { characterGraphId } = storeToRefs(projectStore)
const { nodes, isLoading, error } = storeToRefs(graphStore)

const createOpen = ref(false)
const createName = ref('')
const createSummary = ref('')
const isCreating = ref(false)
const createError = ref('')

watch(
  characterGraphId,
  (id) => {
    if (id) void graphStore.load(id)
  },
  { immediate: true },
)

function openCharacter(charId: string) {
  router.push(`/workspace/${route.params.projectId}/characters/${charId}`)
}

function openCreate() {
  createName.value = ''
  createSummary.value = ''
  createError.value = ''
  createOpen.value = true
}

function closeCreate() {
  if (isCreating.value) return
  createOpen.value = false
}

async function handleCreate() {
  const graphId = characterGraphId.value
  const projectId = String(route.params.projectId)
  const name = createName.value.trim()
  if (!graphId || !name || isCreating.value) return

  isCreating.value = true
  createError.value = ''
  try {
    const graph = await loadSubgraph(graphId)
    const snapshot = graphDtoToSnapshot(graph)
    const index = snapshot.nodes.length + 1
    const newNode = createCreativeNode('character', index, {
      x: 40 + (index % 4) * 220,
      y: 40 + Math.floor(index / 4) * 160,
    })
    newNode.data.title = name
    newNode.data.content = createSummary.value.trim()

    snapshot.nodes.push(newNode)
    await saveSubgraph(graphId, snapshotToSaveDto(snapshot))
    await graphStore.load(graphId, true)
    createOpen.value = false
    router.push(`/workspace/${projectId}/characters/${newNode.id}`)
  } catch (e) {
    createError.value = e instanceof Error ? e.message : 'Failed to create character'
  } finally {
    isCreating.value = false
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

    <div v-else class="card-list__grid">
      <article
        v-for="node in nodes"
        :key="node.id"
        class="char-card"
        @click="openCharacter(node.id)"
      >
        <h3 class="char-card__name">{{ node.title }}</h3>
        <p class="char-card__content">{{ node.content || 'No summary' }}</p>
        <footer v-if="node.tags && node.tags.length" class="char-card__tags">
          <span v-for="tag in node.tags" :key="tag" class="char-card__tag">{{ tag }}</span>
        </footer>
      </article>
      <button type="button" class="char-card char-card--create" @click="openCreate">
        <span class="char-card__plus">+</span>
        <span class="char-card__create-label">New character</span>
      </button>
    </div>

    <div v-if="createOpen" class="card-list__modal" @click.self="closeCreate">
      <form class="create-card" @submit.prevent="handleCreate">
        <h3 class="create-card__title">New character</h3>
        <label class="create-card__field">
          <span>Name</span>
          <input v-model="createName" type="text" placeholder="Character name" autofocus />
        </label>
        <label class="create-card__field">
          <span>Summary</span>
          <textarea v-model="createSummary" rows="3" placeholder="A short description (optional)" />
        </label>
        <p v-if="createError" class="create-card__error">{{ createError }}</p>
        <div class="create-card__actions">
          <button type="button" class="create-card__cancel" @click="closeCreate">Cancel</button>
          <button type="submit" class="create-card__save" :disabled="!createName.trim() || isCreating">
            {{ isCreating ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<style scoped>
.card-list {
  padding: 24px;
}
.card-list__header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 18px;
}
.card-list__hint {
  color: var(--muted, #888);
  font-size: 13px;
}
.card-list__error {
  color: #dc2626;
}
.card-list__modal {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(28, 25, 23, 0.28);
}
.create-card {
  width: min(100%, 360px);
  padding: 20px;
  border-radius: 14px;
  border: 1px solid var(--border, #e5e7eb);
  background: var(--panel-strong, #fff);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.create-card__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}
.create-card__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}
.create-card__field input,
.create-card__field textarea {
  padding: 8px 10px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
  color: var(--text);
  resize: vertical;
}
.create-card__error {
  margin: 0;
  font-size: 12px;
  color: #dc2626;
}
.create-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.create-card__cancel,
.create-card__save {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.create-card__cancel {
  border: 1px solid var(--border, #ddd);
  background: transparent;
  color: var(--text-soft);
}
.create-card__save {
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
}
.create-card__save:disabled {
  opacity: 0.55;
  cursor: wait;
}
.card-list__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.char-card {
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
.char-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.12);
}
.char-card--create {
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-style: dashed;
  background: transparent;
  color: var(--muted);
}
.char-card--create:hover {
  color: var(--accent);
  background: var(--accent-soft);
}
.char-card__plus {
  font-size: 28px;
  line-height: 1;
}
.char-card__create-label {
  font-size: 13px;
  font-weight: 600;
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
