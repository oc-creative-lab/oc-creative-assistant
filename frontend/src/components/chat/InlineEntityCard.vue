<script setup lang="ts">
import { ref } from 'vue'
import type { AppliedEntityDto } from '../../api/chatApi'

/**
 * Inline entity card in the chat.
 *
 * The backend already persists extracted entities by default, so this only does
 * "notify + optional edit/undo":
 * - Collapsed: a single line like "✅ Added Character X"; if not expanded it stays added by default;
 * - Expanded: edit title/body -> save (update), or reject (delete) to undo this addition.
 */
const props = defineProps<{ item: AppliedEntityDto }>()
const emit = defineEmits<{
  edit: [nodeId: string, patch: { title?: string; content?: string }]
  remove: [nodeId: string]
}>()

const NODE_TYPE_LABELS: Record<string, string> = {
  character: 'Character',
  worldbuilding: 'World',
  plot: 'Story',
  idea: 'Idea',
  research: 'Research',
  structure: 'Structure',
}

const expanded = ref(false)
const removed = ref(false)
const title = ref(props.item.title)
const content = ref(props.item.content)
const saveState = ref('')

const verb = props.item.change_type === 'update_node' ? 'Updated' : 'Added'
const icon = props.item.change_type === 'update_node' ? '✏️' : '✅'
const typeLabel = NODE_TYPE_LABELS[props.item.node_type] ?? props.item.node_type

async function handleSave() {
  saveState.value = 'Saving…'
  try {
    emit('edit', props.item.node_id, { title: title.value, content: content.value })
    saveState.value = 'Saved'
  } catch {
    saveState.value = 'Save failed'
  }
}

function handleRemove() {
  removed.value = true
  emit('remove', props.item.node_id)
}
</script>

<template>
  <div v-if="!removed" class="inline-card" :class="{ 'inline-card--open': expanded }">
    <button type="button" class="inline-card__chip" @click="expanded = !expanded">
      <span>{{ icon }} {{ verb }} {{ typeLabel }} · {{ title }}</span>
      <span class="inline-card__caret">{{ expanded ? '▲' : '▼' }}</span>
    </button>

    <div v-if="expanded" class="inline-card__editor">
      <input v-model="title" class="inline-card__title" placeholder="Title" />
      <textarea v-model="content" rows="3" class="inline-card__content" placeholder="Body"></textarea>
      <div class="inline-card__actions">
        <button type="button" class="inline-card__save" @click="handleSave">Save</button>
        <button type="button" class="inline-card__remove" @click="handleRemove">Discard</button>
        <span class="inline-card__state">{{ saveState }}</span>
      </div>
    </div>
  </div>
  <div v-else class="inline-card inline-card--removed">Discarded “{{ title }}”</div>
</template>

<style scoped>
.inline-card {
  margin-top: 6px;
  border: 1px solid var(--accent-soft);
  border-radius: 10px;
  background: var(--panel);
  overflow: hidden;
}
.inline-card--open {
  border-color: var(--accent);
  background: #fff;
}
.inline-card__chip {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-soft);
  text-align: left;
}
.inline-card--open .inline-card__chip {
  color: var(--accent-deep);
}
.inline-card__caret {
  font-size: 10px;
  opacity: 0.6;
}
.inline-card__editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid #eee;
}
.inline-card__title,
.inline-card__content {
  padding: 6px 8px;
  border: 1px solid var(--border, #ddd);
  border-radius: 6px;
  font: inherit;
  resize: vertical;
}
.inline-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.inline-card__save {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
  font-size: 12px;
}
.inline-card__remove {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid #fca5a5;
  background: #fff;
  color: #dc2626;
  cursor: pointer;
  font-size: 12px;
}
.inline-card__state {
  font-size: 12px;
  color: var(--muted, #888);
}
.inline-card--removed {
  margin-top: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--muted, #999);
  background: #f3f4f6;
  border-radius: 10px;
}
</style>
