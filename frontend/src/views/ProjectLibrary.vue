<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useLibraryStore } from '../stores/useLibraryStore'

/**
 * Library（阶段 2）。
 *
 * 项目卡片网格：每卡 name / description / updated_at，点击进工作台。
 * 复用 useLibraryStore + projectApi，不重复实现请求逻辑。
 */
const router = useRouter()
const library = useLibraryStore()
const { projects, isLoading, error } = storeToRefs(library)

const isCreating = ref(false)
const newName = ref('')
const newDescription = ref('')

onMounted(() => {
  library.fetchProjects()
})

function openProject(projectId: string): void {
  router.push(`/workspace/${projectId}`)
}

async function handleCreate(): Promise<void> {
  const name = newName.value.trim()
  if (!name) return
  const detail = await library.createProject({
    name,
    description: newDescription.value.trim(),
  })
  isCreating.value = false
  newName.value = ''
  newDescription.value = ''
  router.push(`/workspace/${detail.id}`)
}

async function handleDelete(projectId: string, event: MouseEvent): Promise<void> {
  event.stopPropagation()
  await library.removeProject(projectId)
}

function formatTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString()
}
</script>

<template>
  <main class="library">
    <header class="library__header">
      <button type="button" class="library__back" @click="router.push('/')">← Home</button>
      <h1>Library</h1>
      <button type="button" class="library__new" @click="isCreating = true">+ New project</button>
    </header>

    <p v-if="error" class="library__error">{{ error }}</p>
    <p v-else-if="isLoading" class="library__hint">Loading…</p>
    <p v-else-if="projects.length === 0" class="library__hint">No projects yet — create one from the top-right.</p>

    <section v-else class="library__grid">
      <article
        v-for="project in projects"
        :key="project.id"
        class="project-card"
        @click="openProject(project.id)"
      >
        <h3 class="project-card__name">{{ project.name }}</h3>
        <p class="project-card__desc">{{ project.description || 'No description' }}</p>
        <footer class="project-card__footer">
          <span class="project-card__time">{{ formatTime(project.updated_at) }}</span>
          <button type="button" class="project-card__del" @click="handleDelete(project.id, $event)">
            Delete
          </button>
        </footer>
      </article>
    </section>

    <div v-if="isCreating" class="library__modal" @click.self="isCreating = false">
      <div class="library__dialog">
        <h2>New project</h2>
        <input v-model="newName" type="text" placeholder="Project name" />
        <textarea v-model="newDescription" placeholder="Description (optional)" rows="3"></textarea>
        <div class="library__dialog-actions">
          <button type="button" @click="isCreating = false">Cancel</button>
          <button type="button" class="primary" :disabled="!newName.trim()" @click="handleCreate">
            Create
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.library {
  min-height: 100vh;
  padding: 24px 32px;
}
.library__header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.library__header h1 {
  flex: 1;
  font-size: 22px;
}
.library__back,
.library__new {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--border, #ddd);
  background: var(--app-bg, #fff);
  cursor: pointer;
}
.library__new {
  border-color: var(--accent);
  color: var(--accent);
}
.library__hint,
.library__error {
  color: #888;
}
.library__error {
  color: #dc2626;
}
.library__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.project-card {
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 120px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.project-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.12);
}
.project-card__name {
  font-size: 16px;
  font-weight: 600;
}
.project-card__desc {
  flex: 1;
  color: #666;
  font-size: 13px;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.project-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.project-card__time {
  font-size: 12px;
  color: #aaa;
}
.project-card__del {
  font-size: 12px;
  color: #dc2626;
  background: none;
  border: none;
  cursor: pointer;
}
.library__modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
}
.library__dialog {
  background: var(--app-bg, #fff);
  border-radius: 12px;
  padding: 24px;
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.library__dialog input,
.library__dialog textarea {
  padding: 8px 10px;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  font: inherit;
  resize: vertical;
}
.library__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.library__dialog-actions button {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--border, #ddd);
  background: var(--app-bg, #fff);
  cursor: pointer;
}
.library__dialog-actions .primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.library__dialog-actions .primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
