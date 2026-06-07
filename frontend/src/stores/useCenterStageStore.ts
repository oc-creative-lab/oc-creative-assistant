import { defineStore } from 'pinia'

/** The node's initial snapshot carried when entering the detail page (avoids the detail page issuing another GET). */
export interface DetailNodeSnapshot {
  id: string
  title: string
  content: string
  nodeType: string
  typeLabel: string
  icon: string
  tags: string[]
  status: string
}

/**
 * Center-panel stage state (second_revision change A).
 *
 * Controls switching the center panel between "canvas" and "node detail": double-click a node → detail; back → canvas.
 * The detail page occupies the canvas position; the left and right panels stay unchanged.
 */
export const useCenterStageStore = defineStore('centerStage', {
  state: () => ({
    mode: 'canvas' as 'canvas' | 'detail',
    detailNodeId: null as string | null,
    detailNode: null as DetailNodeSnapshot | null,
  }),
  actions: {
    openDetail(nodeId: string, node?: DetailNodeSnapshot) {
      this.mode = 'detail'
      this.detailNodeId = nodeId
      this.detailNode = node ?? null
    },
    returnToCanvas() {
      this.mode = 'canvas'
      this.detailNodeId = null
      this.detailNode = null
    },
  },
})
