export type ProjectGroupId = 'characters' | 'worldbuilding' | 'plot' | 'materials'

export type AgentMode = 'inspiration' | 'research' | 'structure'

export interface ProjectItem {
  id: string
  title: string
  kind: string
  summary: string
  meta: string
}

export interface ProjectGroup {
  id: ProjectGroupId
  title: string
  items: ProjectItem[]
}

export interface AgentSuggestion {
  id: string
  title: string
  body: string
}

export interface WorkspaceStatus {
  saveState: string
  indexState: string
  modelState: string
}
