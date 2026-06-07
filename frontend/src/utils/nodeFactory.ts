import { Position } from '@vue-flow/core'
import type { CreativeFlowNode, CreativeNodeData, CreativeNodeType } from '../types/node'
import type { ProjectGroup, ProjectGroupId, ProjectItem } from '../types/workspace'

export interface NodeTypeOption {
  type: CreativeNodeType
  label: string
  icon: string
  description: string
}

/** Node type configuration shown in the left-hand node toolbar. */
export const nodeTypeOptions: NodeTypeOption[] = [
  { type: 'idea', icon: '💡', label: 'Idea node', description: 'Capture brainstorms, initial ideas and inspiration to expand later' },
  { type: 'character', icon: '👤', label: 'Character node', description: 'Capture character profiles, motivations and relationships' },
  { type: 'worldbuilding', icon: '🌍', label: 'Worldbuilding node', description: 'Capture world rules, settings and organizations' },
  { type: 'plot', icon: '🧩', label: 'Plot node', description: 'Capture events, conflicts, turning points and outcomes' },
  { type: 'research', icon: '📚', label: 'Research node', description: 'Capture research summaries, sources and references' },
  { type: 'structure', icon: '🗂', label: 'Structure node', description: 'Organize character cards, relationship maps and plot frameworks' },
]

/* When adding a new node type, this place, the Vue Flow node slot and the backend DTO type all need to be filled in together. */
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
    title: 'Untitled Idea',
    content: 'Capture a new creative idea here...',
    typeLabel: 'Idea',
    icon: '💡',
    tags: ['Idea'],
  },
  character: {
    idPrefix: 'char-draft',
    title: 'Untitled Character',
    content: 'Capture the character\'s motivations, relationships and background here...',
    typeLabel: 'Character',
    icon: '👤',
    tags: ['Character'],
  },
  worldbuilding: {
    idPrefix: 'world-draft',
    title: 'Untitled Worldbuilding',
    content: 'Capture world rules, settings or organization details here...',
    typeLabel: 'Worldbuilding',
    icon: '🌍',
    tags: ['Worldbuilding'],
  },
  plot: {
    idPrefix: 'plot-draft',
    title: 'Untitled Plot',
    content: 'Capture events, conflicts, turning points and outcomes here...',
    typeLabel: 'Plot',
    icon: '🧩',
    tags: ['Plot'],
  },
  research: {
    idPrefix: 'research-draft',
    title: 'Untitled Research',
    content: 'Capture research summaries or reference sources here...',
    typeLabel: 'Research',
    icon: '📚',
    tags: ['Research'],
  },
  structure: {
    idPrefix: 'structure-draft',
    title: 'Untitled Structure',
    content: 'Organize character cards, relationship maps or plot frameworks here...',
    typeLabel: 'Structure',
    icon: '🗂',
    tags: ['Structure'],
  },
}

/**
 * Read the node type configuration.
 *
 * Args:
 *   type: The business node type.
 *
 * Returns:
 *   The matching toolbar configuration; unknown types fall back to the first configuration.
 */
export function getNodeTypeOption(type: CreativeNodeType): NodeTypeOption {
  return nodeTypeOptions.find((option) => option.type === type) ?? nodeTypeOptions[0]
}

/**
 * Create the default business data for a node.
 *
 * Args:
 *   type: The business node type.
 *
 * Returns:
 *   Default data that can be written into CreativeFlowNode.data.
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
 * Create a new canvas node.
 *
 * In the PoC stage, clicking the node toolbar generates a local node directly, without triggering an Agent, RAG or a backend LLM call.
 *
 * Args:
 *   type: The business node type.
 *   index: The sequence number of the newly added node within the current session, used to reduce the chance of ID collisions.
 *   position: The coordinates of the new node on the canvas.
 *
 * Returns:
 *   A business node that Vue Flow can render.
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
 * Convert a graph node into a legacy project list item.
 *
 * This compatibility entry point is still used by the mock and legacy sidebar data structures; the content source has already been migrated to the new content/tags fields.
 *
 * Args:
 *   node: The frontend business node.
 *
 * Returns:
 *   The summary item used by the legacy project list.
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
 * Get the left-hand group that a node type belongs to.
 *
 * Args:
 *   type: The business node type.
 *
 * Returns:
 *   The legacy project list group ID.
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
 * Build the left-hand project groups from the current graph nodes.
 *
 * Args:
 *   nodes: The current list of canvas nodes.
 *
 * Returns:
 *   Project items grouped by business type.
 */
export function buildProjectGroupsFromNodes(nodes: CreativeFlowNode[]): ProjectGroup[] {
  const groups: ProjectGroup[] = [
    { id: 'ideas', title: 'Idea', items: [] },
    { id: 'characters', title: 'Character', items: [] },
    { id: 'worldbuilding', title: 'Worldbuilding', items: [] },
    { id: 'plot', title: 'Plot', items: [] },
    { id: 'research', title: 'Research', items: [] },
    { id: 'structure', title: 'Structure', items: [] },
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
