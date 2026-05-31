<script setup lang="ts">
import { ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../../stores/useProjectStore'
import { updateProject } from '../../api/projectApi'

/**
 * Overview（first_revision 阶段 3）：编辑项目名与简介，持久化到 ProjectORM。
 */
const projectStore = useProjectStore()
const { detail } = storeToRefs(projectStore)

const name = ref('')
const description = ref('')
const saveState = ref('')

// 详情加载/切换项目后回填表单。
watch(
  detail,
  (value) => {
    name.value = value?.name ?? ''
    description.value = value?.description ?? ''
  },
  { immediate: true },
)

async function handleSave() {
  if (!detail.value) return
  saveState.value = 'Saving…'
  try {
    await updateProject(detail.value.id, {
      name: name.value.trim(),
      description: description.value,
    })
    await projectStore.loadProject(detail.value.id, true)
    saveState.value = `Saved · ${new Date().toLocaleTimeString()}`
  } catch (e) {
    saveState.value = e instanceof Error ? `Save failed: ${e.message}` : 'Save failed'
  }
}
</script>

<template>
  <section class="overview">
    <h2>Overview</h2>
    <label class="overview__field">
      <span>Project name</span>
      <input v-model="name" type="text" />
    </label>
    <label class="overview__field">
      <span>Description</span>
      <textarea v-model="description" rows="6" placeholder="Describe the world, tone and goals of this project…"></textarea>
    </label>
    <div class="overview__actions">
      <button type="button" class="overview__save" :disabled="!name.trim()" @click="handleSave">
        Save
      </button>
      <span class="overview__state">{{ saveState }}</span>
    </div>
  </section>
</template>

<style scoped>
.overview {
  max-width: 640px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.overview__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}
.overview__field input,
.overview__field textarea {
  padding: 8px 10px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
  resize: vertical;
}
.overview__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.overview__save {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: var(--accent);
  color: #fff;
  cursor: pointer;
}
.overview__save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.overview__state {
  font-size: 12px;
  color: var(--muted, #888);
}
</style>
