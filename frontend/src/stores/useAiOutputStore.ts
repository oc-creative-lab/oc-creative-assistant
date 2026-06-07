import { defineStore } from 'pinia'

/** A single AI output card in the workspace right panel (second_revision change B). */
export interface AiOutput {
  id: string
  type: 'search' | 'rag' | 'question' | 'feedback'
  content: string
  timestamp: number
  collapsed: boolean
  metadata?: Record<string, unknown>
}

/**
 * Right-panel AI output stream: timeline cards in chronological order (oldest on top).
 *
 * The workspace agent responds passively; its output is dispatched by type into different cards and appended (W5 wires up SSE).
 */
export const useAiOutputStore = defineStore('aiOutput', {
  state: () => ({
    outputs: [] as AiOutput[],
  }),
  actions: {
    push(output: Omit<AiOutput, 'id' | 'timestamp' | 'collapsed'>) {
      this.outputs.push({
        ...output,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        collapsed: false,
      })
    },
    toggleCollapse(id: string) {
      const o = this.outputs.find((x) => x.id === id)
      if (o) o.collapsed = !o.collapsed
    },
    clear() {
      this.outputs = []
    },
  },
})
