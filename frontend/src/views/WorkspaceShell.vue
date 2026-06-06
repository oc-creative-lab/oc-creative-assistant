<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import { loadSubgraph, saveSubgraph } from '../api/graphApi'
import { downloadProjectOcFile, readProjectOcFile } from '../utils/ocFile'
import { useProjectStore } from '../stores/useProjectStore'
import TopToolbar from '../components/workspace/TopToolbar.vue'
import WorkspaceSidebar from '../components/workspace/WorkspaceSidebar.vue'
import RightStageOutput from '../components/workspace/RightStageOutput.vue'
import BottomComposer from '../components/workspace/BottomComposer.vue'
import SettingsModal from '../components/workspace/SettingsModal.vue'
import { provideWorkspaceChatContext } from '../composables/useWorkspaceChatContext'

const props = defineProps<{ projectId: string }>()

const projectStore = useProjectStore()
const { detail, plotGraphId, characterGraphId, worldGraphId } = storeToRefs(projectStore)
const route = useRoute()

/** 当前所在画布对应的 sub-graph；Overview 等非画布视图为 null。 */
const currentGraphId = computed(() => {
  switch (route.name) {
    case 'workspace-plot':
      return plotGraphId.value
    case 'workspace-characters':
    case 'workspace-character-detail':
      return characterGraphId.value
    case 'workspace-world':
      return worldGraphId.value
    default:
      return null
  }
})

const fileInput = ref<HTMLInputElement | null>(null)

  async function handleExport() {
  const story = plotGraphId.value
  const characters = characterGraphId.value
  const world = worldGraphId.value
  if (!story || !characters || !world) {
    window.alert('Project graphs are still loading. Try again in a moment.')
    return
  }
  const [storyGraph, charactersGraph, worldGraph] = await Promise.all([
    loadSubgraph(story),
    loadSubgraph(characters),
    loadSubgraph(world),
  ])
  downloadProjectOcFile(detail.value?.name ?? 'project', {
    story: storyGraph,
    characters: charactersGraph,
    world: worldGraph,
  })
}

function handleImport() {
  if (!plotGraphId.value || !characterGraphId.value || !worldGraphId.value) {
    window.alert('Project graphs are still loading. Try again in a moment.')
    return
  }
  fileInput.value?.click()
}

async function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  const story = plotGraphId.value
  const characters = characterGraphId.value
  const world = worldGraphId.value
  if (!file || !story || !characters || !world) return
  try {
    const boards = await readProjectOcFile(file)
    if (
      !window.confirm(
        'Importing will overwrite Story, Characters and Worldbuilding on this project. Continue?',
      )
    )
      return
    await saveSubgraph(story, boards.story)
    await saveSubgraph(characters, boards.characters)
    await saveSubgraph(world, boards.world)
    await triggerGraphRefresh()
  } catch (e) {
    window.alert(e instanceof Error ? e.message : 'Import failed')
  }
}

const settingsOpen = ref(false)
function handleSettings() {
  settingsOpen.value = true
}

async function handleSave() {
  if (!currentGraphId.value) {
    window.alert('Open a canvas (Story / Characters / Worldbuilding) before saving.')
    return
  }
  await triggerGraphSave()
}

const { triggerGraphRefresh, triggerGraphSave, isSaving } = provideWorkspaceChatContext()

const leftWidth = ref(Math.max(160, Number(localStorage.getItem('oc.leftWidth')) || 300))
const rightWidth = ref(Math.max(500, Number(localStorage.getItem('oc.rightWidth')) || 520))
watch([leftWidth, rightWidth], ([l, r]) => {
  localStorage.setItem('oc.leftWidth', String(l))
  localStorage.setItem('oc.rightWidth', String(r))
})
const leftCollapsed = ref(localStorage.getItem('oc.leftCollapsed') === 'true')
const rightCollapsed = ref(localStorage.getItem('oc.rightCollapsed') === 'true')
const RAIL_WIDTH = 40
const gridColumns = computed(
  () =>
    `${leftCollapsed.value ? RAIL_WIDTH : leftWidth.value}px minmax(0, 1fr) ${rightCollapsed.value ? RAIL_WIDTH : rightWidth.value}px`,
)

let activeSide: 'left' | 'right' | null = null
let startX = 0
let startWidth = 0

function startResize(side: 'left' | 'right', event: MouseEvent) {
  event.preventDefault()
  activeSide = side
  startX = event.clientX
  startWidth = side === 'left' ? leftWidth.value : rightWidth.value
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', stopResize)
}

function onResize(event: MouseEvent) {
  if (!activeSide) return
  const delta = event.clientX - startX
  if (activeSide === 'left') {
    leftWidth.value = Math.min(480, Math.max(160, startWidth + delta))
  } else {
    rightWidth.value = Math.min(760, Math.max(280, startWidth - delta))
  }
}

function stopResize() {
  activeSide = null
  document.body.style.userSelect = ''
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
}

onBeforeUnmount(stopResize)

const projectName = computed(() => detail.value?.name ?? 'Loading project...')

onMounted(() => {
  void projectStore.loadProject(props.projectId)
})

watch(
  () => props.projectId,
  (id) => {
    void projectStore.loadProject(id)
  },
)
</script>

<template>
  <div class="workspace-shell">
    <TopToolbar
      :project-name="projectName"
      :is-saving="isSaving"
      @save="handleSave"
      @settings="handleSettings"
    />
    <input
      ref="fileInput"
      type="file"
      accept=".oc,application/json"
      hidden
      @change="onFilePicked"
    />
    <SettingsModal
      :open="settingsOpen"
      @close="settingsOpen = false"
      @export="handleExport"
      @import="handleImport"
    />

    <main class="workspace-shell__body" :style="{ gridTemplateColumns: gridColumns }">
      <WorkspaceSidebar
        style="grid-column: 1"
        :project-id="projectId"
        :collapsed="leftCollapsed"
        @toggle="leftCollapsed = !leftCollapsed"
      />
      <div class="workspace-shell__center" style="grid-column: 2">
        <section class="workspace-shell__view">
          <router-view />
        </section>
        <BottomComposer />
      </div>
      <RightStageOutput
        style="grid-column: 3"
        :collapsed="rightCollapsed"
        @toggle="rightCollapsed = !rightCollapsed"
      />

      <div
        v-show="!leftCollapsed"
        class="workspace-shell__resizer"
        :style="{ left: `${leftWidth}px` }"
        @mousedown="startResize('left', $event)"
      ></div>
      <div
        v-show="!rightCollapsed"
        class="workspace-shell__resizer"
        :style="{ left: `calc(100% - ${rightWidth}px)` }"
        @mousedown="startResize('right', $event)"
      ></div>
    </main>
  </div>
</template>

<style scoped>
.workspace-shell {
  height: 100vh;
  display: grid;
  grid-template-rows: 56px minmax(0, 1fr) auto;
  background: var(--app-bg);
  color: var(--text);
  overflow: hidden;
}
.workspace-shell__body {
  position: relative;
  min-height: 0;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 360px;
  border-top: 1px solid var(--border);
}
.workspace-shell__resizer {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 8px;
  transform: translateX(-50%);
  cursor: col-resize;
  z-index: 5;
}
.workspace-shell__resizer:hover {
  background: var(--accent-soft);
}
.workspace-shell__center {
  min-width: 0;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
}
.workspace-shell__view {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}
@media (max-width: 1120px) {
  .workspace-shell__body {
    grid-template-columns: 260px minmax(0, 1fr) 320px;
  }
}
</style>
