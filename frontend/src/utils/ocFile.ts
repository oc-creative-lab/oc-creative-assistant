import type { GraphDto, GraphEdgeDto, GraphNodeDto, SaveGraphDto } from '../api/graphApi'

export type OcBoardKey = 'story' | 'characters' | 'world'

export interface OcBoard {
  nodes: GraphNodeDto[]
  edges: GraphEdgeDto[]
}

export interface OcProjectFile {
  format: 'oc-project'
  version: 2
  exportedAt: string
  project?: { id: string; name: string }
  boards: Record<OcBoardKey, OcBoard>
}

/** 把整个项目导出成 .oc 文件并触发下载。 */
export function downloadProjectOcFile(
  projectName: string,
  graphs: Record<OcBoardKey, GraphDto>,
): void {
  const toBoard = (g: GraphDto): OcBoard => ({ nodes: g.nodes, edges: g.edges })
  const payload: OcProjectFile = {
    format: 'oc-project',
    version: 2,
    exportedAt: new Date().toISOString(),
    project: { id: graphs.story.project.id, name: projectName },
    boards: {
      story: toBoard(graphs.story),
      characters: toBoard(graphs.characters),
      world: toBoard(graphs.world),
    },
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${(projectName || 'project').replace(/[^\w.-]+/g, '_')}.oc`
  anchor.click()
  URL.revokeObjectURL(url)
}

/** 单块画布 id 重映射，边端点随之改写，避免与库中既有节点主键冲突。 */
function remapBoard(board: OcBoard | undefined): SaveGraphDto {
  const freshId = () =>
    crypto.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  const idMap = new Map<string, string>()
  const nodes: GraphNodeDto[] = (board?.nodes ?? []).map((node) => {
    const id = freshId()
    idMap.set(node.id, id)
    return { ...node, id }
  })
  const edges: GraphEdgeDto[] = (board?.edges ?? [])
    .filter((edge) => idMap.has(edge.source) && idMap.has(edge.target))
    .map((edge) => ({
      ...edge,
      id: freshId(),
      source: idMap.get(edge.source) as string,
      target: idMap.get(edge.target) as string,
    }))
  return { nodes, edges }
}

export async function readProjectOcFile(file: File): Promise<Record<OcBoardKey, SaveGraphDto>> {
  const parsed = JSON.parse(await file.text()) as Partial<OcProjectFile>
  if (parsed.format !== 'oc-project' || !parsed.boards) {
    throw new Error('Not a valid .oc project file')
  }
  return {
    story: remapBoard(parsed.boards.story),
    characters: remapBoard(parsed.boards.characters),
    world: remapBoard(parsed.boards.world),
  }
}