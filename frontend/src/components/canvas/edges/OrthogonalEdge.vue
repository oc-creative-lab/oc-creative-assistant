<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref } from 'vue'
import { EdgeLabelRenderer, useVueFlow, type EdgeProps } from '@vue-flow/core'
import type { CreativeEdgeData, CreativeEdgeWaypoint } from '../../../types/node'

type Segment = 'source' | 'middle' | 'target'

const props = defineProps<EdgeProps<CreativeEdgeData>>()
const { getViewport } = useVueFlow()
const applyEdgeWaypoint = inject<(id: string, wp: CreativeEdgeWaypoint) => void>('applyEdgeWaypoint')

const defaultOrientation = computed<'horizontal' | 'vertical'>(() =>
  Math.abs(props.targetX - props.sourceX) >= Math.abs(props.targetY - props.sourceY)
    ? 'vertical'
    : 'horizontal',
)

const orientation = computed<'horizontal' | 'vertical'>(
  () => props.data?.waypoint?.orientation ?? defaultOrientation.value,
)

const defaults = computed(() => {
  const { sourceX, sourceY, targetX, targetY } = props
  if (orientation.value === 'vertical') {
    return {
      middle: (sourceX + targetX) / 2,
      nearSource: sourceY,
      nearTarget: targetY,
    }
  }
  return {
    middle: (sourceY + targetY) / 2,
    nearSource: sourceX,
    nearTarget: targetX,
  }
})

const dragSegment = ref<Segment | null>(null)
const localValue = ref<number | null>(null)

function readSegment(seg: Segment): number {
  if (dragSegment.value === seg && localValue.value !== null) {
    return localValue.value
  }
  const wp = props.data?.waypoint
  const d = defaults.value
  if (seg === 'middle') return wp?.middle ?? d.middle
  if (seg === 'source') return wp?.nearSource ?? d.nearSource
  return wp?.nearTarget ?? d.nearTarget
}

const segMiddle = computed(() => readSegment('middle'))
const segSource = computed(() => readSegment('source'))
const segTarget = computed(() => readSegment('target'))

const fullPath = computed(() => {
  const { sourceX, sourceY, targetX, targetY } = props
  if (orientation.value === 'vertical') {
    return [
      `M ${sourceX} ${sourceY}`,
      `L ${sourceX} ${segSource.value}`,
      `L ${segMiddle.value} ${segSource.value}`,
      `L ${segMiddle.value} ${segTarget.value}`,
      `L ${targetX} ${segTarget.value}`,
      `L ${targetX} ${targetY}`,
    ].join(' ')
  }
  return [
    `M ${sourceX} ${sourceY}`,
    `L ${segSource.value} ${sourceY}`,
    `L ${segSource.value} ${segMiddle.value}`,
    `L ${segTarget.value} ${segMiddle.value}`,
    `L ${segTarget.value} ${targetY}`,
    `L ${targetX} ${targetY}`,
  ].join(' ')
})

/* 每段独立的 hit path, 跟 fullPath 中间 3 段一一对齐 */
const hitPaths = computed(() => {
  const { sourceX, sourceY, targetX, targetY } = props
  if (orientation.value === 'vertical') {
    return {
      source: `M ${sourceX} ${segSource.value} L ${segMiddle.value} ${segSource.value}`,
      middle: `M ${segMiddle.value} ${segSource.value} L ${segMiddle.value} ${segTarget.value}`,
      target: `M ${segMiddle.value} ${segTarget.value} L ${targetX} ${segTarget.value}`,
    }
  }
  return {
    source: `M ${segSource.value} ${sourceY} L ${segSource.value} ${segMiddle.value}`,
    middle: `M ${segSource.value} ${segMiddle.value} L ${segTarget.value} ${segMiddle.value}`,
    target: `M ${segTarget.value} ${segMiddle.value} L ${segTarget.value} ${targetY}`,
  }
})

const cursors = computed(() => {
  const v = orientation.value === 'vertical'
  return {
    source: v ? 'ns-resize' : 'ew-resize',
    middle: v ? 'ew-resize' : 'ns-resize',
    target: v ? 'ns-resize' : 'ew-resize',
  }
})

const labelX = computed(() =>
  orientation.value === 'vertical'
    ? segMiddle.value
    : (segSource.value + segTarget.value) / 2,
)
const labelY = computed(() =>
  orientation.value === 'vertical'
    ? (segSource.value + segTarget.value) / 2
    : segMiddle.value,
)

/* ---------- 拖拽 ---------- */
let dragStartClient = { x: 0, y: 0 }
let dragStartValue = 0

function onMouseDown(event: MouseEvent, segment: Segment) {
  event.stopPropagation()
  event.preventDefault()
  dragSegment.value = segment
  dragStartClient = { x: event.clientX, y: event.clientY }
  dragStartValue = readSegment(segment)
  localValue.value = dragStartValue
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(event: MouseEvent) {
  if (dragSegment.value === null) return
  const { zoom } = getViewport()
  const v = orientation.value === 'vertical'
  /* perp 轴推导: vertical 时 middle 用 x, 两侧用 y; horizontal 反过来 */
  const usesX = (v && dragSegment.value === 'middle') || (!v && dragSegment.value !== 'middle')
  const delta = usesX
    ? (event.clientX - dragStartClient.x) / zoom
    : (event.clientY - dragStartClient.y) / zoom
  localValue.value = dragStartValue + delta
}

function onMouseUp() {
  if (dragSegment.value !== null && localValue.value !== null) {
    const next: CreativeEdgeWaypoint = {
      orientation: orientation.value,
      middle: readSegment('middle'),
      nearSource: readSegment('source'),
      nearTarget: readSegment('target'),
    }
    applyEdgeWaypoint?.(props.id, next)
  }
  dragSegment.value = null
  localValue.value = null
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <path
    :id="id"
    :d="fullPath"
    :marker-end="markerEnd"
    :style="style"
    class="vue-flow__edge-path"
    fill="none"
  />

  <path
    :d="hitPaths.source"
    fill="none"
    stroke="transparent"
    stroke-width="20"
    :style="{ pointerEvents: 'stroke', cursor: cursors.source }"
    @mousedown="(e) => onMouseDown(e, 'source')"
  />
  <path
    :d="hitPaths.middle"
    fill="none"
    stroke="transparent"
    stroke-width="20"
    :style="{ pointerEvents: 'stroke', cursor: cursors.middle }"
    @mousedown="(e) => onMouseDown(e, 'middle')"
  />
  <path
    :d="hitPaths.target"
    fill="none"
    stroke="transparent"
    stroke-width="20"
    :style="{ pointerEvents: 'stroke', cursor: cursors.target }"
    @mousedown="(e) => onMouseDown(e, 'target')"
  />

  <EdgeLabelRenderer v-if="label">
    <div
      class="vue-flow__edge-text-wrapper"
      :style="{
        transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
      }"
    >
      <span class="vue-flow__edge-text" :style="labelStyle">{{ label }}</span>
    </div>
  </EdgeLabelRenderer>
</template>

<style scoped>
.vue-flow__edge-text-wrapper {
  position: absolute;
  pointer-events: none;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  font-weight: 700;
}
</style>