import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { ProjectDetail } from '../types/project'
import { getProjectDetail } from '../api/projectApi'

/**
 * 当前项目 store。
 *
 * 持有当前打开项目的元数据：name / description / 三个 sub-graph id / 最新种子。
 * 工作台三视图从这里取对应的 graph_id。
 */
export const useProjectStore = defineStore('project', () => {
  const detail = ref<ProjectDetail | null>(null)
  const isLoading = ref(false)
  const error = ref('')

  const plotGraphId = computed(() => detail.value?.plot_graph_id ?? null)
  const characterGraphId = computed(() => detail.value?.character_graph_id ?? null)
  const worldGraphId = computed(() => detail.value?.world_graph_id ?? null)

  /** 加载指定项目详情；若已是当前项目可强制刷新。 */
  async function loadProject(projectId: string, force = false): Promise<void> {
    if (!force && detail.value?.id === projectId) return
    isLoading.value = true
    error.value = ''
    try {
      detail.value = await getProjectDetail(projectId)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load project'
      detail.value = null
    } finally {
      isLoading.value = false
    }
  }

  /** 清空当前项目（退出工作台时调用）。 */
  function reset(): void {
    detail.value = null
    error.value = ''
  }

  return {
    detail,
    isLoading,
    error,
    plotGraphId,
    characterGraphId,
    worldGraphId,
    loadProject,
    reset,
  }
})
