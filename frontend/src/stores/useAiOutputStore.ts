import { defineStore } from 'pinia'

/** 工作台右栏的一条 AI 输出卡片（second_revision 改点 B）。 */
export interface AiOutput {
  id: string
  type: 'search' | 'rag' | 'question' | 'feedback'
  content: string
  timestamp: number
  collapsed: boolean
  metadata?: Record<string, unknown>
}

/**
 * 右栏 AI 输出流：时间线倒序卡片（最新在最上）。
 *
 * 工作台 agent 被动响应，产出按 type 分发成不同卡片 push 进来（W5 接 SSE）。
 */
export const useAiOutputStore = defineStore('aiOutput', {
  state: () => ({
    outputs: [] as AiOutput[],
  }),
  actions: {
    push(output: Omit<AiOutput, 'id' | 'timestamp' | 'collapsed'>) {
      this.outputs.unshift({
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
