import { Position } from '@vue-flow/core'
import type { CreativeFlowNode, CreativeNodeData, CreativeNodeType } from '../types/node'
import type { ProjectGroup, ProjectGroupId, ProjectItem } from '../types/workspace'

export interface NodeTypeOption {
  type: CreativeNodeType
  label: string
  icon: string
  description: string
}

/** 左侧节点工具栏展示的节点类型配置。 */
export const nodeTypeOptions: NodeTypeOption[] = [
  { type: 'idea', icon: '💡', label: '灵感节点', description: '记录脑洞、初始想法、待扩展灵感' },
  { type: 'character', icon: '👤', label: '角色节点', description: '记录角色设定、动机和关系' },
  { type: 'worldbuilding', icon: '🌍', label: '世界观节点', description: '记录世界规则、场景和组织' },
  { type: 'plot', icon: '🧩', label: '剧情节点', description: '记录事件、冲突、转折和结果' },
  { type: 'research', icon: '📚', label: '资料节点', description: '记录资料摘要、来源和参考' },
  { type: 'structure', icon: '🗂', label: '结构整理节点', description: '整理角色卡、关系图和剧情框架' },
]

/* 新增节点类型时需要同步补齐这里、Vue Flow 节点插槽和后端 DTO 类型。 */
const nodeDefaults: Record<
  CreativeNodeType,
  {
    idPrefix: string
    title: string
    content: string
    typeLabel: string
    icon: string
    tags: string[]
  }
> = {
  idea: {
    idPrefix: 'idea-draft',
    title: '未命名灵感',
    content: '在这里记录一个新的创作灵感……',
    typeLabel: '灵感',
    icon: '💡',
    tags: ['灵感'],
  },
  character: {
    idPrefix: 'char-draft',
    title: '未命名角色',
    content: '在这里记录角色动机、关系和背景……',
    typeLabel: '角色',
    icon: '👤',
    tags: ['角色'],
  },
  worldbuilding: {
    idPrefix: 'world-draft',
    title: '未命名世界观',
    content: '在这里记录世界规则、场景或组织设定……',
    typeLabel: '世界观',
    icon: '🌍',
    tags: ['世界观'],
  },
  plot: {
    idPrefix: 'plot-draft',
    title: '未命名剧情',
    content: '在这里记录事件、冲突、转折和结果……',
    typeLabel: '剧情',
    icon: '🧩',
    tags: ['剧情'],
  },
  research: {
    idPrefix: 'research-draft',
    title: '未命名资料',
    content: '在这里记录资料摘要或参考来源……',
    typeLabel: '资料',
    icon: '📚',
    tags: ['资料'],
  },
  structure: {
    idPrefix: 'structure-draft',
    title: '未命名结构',
    content: '在这里整理角色卡、关系图或剧情框架……',
    typeLabel: '结构整理',
    icon: '🗂',
    tags: ['结构'],
  },
}

/**
 * 读取节点类型配置。
 *
 * Args:
 *   type: 业务节点类型。
 *
 * Returns:
 *   匹配的工具栏配置；未知类型降级为第一个配置。
 */
export function getNodeTypeOption(type: CreativeNodeType): NodeTypeOption {
  return nodeTypeOptions.find((option) => option.type === type) ?? nodeTypeOptions[0]
}

/**
 * 创建节点业务数据默认值。
 *
 * Args:
 *   type: 业务节点类型。
 *
 * Returns:
 *   可写入 CreativeFlowNode.data 的默认数据。
 */
export function createNodeData(type: CreativeNodeType): CreativeNodeData {
  const defaults = nodeDefaults[type]

  return {
    title: defaults.title,
    content: defaults.content,
    nodeType: type,
    tags: [...defaults.tags],
    status: 'draft',
    icon: defaults.icon,
    typeLabel: defaults.typeLabel,
  }
}

/**
 * 创建新的画布节点。
 *
 * PoC 阶段点击节点工具栏会直接生成本地节点，不触发 Agent、RAG 或后端 LLM 调用。
 *
 * Args:
 *   type: 业务节点类型。
 *   index: 当前会话内的新增节点序号，用于降低 ID 冲突概率。
 *   position: 新节点在画布中的坐标。
 *
 * Returns:
 *   Vue Flow 可渲染的业务节点。
 */
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
    data: createNodeData(type),
  }
}

/**
 * 将 graph 节点转换为旧项目列表条目。
 *
 * 该兼容入口仍供 mock 和旧侧栏数据结构使用，内容来源已经迁移到新的 content/tags 字段。
 *
 * Args:
 *   node: 前端业务节点。
 *
 * Returns:
 *   旧项目列表使用的摘要条目。
 */
export function toProjectItem(node: CreativeFlowNode): ProjectItem {
  return {
    id: node.id,
    title: node.data.title,
    kind: node.data.typeLabel,
    summary: node.data.content,
    meta: node.data.tags.join(' / '),
  }
}

/**
 * 获取节点类型所属的左侧分组。
 *
 * Args:
 *   type: 业务节点类型。
 *
 * Returns:
 *   旧项目列表分组 ID。
 */
export function getProjectGroupIdForNodeType(type: CreativeNodeType): ProjectGroupId {
  const groupMap: Record<CreativeNodeType, ProjectGroupId> = {
    idea: 'ideas',
    character: 'characters',
    worldbuilding: 'worldbuilding',
    plot: 'plot',
    research: 'research',
    structure: 'structure',
  }

  return groupMap[type]
}

/**
 * 从当前 graph 节点构建左侧项目分组。
 *
 * Args:
 *   nodes: 当前画布节点列表。
 *
 * Returns:
 *   按业务类型分组后的项目条目。
 */
export function buildProjectGroupsFromNodes(nodes: CreativeFlowNode[]): ProjectGroup[] {
  const groups: ProjectGroup[] = [
    { id: 'ideas', title: '灵感', items: [] },
    { id: 'characters', title: '角色', items: [] },
    { id: 'worldbuilding', title: '世界观', items: [] },
    { id: 'plot', title: '剧情', items: [] },
    { id: 'research', title: '资料', items: [] },
    { id: 'structure', title: '结构整理', items: [] },
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
