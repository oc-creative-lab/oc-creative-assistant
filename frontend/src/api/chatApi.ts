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

/** 删除会话及其历史 / staging。 */
export async function deleteChatSession(sessionId: string): Promise<void> {
  await requestJson<void>(`/api/sessions/${sessionId}`, { method: 'DELETE' })
}

/** 重命名会话。 */
export async function renameChatSession(sessionId: string, title: string): Promise<ChatSessionDto> {
  return requestJson<ChatSessionDto>(`/api/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
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

/** 列出整个项目的 staging。 */
export async function listProjectStaging(
  projectId: string,
  status: AgentStagingItemDto['status'] | null = 'pending',
): Promise<AgentStagingBatchDto[]> {
  const query = status ? `?status=${status}` : ''
  return requestJson<AgentStagingBatchDto[]>(`/api/projects/${projectId}/staging${query}`)
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

/** SSE 事件类型, 与后端 chat_stream._sse 的 payload 对齐。 */
export type ChatStreamEvent =
  | { type: 'node_end'; node: string; label: string }
  | { type: 'intent'; primary: string; confidence: number }
  | { type: 'reply_token'; text: string }
  | {
      type: 'reply_ready'
      reply_text: string
      cited_node_ids: string[]
      staging_summary: string
    }
  | {
      type: 'persistence_done'
      message_id: string
      batch_id: string | null
      staging_count: number
    }
  | {
      type: 'extraction_applied'
      items: AppliedEntityDto[]
    }
  | { type: 'done' }
  | { type: 'error'; message: string }

/** 后台抽取并【自动落库】的卡片（改造 1：对话内联展示，默认已加入）。 */
export interface AppliedEntityDto {
  node_id: string
  title: string
  node_type: string
  content: string
  change_type: 'create_node' | 'update_node'
}

/**
 * 流式 chat: 后端 SSE, 前端 fetch + ReadableStream 解析。
 *
 * EventSource 不支持 POST + body, 所以走原生 fetch。每收到一个完整 SSE
 * data 行就调一次 onEvent, 让组件渐进更新 UI。
 */
export async function streamChat(
  sessionId: string,
  userMessage: string,
  selectedNodeIds: string[],
  onEvent: (event: ChatStreamEvent) => void,
  extractionEnabled = false,
): Promise<void> {
  const response = await fetch(`${backendBaseUrl}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      user_message: userMessage,
      selected_node_ids: selectedNodeIds,
      extraction_enabled: extractionEnabled,
    }),
  })

  if (!response.ok || !response.body) {
    throw new Error(`stream failed: HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    /* SSE 协议: 事件之间用 \n\n 分隔, 不完整的留在 buffer 等下一帧 */
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const raw of chunks) {
      const line = raw.trim()
      if (!line.startsWith('data: ')) continue
      try {
        const data = JSON.parse(line.slice(6)) as ChatStreamEvent
        onEvent(data)
      } catch {
        /* 跳过损坏 chunk, 让流继续 */
      }
    }
  }
}

/** 后端健康检查返回; boot_id 用于识别后端进程是否被重启过。 */
export interface HealthDto {
  status: string
  service: string
  boot_id: string
}

/**
 * 拉取后端 boot_id, 失败返回空串表示"无法识别"; 由调用方决定降级策略。
 */
export async function fetchBackendBootId(): Promise<string> {
  try {
    const data = await requestJson<HealthDto>('/health')
    return data.boot_id ?? ''
  } catch {
    return ''
  }
}

export { backendBaseUrl }