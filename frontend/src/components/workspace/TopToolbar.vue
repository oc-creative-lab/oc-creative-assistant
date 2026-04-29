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
  <!-- 顶部栏：负责全局项目操作 -->
  <header class="top-toolbar">
    <div class="title-block">
      <div class="brand">
        <span class="logo-icon">✨</span>
        <strong>OC Creative Assistant</strong>
      </div>
      <span class="divider">/</span>
      <span class="project-name">{{ projectName }}</span>
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
  align-items: center;
  gap: 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  font-size: 1.1rem;
}

.brand strong {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text);
}

.divider {
  color: var(--border);
  font-size: 1.1rem;
  font-weight: 300;
}

.project-name {
  color: var(--muted);
  font-size: 0.95rem;
  font-weight: 500;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.toolbar-actions button {
  min-height: 34px;
  padding: 0 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  font-size: 0.88rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.toolbar-actions button:hover:not(:disabled) {
  border-color: var(--accent-border);
  background: var(--app-bg);
  color: var(--accent);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
}

.toolbar-actions button:active:not(:disabled) {
  transform: translateY(1px);
  box-shadow: none;
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
