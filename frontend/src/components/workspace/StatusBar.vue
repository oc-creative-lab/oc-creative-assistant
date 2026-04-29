<script setup lang="ts">
import type { WorkspaceStatus } from '../../types/workspace'

defineProps<{
  // 状态栏只展示 AppShell 汇总后的状态，不直接发起保存或索引动作。
  status: WorkspaceStatus
}>()
</script>

<template>
  <footer class="status-bar">
    <span>{{ status.saveState }}</span>
    <span>{{ status.indexState }}</span>
    <span>{{ status.modelState }}</span>
  </footer>
</template>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 14px;
  background: var(--panel-strong);
  color: var(--muted);
  font-size: 0.78rem;
}

.status-bar span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .status-bar {
    align-items: flex-start;
    flex-direction: column;
    padding: 10px 12px;
  }
}
</style>
