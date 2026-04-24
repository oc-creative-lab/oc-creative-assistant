import type { CreativeNodeType } from '../types/node'

export interface GraphProjectDto {
  id: string
  name: string
}

export interface GraphPositionDto {
  x: number
  y: number
}

export interface GraphNodeDto {
  id: string
  type: CreativeNodeType
  title: string
  content: string
  position: GraphPositionDto
  meta: string
  typeLabel: string
}

export interface GraphEdgeDto {
  id: string
  source: string
  target: string
  label: string
  sourceHandle?: string | null
  targetHandle?: string | null
  type: string
  animated: boolean
}

export interface GraphDto {
  project: GraphProjectDto
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
}

export interface SaveGraphDto {
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
}

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
