import { backendBaseUrl } from './http'

/** 工作台底部对话框 SSE 事件（second_revision 改点 B / W5）。 */
export type WorkspaceChatEvent =
  | { type: 'output'; output_type: 'search' | 'rag' | 'question' | 'feedback'; content: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

/**
 * 工作台被动灵感 agent 的 SSE 流。
 *
 * 与 chat 的 streamChat 同构：fetch + ReadableStream 解析；每条完整 data 行
 * 调一次 onEvent。被动响应——只在用户发消息时产出。
 */
export async function streamWorkspaceChat(
  projectId: string,
  message: string,
  quotedNodeIds: string[],
  onEvent: (event: WorkspaceChatEvent) => void,
): Promise<void> {
  const response = await fetch(`${backendBaseUrl}/api/projects/${projectId}/workspace_chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, quoted_node_ids: quotedNodeIds }),
  })

  if (!response.ok || !response.body) {
    throw new Error(`workspace_chat failed: HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''
    for (const raw of chunks) {
      const line = raw.trim()
      if (!line.startsWith('data: ')) continue
      try {
        onEvent(JSON.parse(line.slice(6)) as WorkspaceChatEvent)
      } catch {
        /* 跳过损坏 chunk */
      }
    }
  }
}
