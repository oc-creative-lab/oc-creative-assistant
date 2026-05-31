import { defineStore } from 'pinia'

/** 底部对话框里引用的节点（second_revision 改点 C）。 */
export interface QuotedNodeRef {
  id: string
  type: string // 'character' | 'plot' | 'world' ...
  title: string
}

/**
 * 底部 Composer 状态：引用节点卡片 + 输入框文本。
 *
 * 选中节点 → 复制到对话框 → 以可叉掉的小卡片显示在输入框上方。
 */
export const useComposerStore = defineStore('composer', {
  state: () => ({
    references: [] as QuotedNodeRef[],
    input: '',
  }),
  actions: {
    addReferences(refs: QuotedNodeRef[]) {
      const existing = new Set(this.references.map((r) => r.id))
      refs.forEach((r) => {
        if (!existing.has(r.id)) this.references.push(r)
      })
    },
    removeReference(id: string) {
      this.references = this.references.filter((r) => r.id !== id)
    },
    clear() {
      this.references = []
      this.input = ''
    },
  },
})
