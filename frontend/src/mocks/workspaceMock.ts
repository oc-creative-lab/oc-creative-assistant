import { mockGraphNodes } from './graph'
import type { AgentMode, AgentSuggestion, ProjectGroup, WorkspaceStatus } from '../types/workspace'
import { buildProjectGroupsFromNodes } from '../utils/nodeFactory'

/** PoC default project name, aligned with the backend default project name; used for standalone frontend demos and the legacy entry view. */
export const mockProjectName = 'Hogwarts: The Final Siege'

/** Legacy left-sidebar group data; the real graph now loads from the backend. */
export const mockProjectGroups: ProjectGroup[] = buildProjectGroupsFromNodes(mockGraphNodes)

/** Placeholder agent suggestions for UI states not yet wired to a real LLM. */
export const mockAgentSuggestions: Record<AgentMode, AgentSuggestion[]> = {
  inspiration: [
    {
      id: 'idea-memory-cost',
      title: 'Sharpen the memory cost',
      body: 'You could make the Memory Offering tempting but morally dangerous: the castle survives only if the defenders refuse to let one student carry the whole cost alone.',
    },
    {
      id: 'idea-shield-visual',
      title: 'Make the shield visible',
      body: 'The Ancient Shield could show the defenders\' emotional state: silver cracks when distrust spreads, warmer light when former enemies choose the same people to protect.',
    },
    {
      id: 'idea-draco-vow',
      title: 'Turn Draco\'s vow into a hinge',
      body: 'Let Draco\'s spoken vow decide both the Astronomy Passage and the Ancient Shield, so trust becomes a battlefield action rather than only a theme.',
    },
  ],
  research: [
    {
      id: 'research-siege-lines',
      title: 'Clarify the siege layers',
      body: 'Separate the outer Siege Lines, middle defense, and Great Hall Inner Defense so each plot decision has a clear tactical consequence.',
    },
    {
      id: 'research-passage-rules',
      title: 'Define the passage rules',
      body: 'The Astronomy Passage can have strict rules around vows, tracking curses, and who counts as protected, giving Hermione and Draco concrete constraints to solve.',
    },
  ],
  structure: [
    {
      id: 'structure-siege-chain',
      title: 'Organize the siege chain',
      body: 'A clean plot chain could run from the first assault, to the shield cracking, to Draco\'s warning, to the passage vow, then to Voldemort exploiting renewed distrust.',
    },
    {
      id: 'structure-character-pressure',
      title: 'Build the trust web',
      body: 'Harry, Hermione, Draco, McGonagall, Snape, and Voldemort can each pressure the same core question: whether the defenders can trust under direct attack.',
    },
  ],
}

/** Workspace status placeholder; the save state is overridden by the real backend state in AppShell. */
export const mockWorkspaceStatus: WorkspaceStatus = {
  saveState: 'Hogwarts siege draft saved',
  indexState: 'Shield and passage memory index pending build',
  modelState: 'Model: local story placeholder',
}
