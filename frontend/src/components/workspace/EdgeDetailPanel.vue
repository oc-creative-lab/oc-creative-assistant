<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  RELATION_TYPE_OPTIONS,
  type CreativeFlowEdge,
  type CreativeFlowNode,
  type CreativeRelationType,
} from '../../types/node'

/**
 * Edge detail panel.
 *
 * Provides direction reversal, relation-type switching, and label editing; node
 * lookup is only used to display the source/target titles. The actual edge
 * persistence is handled by the parent after emit('edgeUpdated').
 */
const props = defineProps<{
  selectedEdge: CreativeFlowEdge
  nodes: CreativeFlowNode[]
}>()

const emit = defineEmits<{
  edgeUpdated: [edge: CreativeFlowEdge]
  edgeDeleted: [edgeId: string]
}>()

const isEdgeRelationSelectOpen = ref(false)

function closeAllSelects(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.custom-select-container')) {
    isEdgeRelationSelectOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeAllSelects)
})

onUnmounted(() => {
  document.removeEventListener('click', closeAllSelects)
})

const sourceNodeTitle = computed(
  () => props.nodes.find((node) => node.id === props.selectedEdge.source)?.data.title ?? props.selectedEdge.source,
)

const targetNodeTitle = computed(
  () => props.nodes.find((node) => node.id === props.selectedEdge.target)?.data.title ?? props.selectedEdge.target,
)

function getRelationLabel(relationType: CreativeRelationType) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === relationType)?.label ?? 'Related'
}

function updateEdge(partial: Partial<CreativeFlowEdge['data']>) {
  const data = {
    ...props.selectedEdge.data,
    ...partial,
  }

  emit('edgeUpdated', {
    ...props.selectedEdge,
    label: data.label,
    data,
  })
}

function updateEdgeRelation(relationType: CreativeRelationType) {
  updateEdge({
    relationType,
    label: getRelationLabel(relationType),
  })
}

function reverseSelectedEdge() {
  emit('edgeUpdated', {
    ...props.selectedEdge,
    source: props.selectedEdge.target,
    target: props.selectedEdge.source,
    sourceHandle: props.selectedEdge.targetHandle,
    targetHandle: props.selectedEdge.sourceHandle,
  })
}
</script>

<template>
  <div class="edge-detail-panel">
    <section class="detail-header">
      <p>Current edge</p>
      <h2>{{ selectedEdge.data.label }}</h2>
    </section>

    <section class="detail-panel">
      <dl class="edge-meta">
        <div>
          <dt>Source node</dt>
          <dd>{{ sourceNodeTitle }}</dd>
        </div>
        <div>
          <dt>Target node</dt>
          <dd>{{ targetNodeTitle }}</dd>
        </div>
      </dl>

      <label for="edge-relation">Relation type</label>
      <div class="custom-select-container">
        <div
          class="custom-select-trigger"
          :class="{ 'is-open': isEdgeRelationSelectOpen }"
          @click="isEdgeRelationSelectOpen = !isEdgeRelationSelectOpen"
        >
          <span>{{ getRelationLabel(selectedEdge.data.relationType) }}</span>
          <div class="custom-select-arrow"></div>
        </div>
        <ul class="custom-select-options" v-show="isEdgeRelationSelectOpen">
          <li
            v-for="option in RELATION_TYPE_OPTIONS"
            :key="option.value"
            class="custom-select-option"
            :class="{ 'is-selected': selectedEdge.data.relationType === option.value }"
            @click="updateEdgeRelation(option.value as CreativeRelationType); isEdgeRelationSelectOpen = false"
          >
            {{ option.label }}
          </li>
        </ul>
      </div>

      <label for="edge-label">Edge label</label>
      <div class="input-wrapper">
        <input
          id="edge-label"
          type="text"
          :value="selectedEdge.data.label"
          @input="updateEdge({ label: ($event.target as HTMLInputElement).value })"
        />
      </div>

      <button type="button" class="secondary-action" @click="reverseSelectedEdge">Reverse direction</button>
      <button type="button" class="danger" @click="emit('edgeDeleted', selectedEdge.id)">Delete edge</button>
    </section>
  </div>
</template>

<style scoped src="./AgentSidebar.scoped.css"></style>