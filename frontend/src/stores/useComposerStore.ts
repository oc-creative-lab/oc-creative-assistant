import { defineStore } from 'pinia'

export type WebSearchMode = 'auto' | 'on' | 'off'

/** A node quoted in the bottom dialog box (second_revision change C). */
export interface QuotedNodeRef {
  id: string
  type: string // 'character' | 'plot' | 'world' ...
  title: string
}

/**
 * Bottom Composer state: quoted node cards + input box text.
 *
 * Select a node → copy it to the dialog box → show it as a dismissible small card above the input box.
 */
export const useComposerStore = defineStore('composer', {
  state: () => ({
    references: [] as QuotedNodeRef[],
    input: '',
    collapsed: false,
    /** auto = heuristic; on = force web search; off = disable web search */
    webSearchMode: 'auto' as WebSearchMode,
  }),
  actions: {
    cycleWebSearchMode() {
      const order: WebSearchMode[] = ['auto', 'on', 'off']
      const index = order.indexOf(this.webSearchMode)
      this.webSearchMode = order[(index + 1) % order.length]
    },
    addReferences(refs: QuotedNodeRef[]) {
      const existing = new Set(this.references.map((r) => r.id))
      refs.forEach((r) => {
        if (!existing.has(r.id)) this.references.push(r)
      })
    },
    removeReference(id: string) {
      this.references = this.references.filter((r) => r.id !== id)
    },
    setCollapsed(value: boolean) {
      this.collapsed = value
    },
    clear() {
      this.references = []
      this.input = ''
    },
  },
})
