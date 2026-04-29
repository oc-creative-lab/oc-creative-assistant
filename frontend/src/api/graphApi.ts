import type { CreativeNodeStatus, CreativeNodeType, CreativeRelationType } from '../types/node'

// 后端项目 DTO：用于确定当前 graph 属于哪个项目。
export interface GraphProjectDto {
  id: string
  name: string
}

// 后端只关心画布坐标，不保存 Vue Flow 的 viewport 或 computedPosition。
export interface GraphPositionDto {
  x: number
  y: number
}

// 后端节点 DTO，content 对应前端节点卡片里的 summary。
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

// 后端边 DTO；handle 字段用于恢复从哪个连接点拉出的边。
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

// 读取接口返回的完整 graph 快照。
export interface GraphDto {
  project: GraphProjectDto
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
}

// 保存接口只需要节点和边；projectId 由 URL 参数提供。
export interface SaveGraphDto {
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
}

export interface RagContextRequestDto {
  node_id: string
  query: string
  agent_type: 'inspiration'
  top_k: number
}

export interface RagCurrentNodeDto {
  id: string
  type: string
  title: string
  content: string
  tags: string[]
}

export interface RagGraphContextItemDto {
  id: string
  type: string
  title: string
  content: string
  relation_label: string
  relation_type: string
  direction: string
}

export interface RagVectorContextItemDto {
  id: string
  type: string
  title: string
  content: string
  score: number
}

export interface RagMergedContextItemDto {
  id: string
  source: string
  type: string
  title: string
  content: string
}

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

// 桌面态优先使用 preload 注入的后端地址，浏览器开发态回退到 Vite 环境变量。
const backendBaseUrl = (
  window.ocDesktop?.config.backendUrl ||
  import.meta.env.VITE_BACKEND_URL ||
  'http://127.0.0.1:9000'
).replace(/\/$/, '')

// 统一封装 fetch，避免组件里散落后端地址和错误处理。
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

// 先获取默认项目，再读取该项目 graph，保证首次启动时后端会自动初始化数据。
export async function loadDefaultGraph(): Promise<GraphDto> {
  const project = await requestJson<GraphProjectDto>('/api/projects/default')

  return requestJson<GraphDto>(`/api/projects/${project.id}/graph`)
}

// 手动保存当前画布快照，后端会整体替换项目下的 nodes / edges。
export async function saveProjectGraph(projectId: string, graph: SaveGraphDto): Promise<GraphDto> {
  return requestJson<GraphDto>(`/api/projects/${projectId}/graph`, {
    method: 'PUT',
    body: JSON.stringify(graph),
  })
}

// 当前功能只用于调试 RAG 上下文和 prompt，不是真正 Agent/LLM 调用。
export async function loadRagContext(payload: RagContextRequestDto): Promise<RagContextResponseDto> {
  return requestJson<RagContextResponseDto>('/api/rag/context', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
