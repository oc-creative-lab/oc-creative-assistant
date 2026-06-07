<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'
import { useGraphStore } from '../../stores/useGraphStore'
import {
  deleteNode,
  getNodeCrossReferences,
  getNodeFields,
  saveNodeFields,
  updateNode,
  type CrossReferenceItem,
} from '../../api/projectApi'
import { fileToScaledDataUrl } from '../../utils/imageDataUrl'
import DocFieldsEditor, { type DocFieldRow } from '../../components/workspace/DocFieldsEditor.vue'

const SAVE_DEBOUNCE_MS = 500

/**
 * Character card detail (first_revision decision 2, an approved deviation from the proposal).
 *
 * Top: name + summary; middle: add/edit/remove "free-form fields" (persisted to
 * the fields key of node.meta JSON); bottom: the "relations" area shows this
 * character's outgoing edges in the character sub-graph as tags, without
 * drawing connecting lines.
 */
const props = defineProps<{ charId: string }>()

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const graphStore = useGraphStore()
const { characterGraphId } = storeToRefs(projectStore)

const projectId = computed(() => String(route.params.projectId))
const node = computed(() => graphStore.getNode(props.charId))

const fieldRows = ref<DocFieldRow[]>([])
const title = ref('')
const content = ref('')
const avatar = ref('')
const avatarInput = ref<HTMLInputElement | null>(null)
const saveState = ref('')
const isHydrating = ref(true)
const isDeleting = ref(false)

let saveTimer: ReturnType<typeof setTimeout> | null = null
let isSaving = false
let saveQueued = false

// Cross sub-graph back-references (stage 6): where this character appears in the story / which worldbuilding it belongs to, etc.
const crossRefs = ref<CrossReferenceItem[]>([])
const plotRefs = computed(() => crossRefs.value.filter((r) => r.other_section === 'plot'))
const worldRefs = computed(() => crossRefs.value.filter((r) => r.other_section === 'world'))

async function loadCrossRefs() {
  try {
    const resp = await getNodeCrossReferences(projectId.value, props.charId)
    crossRefs.value = resp.references
  } catch {
    crossRefs.value = []
  }
}

function openPlotNode() {
  router.push(`/workspace/${projectId.value}/plot`)
}

// Relations: this character's outgoing edges → tags (relation name + target character name).
const relations = computed(() =>
  graphStore.outgoingEdges(props.charId).map((edge) => ({
    id: edge.id,
    label: edge.label || edge.relationType || 'relates to',
    target: graphStore.getNode(edge.target)?.title ?? edge.target,
  })),
)

async function loadFields() {
  try {
    const result = await getNodeFields(projectId.value, props.charId)
    avatar.value = result.fields.avatar ?? ''
    fieldRows.value = Object.entries(result.fields)
      .filter(([key]) => key !== 'avatar')
      .map(([key, value]) => ({ key, value }))
  } catch {
    avatar.value = ''
    fieldRows.value = []
  }
}

function openAvatarPicker() {
  avatarInput.value?.click()
}

async function handleAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    saveState.value = 'Please choose an image file'
    return
  }
  try {
    avatar.value = await fileToScaledDataUrl(file, 640, 0.85)
    scheduleSave()
  } catch (error) {
    saveState.value = error instanceof Error ? error.message : 'Failed to load image'
  }
}

function fieldsFromRows(): Record<string, string> {
  const fields: Record<string, string> = {}
  if (avatar.value) fields.avatar = avatar.value
  for (const row of fieldRows.value) {
    const key = row.key.trim()
    if (key) fields[key] = row.value
  }
  return fields
}

function scheduleSave() {
  if (isHydrating.value) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    void persistAll()
  }, SAVE_DEBOUNCE_MS)
}

async function persistAll() {
  if (isSaving) {
    saveQueued = true
    return
  }

  isSaving = true
  saveState.value = 'Saving…'
  try {
    await updateNode(projectId.value, props.charId, {
      title: title.value.trim() || 'Untitled Character',
      content: content.value,
    })
    await saveNodeFields(projectId.value, props.charId, fieldsFromRows())
    if (characterGraphId.value) {
      await graphStore.load(characterGraphId.value, true)
    }
    saveState.value = 'Saved'
  } catch (error) {
    saveState.value = error instanceof Error ? `Save failed: ${error.message}` : 'Save failed'
  } finally {
    isSaving = false
    if (saveQueued) {
      saveQueued = false
      void persistAll()
    }
  }
}

async function hydrate() {
  if (!node.value) return
  isHydrating.value = true
  title.value = node.value.title
  content.value = node.value.content ?? ''
  await loadFields()
  isHydrating.value = false
}

async function handleDelete() {
  const charTitle = title.value.trim() || node.value?.title || 'this character'
  const confirmed = window.confirm(`Delete "${charTitle}"? Related edges will be removed too.`)
  if (!confirmed || isDeleting.value) return

  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }

  isDeleting.value = true
  try {
    await deleteNode(projectId.value, props.charId)
    if (characterGraphId.value) {
      await graphStore.load(characterGraphId.value, true)
    }
    router.push(`/workspace/${projectId.value}/characters`)
  } catch (error) {
    saveState.value = error instanceof Error ? `Delete failed: ${error.message}` : 'Delete failed'
  } finally {
    isDeleting.value = false
  }
}

