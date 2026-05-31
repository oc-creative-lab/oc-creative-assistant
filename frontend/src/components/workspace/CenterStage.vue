<script setup lang="ts">
import { useCenterStageStore } from '../../stores/useCenterStageStore'

/**
 * 中栏舞台控制器（second_revision 改点 A）。
 *
 * W1：占位。W3 在此根据 useCenterStageStore.mode 在画布与节点详情之间切换：
 *   <CanvasWorkspace v-if="mode==='canvas'" /> ⇄ <NodeDetailView v-else />
 * 当前画布视图仍由各 sub-graph 路由视图(PlotCanvas/WorldCanvas)直接渲染，
 * 本组件在 W3 接入双击进详情的能力。
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
