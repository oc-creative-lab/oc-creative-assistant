<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useCenterStageStore } from '../../stores/useCenterStageStore'
import {
  deleteNode as apiDeleteNode,
  getNodeFields,
  saveNodeFields,
  updateNode,
} from '../../api/projectApi'

/**
 * Node detail — a stationery writing surface (second_revision 改点 A, W3).
 *
 * Reads the initial snapshot from useCenterStageStore.detailNode, lets the writer
 * edit title / body / tags / status + free-form attributes, and persists straight
 * to the backend. "Back to canvas" returns (SubgraphCanvas reloads on mode change).
 */
const props = defineProps<{ nodeId: string }>()
const emit = defineEmits<{ return: [] }>()

const route = useRoute()
const centerStage = useCenterStageStore()
const { detailNode } = storeToRefs(centerStage)

const projectId = String(route.params.projectId)

const TYPE_LABEL: Record<string, string> = {
  character: 'Character',
  worldbuilding: 'Worldbuilding',
  world: 'Worldbuilding',
  plot: 'Plot',
  idea: 'Idea',
  research: 'Research',
  structure: 'Structure',
}

const title = ref('')
const body = ref('')
const tagsText = ref('')
const status = ref('draft')
const saveState = ref('')

interface FieldRow {
  key: string
  value: string
}
const fieldRows = ref<FieldRow[]>([])

const typeLabel = computed(() => TYPE_LABEL[detailNode.value?.nodeType ?? ''] ?? 'Note')

function loadFromSnapshot() {
  const node = detailNode.value
  title.value = node?.title ?? ''
  body.value = node?.content ?? ''
  tagsText.value = (node?.tags ?? []).join(', ')
  status.value = node?.status ?? 'draft'
}

async function loadFields() {
  try {
    const result = await getNodeFields(projectId, props.nodeId)
    fieldRows.value = Object.entries(result.fields).map(([key, value]) => ({ key, value }))
  } catch {
    fieldRows.value = []
  }
}

function addField() {
  fieldRows.value.push({ key: '', value: '' })
}
function removeField(index: number) {
  fieldRows.value.splice(index, 1)
}

async function handleSave() {
  saveState.value = 'Saving…'
  const tags = tagsText.value
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
  const fields: Record<string, string> = {}
  for (const row of fieldRows.value) {
    const key = row.key.trim()
    if (key) fields[key] = row.value
  }
  try {
    await updateNode(projectId, props.nodeId, {
      title: title.value,
      content: body.value,
      tags,
      status: status.value,
    })
    await saveNodeFields(projectId, props.nodeId, fields)
    saveState.value = `Saved · ${new Date().toLocaleTimeString()}`
  } catch (e) {
    saveState.value = e instanceof Error ? `Save failed: ${e.message}` : 'Save failed'
  }
}

async function handleDelete() {
  if (!window.confirm('Delete this node? Connected edges will be removed too.')) return
  try {
    await apiDeleteNode(projectId, props.nodeId)
    emit('return')
  } catch (e) {
    saveState.value = e instanceof Error ? `Delete failed: ${e.message}` : 'Delete failed'
  }
}

onMounted(() => {
  loadFromSnapshot()
  void loadFields()
})
watch(
  () => props.nodeId,
  () => {
    loadFromSnapshot()
    void loadFields()
  },
)
</script>

<template>
  <section class="detail">
    <div class="detail__bar">
      <button type="button" class="detail__back" @click="emit('return')">← Back to canvas</button>
      <span class="detail__state">{{ saveState }}</span>
    </div>

    <div class="detail__scroll">
      <article class="sheet">
        <p class="eyebrow sheet__eyebrow">{{ typeLabel }}</p>

        <input
          v-model="title"
          class="sheet__title"
          type="text"
          placeholder="Untitled"
          spellcheck="false"
        />

        <textarea
          v-model="body"
          class="sheet__body"
          rows="10"
          placeholder="Start writing — describe this character, place, or moment…"
        ></textarea>

        <div class="sheet__meta">
          <label class="sheet__meta-row">
            <span class="eyebrow">Tags</span>
            <input v-model="tagsText" type="text" placeholder="protagonist, act one" />
          </label>
          <label class="sheet__meta-row sheet__meta-row--status">
            <span class="eyebrow">Status</span>
            <select v-model="status">
              <option value="draft">draft</option>
              <option value="synced">synced</option>
              <option value="outdated">outdated</option>
            </select>
          </label>
        </div>

        <div class="sheet__fields">
          <div class="sheet__fields-head">
            <span class="eyebrow">Attributes</span>
            <button type="button" class="sheet__add" @click="addField">+ Add field</button>
          </div>
          <p v-if="fieldRows.length === 0" class="sheet__hint">No attributes yet.</p>
          <div v-for="(row, index) in fieldRows" :key="index" class="sheet__field">
            <input v-model="row.key" class="sheet__field-key" placeholder="Faction" />
            <span class="sheet__field-sep">·</span>
            <input v-model="row.value" class="sheet__field-val" placeholder="Flame Kingdom" />
            <button type="button" class="sheet__field-del" @click="removeField(index)">✕</button>
          </div>
        </div>

        <footer class="sheet__foot">
          <button type="button" class="sheet__save" @click="handleSave">Save</button>
          <button type="button" class="sheet__delete" @click="handleDelete">Delete node</button>
        </footer>
      </article>
    </div>
  </section>
