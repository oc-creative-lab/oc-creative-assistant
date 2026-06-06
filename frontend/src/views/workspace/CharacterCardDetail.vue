<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'
import { useGraphStore } from '../../stores/useGraphStore'
import {
  getNodeCrossReferences,
  getNodeFields,
  saveNodeFields,
  type CrossReferenceItem,
} from '../../api/projectApi'

/**
 * 角色卡详情（first_revision 决策 2，已获批准偏离 proposal）。
 *
 * 顶部名字 + 简介；中部“自由字段”增删改（持久化到 node.meta JSON 的 fields 键）；
 * 底部“关系”区把该角色在 character sub-graph 里的出边以标签展示，不画连线。
 */
const props = defineProps<{ charId: string }>()

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const graphStore = useGraphStore()
const { characterGraphId } = storeToRefs(projectStore)

const projectId = computed(() => String(route.params.projectId))
const node = computed(() => graphStore.getNode(props.charId))

interface FieldRow {
  key: string
  value: string
}
const fieldRows = ref<FieldRow[]>([])
const saveState = ref('')

// 跨 sub-graph 反向引用：该角色出现在故事线 / 所属世界观等。
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

// 关系：该角色的出边 → 标签（关系名 + 目标角色名）。
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
  const fields: Record<string, string> = {}
  for (const row of fieldRows.value) {
    const key = row.key.trim()
    if (key) fields[key] = row.value
  }
  try {
    await saveNodeFields(projectId.value, props.charId, fields)
    saveState.value = `Saved · ${new Date().toLocaleTimeString()}`
  } catch (e) {
    saveState.value = e instanceof Error ? `Save failed: ${e.message}` : 'Save failed'
  }
}

// sub-graph 未加载时（直接访问详情 URL / 刷新）按 characterGraphId 兜底加载。
watch(
  characterGraphId,
  (id) => {
    if (id) void graphStore.load(id)
  },
  { immediate: true },
)

onMounted(() => {
  void loadFields()
  void loadCrossRefs()
})
watch(
  () => props.charId,
  () => {
    void loadFields()
    void loadCrossRefs()
  },
)
</script>

<template>
  <section class="char-detail">
    <button type="button" class="char-detail__back" @click="router.push(`/workspace/${projectId}/characters`)">
      ← Characters
    </button>

    <header class="char-detail__head">
      <h2>{{ node?.title ?? 'Character' }}</h2>
      <p class="char-detail__content">{{ node?.content || 'No summary' }}</p>
    </header>

    <div class="char-detail__section">
      <div class="char-detail__section-head">
        <h3>Attributes</h3>
        <button type="button" class="char-detail__add" @click="addField">+ Add field</button>
      </div>
      <p v-if="fieldRows.length === 0" class="char-detail__hint">No attributes yet — add one.</p>
      <div v-for="(row, index) in fieldRows" :key="index" class="char-detail__row">
        <input v-model="row.key" class="char-detail__key" placeholder="Field (e.g. Faction)" />
        <input v-model="row.value" class="char-detail__value" placeholder="Value" />
        <button type="button" class="char-detail__del" @click="removeField(index)">Remove</button>
      </div>
      <div class="char-detail__actions">
        <button type="button" class="char-detail__save" @click="handleSave">Save</button>
        <span class="char-detail__state">{{ saveState }}</span>
      </div>
    </div>

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
.char-detail__back {
  align-self: flex-start;
  font-size: 13px;
  color: var(--muted, #888);
  background: none;
  border: none;
  cursor: pointer;
}
.char-detail__head h2 {
  font-size: 22px;
}
.char-detail__content {
  color: #666;
  font-size: 14px;
  line-height: 1.6;
  margin-top: 6px;
}
.char-detail__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.char-detail__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.char-detail__hint {
  color: var(--muted, #888);
  font-size: 13px;
}
.char-detail__row {
  display: flex;
  gap: 8px;
}
.char-detail__key,
.char-detail__value {
  padding: 6px 10px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
}
.char-detail__key {
  width: 160px;
}
.char-detail__value {
  flex: 1;
}
.char-detail__del {
  background: none;
  border: none;
  color: #dc2626;
  font-size: 12px;
  cursor: pointer;
}
.char-detail__add {
  font-size: 13px;
  color: var(--accent);
  background: none;
  border: none;
  cursor: pointer;
}
.char-detail__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.char-detail__save {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}
.char-detail__state {
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
</style>
