<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { getNodeFields, saveNodeFields } from '../../../api/projectApi'
import DocFieldsEditor, { type DocFieldRow } from '../DocFieldsEditor.vue'
import type { CreativeFlowNode } from '../../../types/node'

const SAVE_DEBOUNCE_MS = 400

const props = defineProps<{
  node: CreativeFlowNode | null
  projectId: string
}>()

const emit = defineEmits<{
  update: [patch: { title?: string; content?: string }]
}>()

const title = ref('')
const fieldRows = ref<DocFieldRow[]>([])
const isLoadingFields = ref(false)
const isHydrating = ref(false)
const saveState = ref('')

const isEmpty = computed(() => !props.node)

let saveTimer: ReturnType<typeof setTimeout> | null = null
let isSaving = false
let saveQueued = false

function fieldsToContent(rows: DocFieldRow[]): string {
  const fields = rowsToFields(rows)
  const keyed = Object.entries(fields)
    .filter(([key, value]) => key.trim() && value.trim())
    .map(([key, value]) => `${key}\n${value}`)
  if (keyed.length > 0) return keyed.join('\n\n')
  const firstValue = rows.find((row) => row.value.trim())?.value.trim()
  return firstValue ?? ''
}

function rowsToFields(rows: DocFieldRow[]): Record<string, string> {
  const fields: Record<string, string> = {}
  for (const row of rows) {
    const key = row.key.trim()
    if (!key) continue
    fields[key] = row.value
  }
  return fields
}

async function loadFields(node: CreativeFlowNode) {
  if (!props.projectId) {
    fieldRows.value = [{ key: '', value: node.data.content ?? '' }]
    return
  }

  isLoadingFields.value = true
  try {
    const result = await getNodeFields(props.projectId, node.id)
    const entries = Object.entries(result.fields)
    if (entries.length > 0) {
      fieldRows.value = entries.map(([key, value]) => ({ key, value }))
    } else if (node.data.content.trim()) {
      fieldRows.value = [{ key: '', value: node.data.content }]
    } else {
      fieldRows.value = [{ key: '', value: '' }]
    }
  } catch {
    fieldRows.value = node.data.content.trim()
      ? [{ key: '', value: node.data.content }]
      : [{ key: '', value: '' }]
  } finally {
    isLoadingFields.value = false
  }
}

watch(
  () => props.node?.id,
  async (nodeId) => {
    const node = props.node
    if (saveTimer) {
      clearTimeout(saveTimer)
      saveTimer = null
    }
    isHydrating.value = true
    title.value = node?.data.title ?? ''
    if (node && nodeId) await loadFields(node)
    else fieldRows.value = []
    isHydrating.value = false
    saveState.value = ''
  },
  { immediate: true },
)

function scheduleSave() {
  if (!props.node || !props.projectId || isLoadingFields.value || isHydrating.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    saveTimer = null
    void persistAll()
  }, SAVE_DEBOUNCE_MS)
}

function flushSave() {
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  void persistAll()
}

async function persistAll() {
  if (!props.node || !props.projectId || isLoadingFields.value || isHydrating.value) return
  if (isSaving) {
    saveQueued = true
    return
  }

  const node = props.node
  const nextTitle = title.value.trim() || 'Untitled'
  const fields = rowsToFields(fieldRows.value)
  const content = fieldsToContent(fieldRows.value)
  const titleChanged = nextTitle !== node.data.title
  const contentChanged = content !== (node.data.content ?? '')

  if (!titleChanged && !contentChanged) return

  isSaving = true
  saveState.value = 'Saving…'
  try {
    await saveNodeFields(props.projectId, node.id, fields)
    const patch: { title?: string; content?: string } = {}
    if (titleChanged) patch.title = nextTitle
    if (contentChanged) patch.content = content
    if (Object.keys(patch).length > 0) emit('update', patch)
    saveState.value = 'Saved'
  } catch {
    saveState.value = 'Save failed'
  } finally {
    isSaving = false
    if (saveQueued) {
      saveQueued = false
      void persistAll()
    }
  }
}

watch([title, fieldRows], () => {
  scheduleSave()
}, { deep: true })

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
})
</script>

<template>
  <section class="world-doc">
    <div v-if="isEmpty" class="world-doc__empty">
      <p>Select a note from the folder tree, or create a new root note.</p>
    </div>

    <div v-else class="world-doc__surface">
      <div class="world-doc__head">
        <input
          v-model="title"
          class="world-doc__title"
          type="text"
          placeholder="Untitled"
          spellcheck="false"
          @blur="flushSave"
          @keydown.enter="($event.target as HTMLInputElement).blur()"
        />
        <span v-if="saveState" class="world-doc__save">{{ saveState }}</span>
      </div>

      <div v-if="isLoadingFields" class="world-doc__loading">Loading…</div>

      <DocFieldsEditor v-else v-model="fieldRows" @blur="flushSave" />
    </div>
  </section>
</template>

<style scoped>
.world-doc {
  height: 100%;
  min-height: 0;
}

.world-doc__empty {
  height: 100%;
  display: grid;
  place-items: center;
  padding: 24px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
  background: var(--paper);
}

.world-doc__surface {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 28px 20px 44px;
  position: relative;
  background: var(--paper);
  background-image:
    linear-gradient(var(--paper), var(--paper)),
    repeating-linear-gradient(
      to bottom,
      transparent 0,
      transparent 33px,
      rgba(28, 25, 23, 0.04) 33px,
      rgba(28, 25, 23, 0.04) 34px
    );
}

.world-doc__surface::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 28px;
  width: 1px;
  background: rgba(233, 130, 74, 0.22);
  pointer-events: none;
}

.world-doc__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 24px;
}

.world-doc__title {
  flex: 1;
  margin: 0;
  border: none;
  background: transparent;
  font-family: var(--font-display);
  font-size: 1.75rem;
  font-weight: 600;
  line-height: 1.25;
  color: var(--text);
  padding: 0;
}

.world-doc__title:focus {
  outline: none;
}

.world-doc__save {
  flex-shrink: 0;
  margin-top: 6px;
  font-size: 11px;
  color: var(--muted);
}

.world-doc__loading {
  color: var(--muted);
  font-size: 13px;
}
</style>
