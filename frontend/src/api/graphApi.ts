import type { CreativeNodeStatus, CreativeNodeType, CreativeRelationType } from '../types/node'

/** 后端项目 DTO，用于确定当前 graph 的生命周期边界。 */
export interface GraphProjectDto {
  id: string
  name: string
}

/** 后端保存的节点坐标；不包含 Vue Flow viewport 或 computedPosition。 */
export interface GraphPositionDto {
  x: number
  y: number
}

/** 后端节点 DTO，content 对应前端节点全文内容。 */
export interface GraphNodeDto {
  id: string
  type: CreativeNodeType
  nodeType?: CreativeNodeType | null
  title: string
  content: string
  position: GraphPositionDto
  meta: string
  typeLabel: string
  tags?: string[]
  status?: CreativeNodeStatus
}

/** 后端边 DTO；handle 字段用于恢复从哪个连接点拉出的边。 */
export interface GraphEdgeDto {
  id: string
  source: string
  target: string
  label: string
  relationType?: CreativeRelationType
  sourceHandle?: string | null
  targetHandle?: string | null
  type: string
  animated: boolean
}

/** 后端向量索引状态；SQLite 保存成功不代表 embedding 一定成功，因此需要单独展示。 */
export interface IndexingStatusDto {
  status: 'not_checked' | 'synced' | 'partial' | 'failed'
  message: string
  provider: string
  model: string
  dimension: number
  expected_nodes: number
  indexed_nodes: number
  missing_node_ids: string[]
  error?: string | null
}

/** 读取接口返回的完整 graph 快照。 */
export interface GraphDto {
  project: GraphProjectDto
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
  indexing?: IndexingStatusDto
}

/** 保存接口请求体；projectId 由 URL 参数提供。 */
export interface SaveGraphDto {
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
}

/** RAG 上下文预览请求体；当前只支持 inspiration 调试入口。 */
export interface RagContextRequestDto {
  node_id: string
  query: string
  agent_type: 'inspiration'
  top_k: number
}

/** RAG 响应中的当前节点快照。 */
export interface RagCurrentNodeDto {
  id: string
  type: string
  title: string
  content: string
  tags: string[]
}

/** 由画布连线推导的一跳图关系上下文。 */
export interface RagGraphContextItemDto {
  id: string
  type: string
  title: string
  content: string
  relation_label: string
  relation_type: string
  direction: string
}

/** 向量检索命中的相似节点上下文。 */
export interface RagVectorContextItemDto {
  id: string
  type: string
  title: string
  content: string
  score: number
}

/** 后端合并去重后的上下文条目。 */
export interface RagMergedContextItemDto {
  id: string
  source: string
  type: string
  title: string
  content: string
}

/** RAG 上下文预览接口响应。 */
export interface RagContextResponseDto {
  current_node: RagCurrentNodeDto
  graph_context: RagGraphContextItemDto[]
  vector_context: RagVectorContextItemDto[]
  merged_context: RagMergedContextItemDto[]
  prompt: string
  debug: {
    query_used: string
    top_k: number
    vector_store: string
    llm_called: boolean
    vector_error?: string | null
  }
}

/* 桌面态优先使用 preload 注入的后端地址，浏览器开发态回退到 Vite 环境变量。 */
const backendBaseUrl = (
  window.ocDesktop?.config.backendUrl ||
  import.meta.env.VITE_BACKEND_URL ||
  'http://127.0.0.1:9000'
).replace(/\/$/, '')

/**
 * 统一请求后端 JSON 接口。
 *
 * Args:
 *   path: 以 `/api` 开头的后端路径。
 *   init: fetch 请求配置。
 *
 * Returns:
 *   反序列化后的响应体。
 *
 * Throws:
 *   Error: 当后端返回非 2xx 状态时抛出。
 */
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return (await response.json()) as T
}

/**
 * 加载默认项目的 graph。
 *
 * 首次启动时会先访问默认项目接口，触发后端初始化示例数据。
 *
 * Returns:
 *   默认项目的完整 graph DTO。
 */
export async function loadDefaultGraph(): Promise<GraphDto> {
  const project = await requestJson<GraphProjectDto>('/api/projects/default')

  return requestJson<GraphDto>(`/api/projects/${project.id}/graph`)
}

/**
 * 保存项目 graph 快照。
 *
 * 后端采用整图替换策略，并在 SQLite 提交后同步向量索引。
 *
 * Args:
 *   projectId: 当前项目 ID。
 *   graph: 需要保存的节点和边快照。
 *
 * Returns:
 *   后端最终落库后的 graph DTO。
 */
export async function saveProjectGraph(projectId: string, graph: SaveGraphDto): Promise<GraphDto> {
  return requestJson<GraphDto>(`/api/projects/${projectId}/graph`, {
    method: 'PUT',
    body: JSON.stringify(graph),
  })
}

/**
 * 加载 RAG 上下文预览。
 *
 * 当前接口只用于调试图关系、向量结果和 prompt，不会调用真正 LLM。
 *
 * Args:
 *   payload: RAG 上下文预览请求体。
 *
 * Returns:
 *   后端构造的上下文和 prompt。
 */
export async function loadRagContext(payload: RagContextRequestDto): Promise<RagContextResponseDto> {
  return requestJson<RagContextResponseDto>('/api/rag/context', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
