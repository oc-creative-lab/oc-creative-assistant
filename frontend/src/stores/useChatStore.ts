import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  AgentStagingBatchDto,
  AppliedEntityDto,
  ChatMessageDto,
  WebSearchMode,
  WebSourceDto,
} from '../api/chatApi'
import {
  createChatSession,
  listProjectSessions,
  listProjectStaging,
  listSessionMessages,
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

  /** Enter a project: reuse the most recent session or create one, load history and pending staging. */
  async function init(targetProjectId: string): Promise<void> {
    if (projectId.value === targetProjectId && sessionId.value) return
    projectId.value = targetProjectId
    error.value = ''
    try {
      const sessions = await listProjectSessions(targetProjectId)
      const session = sessions[0] ?? (await createChatSession(targetProjectId, 'Chat writing'))
      sessionId.value = session.id
      messages.value = (await listSessionMessages(session.id)).map(_toMessage)
      await refreshStaging()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to start chat'
    }
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

    messages.value.push({ id: `local-${Date.now()}`, role: 'user', content })
    streamingReply.value = ''
    streamingWebSources.value = []
    progressLabel.value = 'Thinking…'
    isStreaming.value = true
    error.value = ''
    const appliedThisTurn: AppliedEntityDto[] = []

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
          } else if (event.type === 'extraction_applied') {
            appliedThisTurn.push(...event.items)
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
        })
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Reply failed'
    } finally {
      streamingReply.value = ''
      streamingWebSources.value = []
      progressLabel.value = ''
      isStreaming.value = false
      if (appliedThisTurn.length) {
        await notifyGraphMutated()
      }
      // background extraction finishes after persistence, so refresh the pending list shortly after.
      await refreshStaging()
    }
  }

  /** Accept/reject a whole staging batch, then refresh. */
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
    messages,
    streamingReply,
    streamingWebSources,
    isStreaming,
    progressLabel,
    lastAgent,
    stagingBatches,
    error,
    init,
    send,
    setGraphMutatedHandler,
    refreshStaging,
    resolveBatch,
    resolveItem,
    editAppliedNode,
    removeAppliedNode,
  }
})