</template>

<style scoped>
.detail {
  height: 100%;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  background: var(--app-bg);
}
.detail__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--panel);
}
.detail__back {
  border: none;
  background: none;
  color: var(--text-soft);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.detail__back:hover {
  color: var(--accent);
}
.detail__state {
  font-size: 12px;
  color: var(--muted);
}
.detail__scroll {
  min-height: 0;
  overflow-y: auto;
  padding: 28px 24px 60px;
  display: flex;
  justify-content: center;
}

/* —— the sheet of paper —— */
.sheet {
  width: 100%;
  max-width: 660px;
  padding: 44px 52px 40px;
  background: var(--paper);
  border: 1px solid var(--border);
  border-radius: 4px;
  box-shadow: var(--shadow-lg);
  /* faint ruled lines + a warm paper wash */
  background-image:
    linear-gradient(var(--paper), var(--paper)),
    repeating-linear-gradient(
      to bottom,
      transparent 0,
      transparent 33px,
      rgba(28, 25, 23, 0.04) 33px,
      rgba(28, 25, 23, 0.04) 34px
    );
  background-clip: padding-box;
  position: relative;
}
/* a soft binding margin line on the left, like a letter pad */
.sheet::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 34px;
  width: 1px;
  background: rgba(233, 130, 74, 0.25);
}
.sheet__eyebrow {
  margin: 0 0 10px;
}
.sheet__title {
  width: 100%;
  border: none;
  background: transparent;
  font-family: var(--font-serif);
  font-size: 2.1rem;
  font-weight: 500;
  letter-spacing: -0.015em;
  color: var(--text);
  padding: 0;
}
.sheet__title::placeholder {
  color: rgba(28, 25, 23, 0.25);
}
.sheet__title:focus {
  outline: none;
}
.sheet__body {
  width: 100%;
  margin-top: 14px;
  border: none;
  background: transparent;
  resize: vertical;
  font-family: var(--font-serif);
  font-size: 1.04rem;
  line-height: 34px; /* aligns text to the ruled lines */
  color: var(--text-soft);
}
.sheet__body:focus {
  outline: none;
}
.sheet__body::placeholder {
  color: rgba(28, 25, 23, 0.28);
}

.sheet__meta {
  display: flex;
  gap: 28px;
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid rgba(28, 25, 23, 0.08);
}
.sheet__meta-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
.sheet__meta-row--status {
  flex: 0 0 140px;
}
.sheet__meta-row input,
.sheet__meta-row select {
  border: none;
  border-bottom: 1px solid var(--border-strong);
  background: transparent;
  padding: 4px 0;
  font-size: 0.92rem;
  color: var(--text);
}
.sheet__meta-row input:focus,
.sheet__meta-row select:focus {
  outline: none;
  border-bottom-color: var(--accent);
}

.sheet__fields {
  margin-top: 24px;
}
.sheet__fields-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.sheet__add {
  border: none;
  background: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}
.sheet__hint {
  color: var(--muted);
  font-size: 13px;
}
.sheet__field {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
}
.sheet__field-key {
  width: 150px;
  border: none;
  background: transparent;
  font-weight: 600;
  color: var(--text);
}
.sheet__field-sep {
  color: var(--muted);
}
.sheet__field-val {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-soft);
}
.sheet__field-key:focus,
.sheet__field-val:focus {
  outline: none;
}
.sheet__field-del {
  border: none;
  background: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 11px;
  opacity: 0;
  transition: opacity 0.15s;
}
.sheet__field:hover .sheet__field-del {
  opacity: 1;
}

.sheet__foot {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 32px;
}
.sheet__save {
  padding: 9px 22px;
  border-radius: 999px;
  border: none;
  background: var(--text);
  color: #fff;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
}
.sheet__save:hover {
  background: var(--accent);
}
.sheet__delete {
  padding: 9px 16px;
  border-radius: 999px;
  border: 1px solid var(--border-strong);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.86rem;
}
.sheet__delete:hover {
  color: var(--warm);
  border-color: var(--warm);
}
</style>
