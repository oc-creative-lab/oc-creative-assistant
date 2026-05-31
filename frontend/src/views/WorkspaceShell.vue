<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useProjectStore } from '../stores/useProjectStore'
import { mockWorkspaceStatus } from '../mocks/workspaceMock'
import TopToolbar from '../components/workspace/TopToolbar.vue'
import WorkspaceSidebar from '../components/workspace/WorkspaceSidebar.vue'
import RightStageOutput from '../components/workspace/RightStageOutput.vue'
import BottomComposer from '../components/workspace/BottomComposer.vue'
import StatusBar from '../components/workspace/StatusBar.vue'

/**
 * 工作台外壳（second_revision 改点 B：写作友好型布局）。
 *
 * 四行：TopToolbar / 中部三栏 / BottomComposer / StatusBar。
 * 中部三列：WorkspaceSidebar(300) | router-view(1fr) | RightStageOutput(360)。
 * 工作台已废弃 FloatingChatDock，AI 改为底部常驻输入 + 右栏输出流。
 */
const props = defineProps<{ projectId: string }>()

const projectStore = useProjectStore()
const { detail } = storeToRefs(projectStore)

const projectName = computed(() => detail.value?.name ?? '正在加载项目...')

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
    <TopToolbar :project-name="projectName" :is-saving="false" />

    <main class="workspace-shell__body">
      <WorkspaceSidebar :project-id="projectId" />
      <div class="workspace-shell__center">
        <section class="workspace-shell__view">
          <router-view />
        </section>
        <BottomComposer />
      </div>
      <RightStageOutput />
    </main>

    <StatusBar :status="mockWorkspaceStatus" />
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
  min-height: 0;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 360px;
  border-top: 1px solid var(--border);
}
/* 中栏纵向拆成：视图(画布/详情, 1fr) + 底部提问条(auto)，提问条只占中栏宽度 */
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
