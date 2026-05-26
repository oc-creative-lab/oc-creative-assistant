import { backendBaseUrl, requestJson } from './http'

/** 对话会话 DTO; thread_id 给 LangGraph Checkpointer 使用。 */
export interface ChatSessionDto {
  id: string
  project_id: string
  thread_id: string
  title: string
  created_at: string
  updated_at: string
}

/** 单条对话消息 DTO; meta 携带 agent_type / cited_node_ids / staging_summary。 */
export interface ChatMessageDto {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  meta: {
    agent_type?: string
    cited_node_ids?: string[]
    staging_summary?: string
  }
  created_at: string
}

/** Agent 一轮推理后的对话回复 + staging 摘要。 */
export interface ChatResponseDto {
  message_id: string
  reply_text: string
  cited_node_ids: string[]
  intent: string
  batch_id: string | null
  staging_count: number
  staging_summary: string
}

/** staging 单项 DTO; 与后端 AgentStagingPayload 对齐。 */
export interface AgentStagingItemDto {
  id: string
  session_id: string
  message_id: string
  project_id: string
  batch_id: string
  change_type: 'create_node' | 'create_edge' | 'update_node' | 'delete_node' | 'delete_edge'
  target_id: string | null
  pending_id: string | null
  payload: Record<string, unknown>
  payload_edited: Record<string, unknown> | null
  agent_type: string
  reasoning: string
  order_in_batch: number
  status: 'pending' | 'accepted' | 'edited' | 'rejected'
  created_at: string
  resolved_at: string | null
}

/** staging 批次 DTO, 同 batch_id 的多条变更聚合展示。 */
export interface AgentStagingBatchDto {
  batch_id: string
  items: AgentStagingItemDto[]
}

/**
 * 创建对话会话; 同时分配 thread_id 用于 LangGraph 持久化。
 */
export async function createChatSession(projectId: string, title = ''): Promise<ChatSessionDto> {
  return requestJson<ChatSessionDto>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, title }),
  })
}

/** 列出指定项目下的会话, 创建时间倒序。 */
export async function listProjectSessions(projectId: string): Promise<ChatSessionDto[]> {
  return requestJson<ChatSessionDto[]>(`/api/projects/${projectId}/sessions`)
}

/** 读取会话完整消息历史, 时间正序。 */
export async function listSessionMessages(sessionId: string): Promise<ChatMessageDto[]> {
  return requestJson<ChatMessageDto[]>(`/api/sessions/${sessionId}/messages`)
}

/**
 * 触发 agent_graph 完整推理; 返回回复 + staging 摘要。
 * DeepSeek 单轮可能要等数十秒, 调用方应自行处理 loading 状态。
 */
export async function postChat(
  sessionId: string,
  userMessage: string,
  selectedNodeIds: string[] = [],
): Promise<ChatResponseDto> {
  return requestJson<ChatResponseDto>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      user_message: userMessage,
      selected_node_ids: selectedNodeIds,
    }),
  })
}

/** 列出当前会话的 staging, 默认只看 pending; 自动按 batch 分组。 */
export async function listSessionStaging(
  sessionId: string,
  status: AgentStagingItemDto['status'] | null = 'pending',
): Promise<AgentStagingBatchDto[]> {
  const query = status ? `?status=${status}` : ''
  return requestJson<AgentStagingBatchDto[]>(`/api/sessions/${sessionId}/staging${query}`)
}

/** 单条 staging 的 accept / edit / reject; 已结案再次操作返回 409。 */
export async function resolveStagingItem(
  stagingId: string,
  action: 'accept' | 'edit' | 'reject',
  payloadEdited?: Record<string, unknown>,
): Promise<AgentStagingItemDto> {
  return requestJson<AgentStagingItemDto>(`/api/staging/${stagingId}`, {
    method: 'PATCH',
    body: JSON.stringify({ action, payload_edited: payloadEdited ?? null }),
  })
}

/** 批量接受 / 拒绝同一 turn 的 staging; 已结案的项静默跳过。 */
export async function resolveStagingBatch(
  batchId: string,
  action: 'accept_all' | 'reject_all',
): Promise<AgentStagingItemDto[]> {
  return requestJson<AgentStagingItemDto[]>(`/api/staging/batch/${batchId}`, {
    method: 'PATCH',
    body: JSON.stringify({ action }),
  })
}

export { backendBaseUrl }