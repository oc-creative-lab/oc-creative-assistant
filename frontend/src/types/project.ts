/**
 * 项目 / sub-graph / 种子相关类型。
 *
 * 字段命名与后端 DTO 对齐（snake_case），避免在 API 边界再做一层转换。
 */

/** sub-graph 分区。 */
export type GraphSection = 'plot' | 'character' | 'world'

/** 项目种子。 */
export interface ProjectSeed {
  id: string
  project_id: string
  version: number
  seed_json: string
  source: 'chat_end' | 'user_edit'
  created_at?: string | null
}

/** sub-graph 元信息。 */
export interface GraphInfo {
  id: string
  project_id: string
  section: GraphSection
}

/** 项目库卡片所需的概览信息。 */
export interface ProjectSummary {
  id: string
  name: string
  description: string
  created_at?: string | null
  updated_at?: string | null
}

/** 项目详情：含三个 sub-graph id 与最新种子。 */
export interface ProjectDetail {
  id: string
  name: string
  description: string
  plot_graph_id: string | null
  character_graph_id: string | null
  world_graph_id: string | null
  latest_seed: ProjectSeed | null
  created_at?: string | null
  updated_at?: string | null
}

/** 创建项目请求体。 */
export interface ProjectCreatePayload {
  name: string
  description?: string
}
