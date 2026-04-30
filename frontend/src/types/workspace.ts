/** 旧项目列表分组 id，保留给 mock/兼容代码；左侧主入口已改为节点工具栏。 */
export type ProjectGroupId = 'ideas' | 'characters' | 'worldbuilding' | 'plot' | 'research' | 'structure'

/** 右侧 Agent 面板的工作模式。 */
export type AgentMode = 'inspiration' | 'research' | 'structure'

/** sidebar、当前节点卡片和 Agent 面板共享的节点摘要形态。 */
export interface ProjectItem {
  id: string
  title: string
  kind: string
  summary: string
  meta: string
}

/** 左侧项目面板按业务类型组织节点条目。 */
export interface ProjectGroup {
  id: ProjectGroupId
  title: string
  items: ProjectItem[]
}

/** 右侧 Agent 面板的建议卡片，目前来自 mock 数据。 */
export interface AgentSuggestion {
  id: string
  title: string
  body: string
}

/** 底部状态栏聚合保存、索引和模型三类运行状态。 */
export interface WorkspaceStatus {
  saveState: string
  indexState: string
  modelState: string
}
