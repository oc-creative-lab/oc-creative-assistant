import { mockGraphNodes } from './graph'
import type { AgentMode, AgentSuggestion, ProjectGroup, WorkspaceStatus } from '../types/workspace'
import type { CreativeNodeType } from '../types/node'

export const mockProjectName = '\u300a\u661f\u5ead\u6863\u6848\u300b'

// mock 数据仍用于右侧 Agent 和部分状态占位；真实 graph 已从后端加载。
const groupLabels: Record<CreativeNodeType, string> = {
  character: '\u89d2\u8272',
  worldbuilding: '\u4e16\u754c\u89c2',
  plot: '\u5267\u60c5',
}

export const mockProjectGroups: ProjectGroup[] = [
  {
    id: 'characters',
    title: groupLabels.character,
    items: mockGraphNodes
      .filter((node) => node.type === 'character')
      .map((node) => ({
        id: node.id,
        title: node.data.title,
        kind: node.data.typeLabel,
        summary: node.data.summary,
        meta: node.data.meta,
      })),
  },
  {
    id: 'worldbuilding',
    title: groupLabels.worldbuilding,
    items: mockGraphNodes
      .filter((node) => node.type === 'worldbuilding')
      .map((node) => ({
        id: node.id,
        title: node.data.title,
        kind: node.data.typeLabel,
        summary: node.data.summary,
        meta: node.data.meta,
      })),
  },
  {
    id: 'plot',
    title: groupLabels.plot,
    items: mockGraphNodes
      .filter((node) => node.type === 'plot')
      .map((node) => ({
        id: node.id,
        title: node.data.title,
        kind: node.data.typeLabel,
        summary: node.data.summary,
        meta: node.data.meta,
      })),
  },
  {
    id: 'materials',
    title: '\u8d44\u6599',
    items: [
      {
        id: 'mat-royal-archive',
        title: '\u738b\u5ba4\u6863\u6848\u6458\u8981',
        kind: '\u8d44\u6599',
        summary: '\u5173\u4e8e\u738b\u90fd\u65e7\u5951\u7ea6\u548c\u5730\u4e0b\u9057\u5740\u7684\u7814\u7a76\u6458\u8981\u3002',
        meta: '\u53c2\u8003 / \u6863\u6848',
      },
    ],
  },
]

export const mockAgentSuggestions: Record<AgentMode, AgentSuggestion[]> = {
  inspiration: [
    {
      id: 'idea-cost',
      title: '\u7ed9\u80fd\u529b\u589e\u52a0\u4ee3\u4ef7',
      body: '\u5f53\u524d\u8282\u70b9\u53ef\u4ee5\u8ffd\u95ee\u4e00\u4e2a\u4ee3\u4ef7\uff1a\u8bb0\u5fc6\u951a\u70b9\u88ab\u6539\u5199\u540e\uff0c\u89d2\u8272\u4f1a\u5931\u53bb\u4ec0\u4e48\uff1f',
    },
    {
      id: 'idea-visual',
      title: '\u5f3a\u5316\u89c6\u89c9\u951a\u70b9',
      body: '\u53ef\u4ee5\u628a\u672f\u5f0f\u75d5\u8ff9\u7edf\u4e00\u6210\u661f\u7802\u3001\u94f6\u7ebf\u548c\u5012\u8f6c\u7684\u949f\u9762\u7b26\u53f7\u3002',
    },
    {
      id: 'idea-choice',
      title: '\u5236\u9020\u9009\u62e9\u538b\u529b',
      body: '\u8ba9\u827e\u7433\u5728\u4fdd\u62a4\u5bfc\u5e08\u548c\u66dd\u5149\u738b\u90fd\u79d8\u5bc6\u4e4b\u95f4\u505a\u51fa\u53d6\u820d\u3002',
    },
  ],
  research: [
    {
      id: 'research-archive',
      title: '\u8865\u9f50\u6863\u6848\u6765\u6e90',
      body: '\u53ef\u4ee5\u4e3a\u738b\u5ba4\u6863\u6848\u9986\u8865\u4e00\u5c42\u516c\u5f00\u804c\u8d23\u3001\u9690\u79d8\u804c\u8d23\u548c\u5185\u90e8\u89c4\u5219\u3002',
    },
    {
      id: 'research-city',
      title: '\u67e5\u8be2\u7a7a\u95f4\u7ebf\u7d22',
      body: '\u5f53\u524d\u8bbe\u5b9a\u9002\u5408\u8ffd\u52a0\u4e00\u4efd\u738b\u90fd\u533a\u57df\u6e05\u5355\uff0c\u4fbf\u4e8e\u540e\u7eed\u753b\u5e03\u7f16\u6392\u3002',
    },
  ],
  structure: [
    {
      id: 'structure-act-one',
      title: '\u6574\u7406\u7b2c\u4e00\u5e55\u94fe\u8def',
      body: '\u5efa\u8bae\u5c06\u5931\u7a83\u6863\u6848\u3001\u521d\u9047\u4e8b\u4ef6\u3001\u5bfc\u5e08\u8bd5\u63a2\u3001\u738b\u90fd\u5f02\u53d8\u4e32\u6210\u8fde\u7eed\u8282\u70b9\u3002',
    },
    {
      id: 'structure-relation',
      title: '\u5efa\u7acb\u89d2\u8272\u5173\u7cfb',
      body: '\u827e\u7433\u4e0e\u5bfc\u5e08\u7684\u5173\u7cfb\u53ef\u4ee5\u5148\u4ece\u4e92\u76f8\u8bd5\u63a2\uff0c\u9010\u6b65\u8f6c\u4e3a\u5171\u4eab\u98ce\u9669\u3002',
    },
  ],
}

export const mockWorkspaceStatus: WorkspaceStatus = {
  saveState: '\u672c\u5730\u8349\u7a3f\u5df2\u4fdd\u5b58',
  indexState: '\u8d44\u6599\u7d22\u5f15\u5f85\u6784\u5efa',
  modelState: '\u6a21\u578b\uff1a\u672c\u5730\u5360\u4f4d',
}
