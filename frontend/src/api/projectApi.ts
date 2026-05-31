import type {
  ProjectCreatePayload,
  ProjectDetail,
  ProjectSeed,
  ProjectSummary,
} from '../types/project'
import { requestJson } from './http'

/**
 * 项目 API 客户端（first_revision 阶段 1）。
 *
 * 与后端 /api/projects/* 对应。sub-graph 的节点/边读写仍走 graphApi 的
 * loadSubgraph / saveSubgraph（按 graph_id）。
 */

/** 列出全部项目（项目库卡片）。 */
export async function listProjects(): Promise<ProjectSummary[]> {
  return requestJson<ProjectSummary[]>('/api/projects')
}

/** 创建项目，后端自动创建三个 sub-graph。 */
export async function createProject(payload: ProjectCreatePayload): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 读取项目详情（含三个 graph_id 与最新种子）。 */
export async function getProjectDetail(projectId: string): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>(`/api/projects/${projectId}`)
}

/** 更新项目 name / description（项目概览页编辑简介用）。 */
export async function updateProject(
  projectId: string,
  payload: { name?: string; description?: string },
): Promise<ProjectDetail> {
  return requestJson<ProjectDetail>(`/api/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/** 读取节点自由字段（角色卡）。 */
export async function getNodeFields(
  projectId: string,
  nodeId: string,
): Promise<{ node_id: string; fields: Record<string, string> }> {
  return requestJson(`/api/projects/${projectId}/nodes/${nodeId}/fields`)
}

/** 整体替换节点自由字段（角色卡）。 */
export async function saveNodeFields(
  projectId: string,
  nodeId: string,
  fields: Record<string, string>,
): Promise<{ node_id: string; fields: Record<string, string> }> {
  return requestJson(`/api/projects/${projectId}/nodes/${nodeId}/fields`, {
    method: 'PUT',
    body: JSON.stringify({ node_id: nodeId, fields }),
  })
}

/** 一条跨 sub-graph 引用。 */
export interface CrossReferenceItem {
  edge_id: string
  other_node_id: string
  other_title: string
  other_section: 'plot' | 'character' | 'world'
  relation_type: string
  relation_label: string
  direction: 'outgoing' | 'incoming'
}

/** 节点在其它 sub-graph 中被引用的位置（first_revision 阶段 6）。 */
export interface CrossReferenceResponse {
  node_id: string
  section: 'plot' | 'character' | 'world' | null
  references: CrossReferenceItem[]
}

/** 更新节点字段（内联卡片"编辑" + 节点详情页共用，复用 graph 的 PATCH node 端点）。 */
export async function updateNode(
  projectId: string,
  nodeId: string,
  patch: {
    title?: string
    content?: string
    tags?: string[]
    status?: string
    nodeType?: string
  },
): Promise<unknown> {
  return requestJson(`/api/projects/${projectId}/nodes/${nodeId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

/** 删除节点（对话内联卡片"拒绝/撤销"用）。 */
export async function deleteNode(projectId: string, nodeId: string): Promise<void> {
  await requestJson<void>(`/api/projects/${projectId}/nodes/${nodeId}`, { method: 'DELETE' })
}

/** 读取节点的跨 sub-graph 反向引用。 */
export async function getNodeCrossReferences(
  projectId: string,
  nodeId: string,
): Promise<CrossReferenceResponse> {
  return requestJson<CrossReferenceResponse>(
    `/api/projects/${projectId}/nodes/${nodeId}/cross_references`,
  )
}

/** 级联删除项目。 */
export async function deleteProject(projectId: string): Promise<void> {
  await requestJson<void>(`/api/projects/${projectId}`, { method: 'DELETE' })
}

/** 读取项目当前种子；尚无种子时后端返回 404。 */
export async function getProjectSeed(projectId: string): Promise<ProjectSeed> {
  return requestJson<ProjectSeed>(`/api/projects/${projectId}/seed`)
}

/** 强制重建项目种子，版本自增。 */
export async function rebuildProjectSeed(projectId: string): Promise<ProjectSeed> {
  return requestJson<ProjectSeed>(`/api/projects/${projectId}/seed/rebuild`, {
    method: 'POST',
  })
}
