<script setup lang="ts">
import { useCenterStageStore } from '../../stores/useCenterStageStore'

/**
 * Center-stage controller (second_revision change A).
 *
 * W1: placeholder. In W3 this switches between the canvas and node detail based on
 * useCenterStageStore.mode:
 *   <CanvasWorkspace v-if="mode==='canvas'" /> ⇄ <NodeDetailView v-else />
 * The canvas view is currently rendered directly by each sub-graph route view
 * (PlotCanvas/WorldCanvas); in W3 this component wires up the double-click-to-detail
 * capability.
 */
const store = useCenterStageStore()
defineExpose({ store })
</script>

<template>
  <div class="center-stage">
    <slot />
  </div>
</template>

<style scoped>
.center-stage {
  height: 100%;
  min-height: 0;
}
</style>
