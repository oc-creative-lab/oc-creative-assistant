<script setup lang="ts">
defineProps<{
  projectName: string
  isSaving: boolean
}>()

defineEmits<{
  save: []
}>()

// 目前只有 save 接入实际逻辑，其余按钮先保留为后续桌面能力入口。
const toolbarActions = [
  { id: 'save', label: '\u4fdd\u5b58' },
  { id: 'import', label: '\u5bfc\u5165\u8d44\u6599' },
  { id: 'export', label: '\u5bfc\u51fa' },
  { id: 'settings', label: '\u8bbe\u7f6e' },
]

const savingLabel = '\u4fdd\u5b58\u4e2d...'
</script>

<template>
  <header class="top-toolbar">
    <div class="title-block">
      <strong>OC Creative Assistant</strong>
      <span>{{ projectName }}</span>
    </div>

    <nav class="toolbar-actions" aria-label="&#24037;&#20316;&#21306;&#25805;&#20316;">
      <button
        v-for="action in toolbarActions"
        :key="action.id"
        type="button"
        :disabled="action.id === 'save' && isSaving"
        @click="action.id === 'save' ? $emit('save') : undefined"
      >
        {{ action.id === 'save' && isSaving ? savingLabel : action.label }}
      </button>
    </nav>
  </header>
</template>

<style scoped>
.top-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 18px;
  background: var(--panel-strong);
}

.title-block {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.title-block strong {
  font-size: 0.98rem;
  line-height: 1;
}

.title-block span {
  color: var(--muted);
  font-size: 0.9rem;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.toolbar-actions button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
  cursor: pointer;
}

.toolbar-actions button:disabled {
  cursor: wait;
  opacity: 0.72;
}

@media (max-width: 640px) {
  .top-toolbar {
    align-items: flex-start;
    flex-direction: column;
    padding: 12px;
  }

  .toolbar-actions {
    justify-content: flex-start;
  }
}
</style>
