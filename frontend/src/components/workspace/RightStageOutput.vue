<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAiOutputStore } from '../../stores/useAiOutputStore'
import AiOutputCard from './AiOutputCard.vue'

/**
 * 右栏 AI 输出流（second_revision 改点 B / W5）。
 * 时间线倒序卡片（最新在最上），每张可折叠，按来源类型标签区分。
 */
const store = useAiOutputStore()
const { outputs } = storeToRefs(store)
</script>

<template>
  <aside class="right-stage">
    <header class="right-stage__head">AI output</header>
    <p v-if="outputs.length === 0" class="right-stage__empty">
      Ask in the composer below — search, memory, prompts and feedback land here, newest first.
    </p>
    <div v-else class="right-stage__list">
      <AiOutputCard
        v-for="output in outputs"
        :key="output.id"
        :output="output"
        @toggle="store.toggleCollapse"
      />
    </div>
  </aside>
</template>

<style scoped>
.right-stage {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border, #e5e7eb);
  overflow: hidden;
}
.right-stage__head {
  padding: 12px 16px;
  font-weight: 600;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
.right-stage__empty {
  padding: 16px;
  color: var(--muted, #888);
  font-size: 13px;
  line-height: 1.6;
}
.right-stage__list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
