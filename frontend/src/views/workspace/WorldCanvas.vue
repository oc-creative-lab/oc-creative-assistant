<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'
import SubgraphCanvas from '../../components/workspace/SubgraphCanvas.vue'

/**
 * 世界观视图：Vue Flow 画布，绑定 world sub-graph。
 */
const { worldGraphId } = storeToRefs(useProjectStore())
</script>

<template>
  <SubgraphCanvas
    v-if="worldGraphId"
    :key="worldGraphId"
    :graph-id="worldGraphId"
    :create-types="['worldbuilding']"
  />
  <p v-else class="workspace-loading">Loading worldbuilding...</p>
</template>

<style scoped>
.workspace-loading {
  padding: 24px;
  color: var(--muted, #888);
}
</style>
