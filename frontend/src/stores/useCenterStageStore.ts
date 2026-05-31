import { defineStore } from 'pinia'

/** 进入详情页时携带的节点初始快照（避免详情页再发一次 GET）。 */
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
 * 中栏舞台状态（second_revision 改点 A）。
 *
 * 控制中栏在"画布"与"节点详情"之间切换：双击节点 → detail；返回 → canvas。
 * 详情页占据画布位置，左右栏不变。
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
