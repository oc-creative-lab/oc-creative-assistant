import { defineStore } from 'pinia'

/** Cross-page "jump to node" intent: a chip in chat sets it, the target board consumes it after load. */
export const useNodeNavStore = defineStore('nodeNav', {
  state: () => ({ pendingNodeId: '' }),
  actions: {
    request(nodeId: string) {
      this.pendingNodeId = nodeId
    },
    consume(): string {
      const id = this.pendingNodeId
      this.pendingNodeId = ''
      return id
    },
  },
})