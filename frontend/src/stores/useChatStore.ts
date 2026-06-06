import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  AgentStagingBatchDto,
  AppliedEntityDto,
  ChatMessageDto,
  ChatSessionDto,
} from '../api/chatApi'
import {
  createChatSession,
  listProjectSessions,
  deleteChatSession,
  renameChatSession,
  listProjectStaging,
  listSessionMessages,
  resolveStagingBatch,
  resolveStagingItem,
  streamChat,
} from '../api/chatApi'
import { deleteNode as apiDeleteNode, updateNode as apiUpdateNode } from '../api/projectApi'

/** ChatWorkspace 里用的轻量消息模型（历史消息 + 本轮流式消息共用）。 */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agentType?: string
  /** 本轮后台自动落库的卡片（改造 1：对话内联展示）。 */
  applied?: AppliedEntityDto[]
}

/**
 * 全屏聊天 store。
 *
 * 负责会话生命周期、消息流（复用 streamChat SSE）、后台抽出的 staging 列表。
 * 开启 extraction_enabled，让 structured_extractor / question_planner 介入。
 */
export const useChatStore = defineStore('chat', () => {
  const projectId = ref('')
  const sessionId = ref('')
  const sessions = ref<ChatSessionDto[]>([])
  const messages = ref<ChatMessage[]>([])
  const streamingReply = ref('')
  const isStreaming = ref(false)
  const progressLabel = ref('')
  const lastAgent = ref('')
  const stagingBatches = ref<AgentStagingBatchDto[]>([])
  const error = ref('')

  function _toMessage(dto: ChatMessageDto): ChatMessage {
    return { id: dto.id, role: dto.role, content: dto.content, agentType: dto.meta?.agent_type }
  }

  /** 进入项目：加载全部会话并选中最近活跃的一个；没有会话就保持空，不创建。 */
  async function init(targetProjectId: string): Promise<void> {
    if (projectId.value === targetProjectId) return
    projectId.value = targetProjectId
    error.value = ''
    try {
      sessions.value = await listProjectSessions(targetProjectId)
      await refreshStaging()
      if (sessions.value.length) {
        await selectSession(sessions.value[0].id)
      } else {
        sessionId.value = ''
        messages.value = []
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load chats'
    }
  }

  /** 切换到指定会话，加载其消息历史。 */
  async function selectSession(targetSessionId: string): Promise<void> {
    if (!targetSessionId || sessionId.value === targetSessionId) return
    sessionId.value = targetSessionId
    error.value = ''
    try {
      messages.value = (await listSessionMessages(targetSessionId)).map(_toMessage)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to load messages'
    }
  }

  /** 删除会话; 若删的是当前会话, 自动切到最近一个或回到空白新会话。 */
  async function deleteSession(targetSessionId: string): Promise<void> {
    await deleteChatSession(targetSessionId)
    sessions.value = sessions.value.filter((s) => s.id !== targetSessionId)
    if (sessionId.value === targetSessionId) {
      if (sessions.value.length) {
        sessionId.value = ''
        await selectSession(sessions.value[0].id)
      } else {
        startNewSession()
      }
    }
    await refreshStaging()
  }

  /** 重命名会话, 同步更新列表里的标题。 */
  async function renameSession(targetSessionId: string, title: string): Promise<void> {
    const trimmed = title.trim()
    if (!trimmed) return
    const updated = await renameChatSession(targetSessionId, trimmed)
    const idx = sessions.value.findIndex((s) => s.id === targetSessionId)
    if (idx !== -1) sessions.value[idx] = updated
  }

  /** 开始新会话：仅清空当前视图；真正的会话行在首条消息发送时惰性创建。 */
  function startNewSession(): void {
    sessionId.value = ''
    messages.value = []
    streamingReply.value = ''
    error.value = ''
  }

  /** 拉取项目级待审 staging（后台抽出的实体）。 */
  async function refreshStaging(): Promise<void> {
    if (!projectId.value) return
    try {
      stagingBatches.value = await listProjectStaging(projectId.value, 'pending')
    } catch {
      /* staging 拉取失败不阻断聊天 */
    }
  }

  /** 发送一条消息，流式接收回复；extractionEnabled 控制后台自动抽取。 */
  async function send(
    text: string,
    quotedNodeIds: string[] = [],
    extractionEnabled = true,
  ): Promise<void> {
    const content = text.trim()
    if (!content || isStreaming.value || !projectId.value) return

    // 惰性创建：没有当前会话时，用首条消息（截断）作标题新建一个，避免空会话堆积
    if (!sessionId.value) {
      try {
        const session = await createChatSession(projectId.value, content.slice(0, 30))
        sessions.value.unshift(session)
        sessionId.value = session.id
      } catch (e) {
        error.value = e instanceof Error ? e.message : 'Failed to create chat'
        return
      }
    }

    messages.value.push({ id: `local-${Date.now()}`, role: 'user', content })
    streamingReply.value = ''
    progressLabel.value = 'Thinking…'
    lastAgent.value = ''
    isStreaming.value = true
    error.value = ''
    const appliedThisTurn: AppliedEntityDto[] = []

    try {
      await streamChat(
        sessionId.value,
        content,
        quotedNodeIds,
        (event) => {
          if (event.type === 'reply_token') {
            streamingReply.value += event.text
          } else if (event.type === 'node_end') {
            progressLabel.value = event.label
          } else if (event.type === 'intent') {
            lastAgent.value = event.primary
          } else if (event.type === 'reply_ready') {
            streamingReply.value = event.reply_text
          } else if (event.type === 'extraction_applied') {
            appliedThisTurn.push(...event.items)
          } else if (event.type === 'error') {
            error.value = event.message
          }
        },
        extractionEnabled,
      )
      // 落定本轮 assistant 消息（带上本轮自动落库的卡片）
      if (streamingReply.value) {
        messages.value.push({
          id: `asst-${Date.now()}`,
          role: 'assistant',
          content: streamingReply.value,
          agentType: lastAgent.value,
          applied: appliedThisTurn.length ? [...appliedThisTurn] : undefined,
        })
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Reply failed'
    } finally {
      streamingReply.value = ''
      progressLabel.value = ''
      isStreaming.value = false
      // 后台抽取在 persistence 之后完成，稍后刷新待审列表。
      await refreshStaging()
    }
  }

  /** 接受/拒绝整批 staging，然后刷新。 */
  async function resolveBatch(batchId: string, action: 'accept_all' | 'reject_all'): Promise<void> {
    await resolveStagingBatch(batchId, action)
    await refreshStaging()
  }

  /** 接受/拒绝单条 staging，然后刷新。 */
  async function resolveItem(stagingId: string, action: 'accept' | 'reject'): Promise<void> {
    await resolveStagingItem(stagingId, action)
    await refreshStaging()
  }

  /** 编辑某张内联卡片对应的节点标题/正文（改造 1）。 */
  async function editAppliedNode(
    nodeId: string,
    patch: { title?: string; content?: string },
  ): Promise<void> {
    if (!projectId.value) return
    await apiUpdateNode(projectId.value, nodeId, patch)
    for (const message of messages.value) {
      const item = message.applied?.find((a) => a.node_id === nodeId)
      if (item) {
        if (patch.title !== undefined) item.title = patch.title
        if (patch.content !== undefined) item.content = patch.content
      }
    }
  }

  /** 撤销（删除）某张内联卡片对应的节点（改造 1：默认已加入，可拒绝）。 */
  async function removeAppliedNode(nodeId: string): Promise<void> {
    if (!projectId.value) return
    await apiDeleteNode(projectId.value, nodeId)
    for (const message of messages.value) {
      if (message.applied) {
        message.applied = message.applied.filter((a) => a.node_id !== nodeId)
      }
    }
  }

  return {
    projectId,
    sessionId,
    sessions,
    messages,
    streamingReply,
    isStreaming,
    progressLabel,
    lastAgent,
    stagingBatches,
    error,
    init,
    selectSession,
    startNewSession,
    deleteSession,
    renameSession,
    send,
    refreshStaging,
    resolveBatch,
    resolveItem,
    editAppliedNode,
    removeAppliedNode,
  }
})
