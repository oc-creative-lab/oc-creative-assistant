<script setup lang="ts">
/**
 * Top toolbar.
 *
 * Only displays the project name and global action entry points; currently only the
 * save action is wired to business logic, while the other buttons remain as entry
 * points for future import, export, and settings capabilities.
 */
defineProps<{
  projectName: string
  isSaving: boolean
}>()

const emit = defineEmits<{
  save: []
}>()

const toolbarActions = [
  { id: 'refresh', label: 'Refresh' },
  { id: 'save', label: 'Save' },
  { id: 'import', label: 'Import' },
  { id: 'export', label: 'Export' },
  { id: 'settings', label: 'Settings' },
]

const savingLabel = 'Saving…'

function handleActionClick(actionId: string) {
  if (actionId === 'save') {
    emit('save')
  } else if (actionId === 'refresh') {
    window.location.reload()
  }
}
</script>

<template>
  <!-- Top bar: global project actions -->
  <header class="top-toolbar">
    <div class="title-block">
      <div class="brand">
        <span class="logo-icon">✨</span>
        <strong>OC Creative Assistant</strong>
      </div>
      <span class="divider">/</span>
      <span class="project-name">{{ projectName }}</span>
    </div>

    <nav class="toolbar-actions" aria-label="Workspace actions">
      <button
        v-for="action in toolbarActions"
        :key="action.id"
        type="button"
        :disabled="action.id === 'save' && isSaving"
        @click="handleActionClick(action.id)"
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
