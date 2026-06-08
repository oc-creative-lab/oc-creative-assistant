import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  AgentStagingBatchDto,
  AppliedEntityDto,
  ChatMessageDto,
  ChatSessionDto,
  RelatedNodeDto,
  WebSearchMode,
  WebSourceDto,
} from '../api/chatApi'
import {
  createChatSession,
  deleteChatSession,
  generateSessionTitle,
  listProjectSessions,
  listProjectStaging,
  listSessionMessages,
  renameChatSession,
  resolveStagingBatch,
  resolveStagingItem,
  streamChat,
} from '../api/chatApi'
import { deleteNode as apiDeleteNode, updateNode as apiUpdateNode } from '../api/projectApi'

/** The lightweight message model used in ChatWorkspace (shared by historical messages + this turn's streaming message). */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agentType?: string
  /** Cards auto-persisted in the background this turn (revamp 1: inline display in chat). */
  applied?: AppliedEntityDto[]
  /** Web search source links (research / external facts). */
  webSources?: WebSourceDto[]
  /** Related nodes (cited in the reply). */
  relatedNodes?: RelatedNodeDto[]
}

/**
 * Full-screen chat store (first_revision phase 4).
 *
 * Handles the session lifecycle, message stream (reusing streamChat SSE), and the staging list extracted in the background.
 * Enables extraction_enabled so that structured_extractor / question_planner step in.
 */
