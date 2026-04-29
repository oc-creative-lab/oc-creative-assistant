import { MarkerType, Position } from '@vue-flow/core'
import type { CreativeFlowEdge, CreativeFlowNode } from '../types/node'

// 早期前端独立演示用 graph；当前主要作为 mock sidebar/status 的数据来源。
export const mockGraphNodes: CreativeFlowNode[] = [
  {
    id: 'char-airin',
    type: 'character',
    position: { x: 40, y: 80 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: '\u827e\u7433',
      typeLabel: '\u89d2\u8272',
      summary: '\u5e74\u8f7b\u7684\u89c1\u4e60\u8bb0\u5f55\u5b98\uff0c\u5bf9\u738b\u90fd\u9690\u85cf\u7684\u9b54\u6cd5\u75d5\u8ff9\u5f02\u5e38\u654f\u611f\u3002',
      meta: '\u4e3b\u89d2 / \u89c6\u89d2\u8282\u70b9',
    },
  },
  {
    id: 'char-mentor',
    type: 'character',
    position: { x: 40, y: 290 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: '\u5bfc\u5e08',
      typeLabel: '\u89d2\u8272',
      summary: '\u66fe\u7ecf\u670d\u52a1\u4e8e\u738b\u5ba4\u6863\u6848\u9986\uff0c\u4fdd\u7559\u7740\u5173\u4e8e\u53e4\u8001\u5951\u7ea6\u7684\u79d8\u5bc6\u3002',
      meta: '\u5f15\u5bfc\u8005 / \u4fe1\u606f\u6e90',
    },
  },
  {
    id: 'world-capital',
    type: 'worldbuilding',
    position: { x: 360, y: 40 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: '\u738b\u90fd',
      typeLabel: '\u4e16\u754c\u89c2',
      summary: '\u5efa\u5728\u4e09\u5c42\u53e4\u57ce\u9057\u5740\u4e0a\u7684\u90fd\u57ce\uff0c\u5730\u4e0b\u4ecd\u6709\u672a\u6ce8\u9500\u7684\u65e7\u9b54\u6cd5\u9635\u3002',
      meta: '\u6838\u5fc3\u573a\u666f / \u57ce\u5e02',
    },
  },
  {
    id: 'world-magic-rule',
    type: 'worldbuilding',
    position: { x: 360, y: 250 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: '\u9b54\u6cd5\u89c4\u5219',
      typeLabel: '\u8bbe\u5b9a',
      summary: '\u6240\u6709\u672f\u5f0f\u90fd\u9700\u8981\u4ee5\u771f\u540d\u6216\u8bb0\u5fc6\u4f5c\u4e3a\u951a\u70b9\uff0c\u4ee3\u4ef7\u4f1a\u8ffd\u6eaf\u5230\u65bd\u672f\u8005\u3002',
      meta: '\u89c4\u5219 / \u7ea6\u675f',
    },
  },
  {
    id: 'plot-first-meet',
    type: 'plot',
    position: { x: 700, y: 120 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: '\u521d\u9047\u4e8b\u4ef6',
      typeLabel: '\u5267\u60c5',
      summary: '\u827e\u7433\u5728\u738b\u90fd\u96c6\u5e02\u8ffd\u67e5\u5931\u7a83\u6863\u6848\uff0c\u610f\u5916\u9047\u5230\u4f2a\u88c5\u8eab\u4efd\u7684\u5bfc\u5e08\u3002',
      meta: '\u7b2c\u4e00\u5e55 / \u5f00\u7aef',
    },
  },
  {
    id: 'plot-conflict-rise',
    type: 'plot',
    position: { x: 1020, y: 210 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: '\u51b2\u7a81\u5347\u7ea7',
      typeLabel: '\u5267\u60c5',
      summary: '\u9b54\u6cd5\u9635\u88ab\u610f\u5916\u542f\u52a8\uff0c\u738b\u90fd\u5730\u4e0b\u9057\u5740\u5f00\u59cb\u5f71\u54cd\u5730\u8868\u79e9\u5e8f\u3002',
      meta: '\u7b2c\u4e8c\u5e55 / \u538b\u529b',
    },
  },
]

export const mockGraphEdges: CreativeFlowEdge[] = [
  {
    id: 'edge-airin-first-meet',
    source: 'char-airin',
    target: 'plot-first-meet',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'edge-mentor-first-meet',
    source: 'char-mentor',
    target: 'plot-first-meet',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'edge-capital-first-meet',
    source: 'world-capital',
    target: 'plot-first-meet',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'edge-magic-conflict',
    source: 'world-magic-rule',
    target: 'plot-conflict-rise',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'edge-first-meet-conflict',
    source: 'plot-first-meet',
    target: 'plot-conflict-rise',
    type: 'smoothstep',
    animated: true,
    markerEnd: MarkerType.ArrowClosed,
  },
]
