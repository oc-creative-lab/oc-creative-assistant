import { backendBaseUrl } from './http'

/** SSE events for the workspace bottom dialog box (second_revision change B / W5). */
export type WorkspaceChatEvent =
  | { type: 'output'; output_type: 'search' | 'rag' | 'question' | 'feedback'; content: string }
  | { type: 'error'; message: string }
  | { type: 'done' }

/**
 * SSE stream of the workspace's passive inspiration agent.
 *
 * Isomorphic to chat's streamChat: fetch + ReadableStream parsing; onEvent is called
 * once per complete data line. Passive response—only produces output when the user sends a message.
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
        /* skip the corrupted chunk */
      }
    }
  }
}
