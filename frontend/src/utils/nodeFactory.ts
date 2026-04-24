import { Position } from '@vue-flow/core'
import type { CreativeFlowNode, CreativeNodeType } from '../types/node'
import type { ProjectGroup, ProjectGroupId, ProjectItem } from '../types/workspace'

export const nodeTypeOptions: Array<{ type: CreativeNodeType; label: string }> = [
  { type: 'character', label: '\u89d2\u8272\u8282\u70b9' },
  { type: 'worldbuilding', label: '\u4e16\u754c\u89c2\u8282\u70b9' },
  { type: 'plot', label: '\u5267\u60c5\u8282\u70b9' },
]

const nodeDefaults: Record<
  CreativeNodeType,
  {
    idPrefix: string
    title: string
    typeLabel: string
    summary: string
    meta: string
  }
> = {
  character: {
    idPrefix: 'char-draft',
    title: '\u65b0\u89d2\u8272',
    typeLabel: '\u89d2\u8272',
    summary: '\u8fd9\u662f\u4e00\u4e2a\u65b0\u7684\u89d2\u8272\u8282\u70b9\uff0c\u53ef\u540e\u7eed\u8865\u5145\u52a8\u673a\u3001\u5173\u7cfb\u548c\u80cc\u666f\u3002',
    meta: '\u8349\u7a3f / \u89d2\u8272',
  },
  worldbuilding: {
    idPrefix: 'world-draft',
    title: '\u65b0\u4e16\u754c\u89c2\u8bbe\u5b9a',
    typeLabel: '\u4e16\u754c\u89c2',
    summary: '\u8fd9\u662f\u4e00\u4e2a\u65b0\u7684\u4e16\u754c\u89c2\u8282\u70b9\uff0c\u53ef\u7528\u6765\u8bb0\u5f55\u573a\u666f\u3001\u89c4\u5219\u6216\u7ec4\u7ec7\u3002',
    meta: '\u8349\u7a3f / \u8bbe\u5b9a',
  },
  plot: {
    idPrefix: 'plot-draft',
    title: '\u65b0\u5267\u60c5\u8282\u70b9',
    typeLabel: '\u5267\u60c5',
    summary: '\u8fd9\u662f\u4e00\u4e2a\u65b0\u7684\u5267\u60c5\u8282\u70b9\uff0c\u53ef\u540e\u7eed\u8865\u5145\u51b2\u7a81\u3001\u8f6c\u6298\u548c\u7ed3\u679c\u3002',
    meta: '\u8349\u7a3f / \u5267\u60c5',
  },
}

// 根据节点类型创建带默认内容的画布节点，后续接后端时可以把这里替换为真实创建 DTO。
export function createCreativeNode(
  type: CreativeNodeType,
  index: number,
  position: { x: number; y: number },
): CreativeFlowNode {
  const defaults = nodeDefaults[type]

  return {
    id: `${defaults.idPrefix}-${Date.now()}-${index}`,
    type,
    position,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      title: `${defaults.title} ${index}`,
      typeLabel: defaults.typeLabel,
      summary: defaults.summary,
      meta: defaults.meta,
    },
  }
}

// 将画布节点映射为左侧项目面板条目，保持 sidebar 与画布使用同一份节点语义。
export function toProjectItem(node: CreativeFlowNode): ProjectItem {
  return {
    id: node.id,
    title: node.data.title,
    kind: node.data.typeLabel,
    summary: node.data.summary,
    meta: node.data.meta,
  }
}

// 目前三类可编辑节点分别落入左侧对应分组，资料分组暂不参与画布创建。
export function getProjectGroupIdForNodeType(type: CreativeNodeType): ProjectGroupId {
  const groupMap: Record<CreativeNodeType, ProjectGroupId> = {
    character: 'characters',
    worldbuilding: 'worldbuilding',
    plot: 'plot',
  }

  return groupMap[type]
}

// 根据当前 graph nodes 重新生成左侧项目分组，让加载、创建、保存后的数据都保持一致。
export function buildProjectGroupsFromNodes(nodes: CreativeFlowNode[]): ProjectGroup[] {
  const groups: ProjectGroup[] = [
    { id: 'characters', title: '\u89d2\u8272', items: [] },
    { id: 'worldbuilding', title: '\u4e16\u754c\u89c2', items: [] },
    { id: 'plot', title: '\u5267\u60c5', items: [] },
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

  for (const node of nodes) {
    const groupId = getProjectGroupIdForNodeType(node.type)
    const group = groups.find((item) => item.id === groupId)

    if (group) {
      group.items.push(toProjectItem(node))
    }
  }

  return groups
}