watch(
  characterGraphId,
  async (id) => {
    if (!id) return
    await graphStore.load(id)
    await hydrate()
  },
  { immediate: true },
)

onMounted(() => {
  void loadCrossRefs()
  void hydrate()
})

watch(
  () => props.charId,
  () => {
    void hydrate()
    void loadCrossRefs()
  },
)

watch([title, content, fieldRows], () => {
  scheduleSave()
}, { deep: true })

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
})
</script>

<template>
  <section class="char-detail">
    <header class="char-detail__topbar">
      <button type="button" class="char-detail__back" @click="router.push(`/workspace/${projectId}/characters`)">
        ← Characters
      </button>
      <span v-if="saveState" class="char-detail__state">{{ saveState }}</span>
    </header>

    <input
      ref="avatarInput"
      class="char-detail__file-input"
      type="file"
      accept="image/*"
      @change="handleAvatarChange"
    />

    <header class="char-detail__head">
      <div
        class="char-detail__avatar"
        role="button"
        tabindex="0"
        :aria-label="avatar ? 'Double-click to change avatar' : 'Double-click to upload avatar'"
        title="Double-click to change avatar"
        @dblclick.stop="openAvatarPicker"
        @keydown.enter="openAvatarPicker"
      >
        <img v-if="avatar" :src="avatar" :alt="title || 'Character avatar'" />
        <span v-else class="char-detail__avatar-placeholder">+</span>
      </div>
      <div class="char-detail__intro">
        <input
          v-model="title"
          class="char-detail__title"
          type="text"
          placeholder="Character name"
          spellcheck="false"
        />
        <textarea
          v-model="content"
          class="char-detail__summary"
          rows="2"
          placeholder="Add a summary…"
          spellcheck="true"
        />
      </div>
    </header>

    <DocFieldsEditor v-model="fieldRows" />

    <div class="char-detail__section">
      <h3>Relations</h3>
      <p v-if="relations.length === 0" class="char-detail__hint">No character relations yet.</p>
      <div v-else class="char-detail__relations">
        <span v-for="rel in relations" :key="rel.id" class="char-detail__rel">
          {{ rel.label }} → {{ rel.target }}
        </span>
      </div>
    </div>

    <div class="char-detail__section">
      <h3>Cross-references</h3>
      <p v-if="crossRefs.length === 0" class="char-detail__hint">No cross-references yet.</p>
      <template v-else>
        <div v-if="worldRefs.length" class="char-detail__xref-group">
          <span class="char-detail__xref-label">In worldbuilding:</span>
          <span v-for="ref in worldRefs" :key="ref.edge_id" class="char-detail__rel">
            {{ ref.other_title }}
          </span>
        </div>
        <div v-if="plotRefs.length" class="char-detail__xref-group">
          <span class="char-detail__xref-label">Appears in story:</span>
          <button
            v-for="ref in plotRefs"
            :key="ref.edge_id"
            type="button"
            class="char-detail__rel char-detail__rel--link"
            @click="openPlotNode"
          >
            {{ ref.other_title }}
          </button>
        </div>
      </template>
    </div>

    <footer class="char-detail__footer">
      <button
        type="button"
        class="char-detail__delete"
        :disabled="isDeleting"
        @click="handleDelete"
      >
        {{ isDeleting ? 'Deleting…' : 'Delete character' }}
      </button>
    </footer>
  </section>
</template>

<style scoped>
.char-detail {
  max-width: 640px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.char-detail__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.char-detail__back {
  font-size: 13px;
  color: var(--muted, #888);
  background: none;
  border: none;
  cursor: pointer;
}
.char-detail__file-input {
  display: none;
}
.char-detail__head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.char-detail__avatar {
  flex-shrink: 0;
  width: 72px;
  height: 72px;
  padding: 0;
  border: 1px dashed var(--border, #ddd);
  border-radius: 999px;
  overflow: hidden;
  background: var(--panel-strong, #fafafa);
  cursor: pointer;
}
.char-detail__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.char-detail__avatar-placeholder {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  font-size: 28px;
  color: var(--muted, #888);
}
.char-detail__intro {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.char-detail__title {
  width: 100%;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  cursor: text;
}
.char-detail__title:focus {
  outline: none;
}
.char-detail__summary {
  width: 100%;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  resize: vertical;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-soft, #666);
  cursor: text;
  min-height: 3.2em;
}
.char-detail__summary:focus {
  outline: none;
  color: var(--text);
}
.char-detail__summary::placeholder,
.char-detail__title::placeholder {
  color: var(--muted, #aaa);
}
.char-detail__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.char-detail__hint {
  color: var(--muted, #888);
  font-size: 13px;
}
.char-detail__state {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--muted, #888);
}
.char-detail__relations {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.char-detail__rel {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-deep);
}
.char-detail__rel--link {
  border: none;
  cursor: pointer;
}
.char-detail__xref-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.char-detail__xref-label {
  font-size: 13px;
  color: var(--muted, #666);
}
.char-detail__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
  padding-top: 20px;
  border-top: 1px solid var(--border, #e5e7eb);
}
.char-detail__delete {
  padding: 8px 14px;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  background: #fff;
  color: #dc2626;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.char-detail__delete:hover:not(:disabled) {
  background: #fef2f2;
}
.char-detail__delete:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
