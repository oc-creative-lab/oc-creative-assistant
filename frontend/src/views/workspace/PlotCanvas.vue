<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'
import SubgraphCanvas from '../../components/workspace/SubgraphCanvas.vue'

/**
 * 故事线视图（first_revision 阶段 3）：Vue Flow 画布，绑定 plot sub-graph。
 */
const { plotGraphId } = storeToRefs(useProjectStore())
</script>

<template>
  <SubgraphCanvas
    v-if="plotGraphId"
    :key="plotGraphId"
    :graph-id="plotGraphId"
    :create-types="['plot']"
  />
  <p v-else class="workspace-loading">正在加载故事线...</p>
</template>

<style scoped>
.workspace-loading {
  padding: 24px;
  color: var(--muted, #888);
}
</style>