export const useChatStore = defineStore('chat', () => {
  const projectId = ref('')
  const sessionId = ref('')
  const sessions = ref<ChatSessionDto[]>([])
  const messages = ref<ChatMessage[]>([])
  const streamingReply = ref('')
  const streamingWebSources = ref<WebSourceDto[]>([])
  const isStreaming = ref(false)
  const progressLabel = ref('')
  const lastAgent = ref('')
  const stagingBatches = ref<AgentStagingBatchDto[]>([])
  const error = ref('')

  function _toMessage(dto: ChatMessageDto): ChatMessage {
    return {
      id: dto.id,
      role: dto.role,
      content: dto.content,
      agentType: dto.meta?.agent_type,
      webSources: dto.meta?.web_sources?.length ? dto.meta.web_sources : undefined,
    }
  }

  /** Enter a project: load the session list, reuse the most recent one (don't auto-create on refresh). */
  async function init(targetProjectId: string): Promise<void> {
    if (projectId.value === targetProjectId && sessionId.value) return
    projectId.value = targetProjectId
    error.value = ''
    try {
      sessions.value = await listProjectSessions(targetProjectId)
      const session = sessions.value[0] ?? (await createChatSession(targetProjectId, 'New chat'))
      if (!sessions.value.length) sessions.value = [session]
      await switchSession(session.id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to start chat'
    }
  }

  /** Reload the session list from the backend. */
  async function loadSessions(): Promise<void> {
    if (!projectId.value) return
    sessions.value = await listProjectSessions(projectId.value)
  }

  /** Switch to a session and load its history + pending staging. */
  async function switchSession(id: string): Promise<void> {
    if (!id) return
    sessionId.value = id
    messages.value = (await listSessionMessages(id)).map(_toMessage)
    await refreshStaging()
  }

  /** Create a fresh chat session and switch to it (explicit user action only). */
  async function newSession(): Promise<void> {
    if (!projectId.value) return
    const session = await createChatSession(projectId.value, 'New chat')
    sessions.value = [session, ...sessions.value]
    sessionId.value = session.id
    messages.value = []
    await refreshStaging()
  }

  /** Delete a session; if it was the active one, fall back to the most recent remaining (or a new one). */
  async function deleteSession(id: string): Promise<void> {
    await deleteChatSession(id)
    sessions.value = sessions.value.filter((s) => s.id !== id)
    if (sessionId.value === id) {
      if (sessions.value.length) await switchSession(sessions.value[0].id)
      else await newSession()
    }
  }

  /** Rename a session and sync the local list. */
  async function renameSession(id: string, title: string): Promise<void> {
    const updated = await renameChatSession(id, title)
    sessions.value = sessions.value.map((s) => (s.id === id ? updated : s))
  }

  /** Fetch the project-level pending staging (entities extracted in the background). */
  async function refreshStaging(): Promise<void> {
    if (!projectId.value) return
    try {
      stagingBatches.value = await listProjectStaging(projectId.value, 'pending')
    } catch {
      /* a failed staging fetch does not block chat */
    }
  }

  let onGraphMutated: (() => void | Promise<void>) | null = null

  function setGraphMutatedHandler(handler: (() => void | Promise<void>) | null) {
    onGraphMutated = handler
  }

  async function notifyGraphMutated() {
    if (onGraphMutated) await onGraphMutated()
  }

  /** Send a message, enable background extraction, and receive the reply via streaming. */
  async function send(
    text: string,
    selectedNodeIds: string[] = [],
    webSearchMode: WebSearchMode = 'auto',
  ): Promise<void> {
    const content = text.trim()
    if (!content || !sessionId.value || isStreaming.value) return

    const isFirstTurn = messages.value.length === 0
    const turnSessionId = sessionId.value
    messages.value.push({ id: `local-${Date.now()}`, role: 'user', content })
    streamingReply.value = ''
    streamingWebSources.value = []
    progressLabel.value = 'Thinking…'
    isStreaming.value = true
    error.value = ''
    const appliedThisTurn: AppliedEntityDto[] = []
    let relatedThisTurn: RelatedNodeDto[] = []
    let stagingApplied = false

    try {
      await streamChat(
        sessionId.value,
        content,
        selectedNodeIds,
        (event) => {
          if (event.type === 'reply_token') {
            streamingReply.value += event.text
          } else if (event.type === 'node_end') {
            progressLabel.value = event.label
          } else if (event.type === 'intent') {
            lastAgent.value = event.primary
          } else if (event.type === 'reply_ready') {
            streamingReply.value = event.reply_text
            streamingWebSources.value = event.web_sources?.length ? [...event.web_sources] : []
            relatedThisTurn = event.related_nodes?.length ? [...event.related_nodes] : []
          } else if (event.type === 'extraction_applied') {
            appliedThisTurn.push(...event.items)
          } else if (event.type === 'persistence_done') {
            if (event.staging_count > 0) stagingApplied = true
          } else if (event.type === 'error') {
            const parts = [event.message]
            if (event.debug?.traceback) {
              parts.push(event.debug.traceback)
            }
            error.value = parts.join('\n\n')
          }
        },
        true, // extraction_enabled
        webSearchMode,
      )
      // finalize this turn's assistant message (with the cards auto-persisted this turn)
      if (streamingReply.value) {
        messages.value.push({
          id: `asst-${Date.now()}`,
          role: 'assistant',
          content: streamingReply.value,
          agentType: lastAgent.value,
          applied: appliedThisTurn.length ? [...appliedThisTurn] : undefined,
          webSources: streamingWebSources.value.length ? [...streamingWebSources.value] : undefined,
          relatedNodes: relatedThisTurn.length ? [...relatedThisTurn] : undefined,
        })
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Reply failed'
    } finally {
      streamingReply.value = ''
      streamingWebSources.value = []
      progressLabel.value = ''
      isStreaming.value = false
      if (appliedThisTurn.length || stagingApplied) {
        await notifyGraphMutated()
      }
      await refreshStaging()
      if (isFirstTurn) {
        try {
          const updated = await generateSessionTitle(turnSessionId, content)
          sessions.value = sessions.value.map((s) => (s.id === updated.id ? updated : s))
        } catch {
          /* title generation is best-effort */
        }
      }
    }
  }

  async function resolveBatch(batchId: string, action: 'accept_all' | 'reject_all'): Promise<void> {
    await resolveStagingBatch(batchId, action)
    await refreshStaging()
    if (action === 'accept_all') await notifyGraphMutated()
  }

  /** Accept/reject a single staging item, then refresh. */
  async function resolveItem(stagingId: string, action: 'accept' | 'reject'): Promise<void> {
    await resolveStagingItem(stagingId, action)
    await refreshStaging()
    if (action === 'accept') await notifyGraphMutated()
  }

  /** Edit the title/body of the node behind a given inline card (revamp 1). */
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

  /** Undo (delete) the node behind a given inline card (revamp 1: added by default, can be rejected). */
  async function removeAppliedNode(nodeId: string): Promise<void> {
    if (!projectId.value) return
    await apiDeleteNode(projectId.value, nodeId)
    for (const message of messages.value) {
      if (message.applied) {
        message.applied = message.applied.filter((a) => a.node_id !== nodeId)
      }
    }
    await notifyGraphMutated()
  }

  return {
    projectId,
    sessionId,
    sessions,
    messages,
    streamingReply,
    streamingWebSources,
    isStreaming,
    progressLabel,
    lastAgent,
    stagingBatches,
    error,
    init,
    loadSessions,
    switchSession,
    newSession,
    deleteSession,
    renameSession,
    send,
    setGraphMutatedHandler,
    refreshStaging,
    resolveBatch,
    resolveItem,
    editAppliedNode,
    removeAppliedNode,
  }
})
