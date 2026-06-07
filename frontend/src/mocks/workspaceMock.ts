import { mockGraphNodes } from './graph'
import type { AgentMode, AgentSuggestion, ProjectGroup, WorkspaceStatus } from '../types/workspace'
import { buildProjectGroupsFromNodes } from '../utils/nodeFactory'

/** PoC default project name, aligned with the backend default project name; used for standalone frontend demos and the legacy entry view. */
export const mockProjectName = 'Jujutsu Kaisen — Shibuya Station Line'

/** Legacy left-sidebar group data; the real graph now loads from the backend. */
export const mockProjectGroups: ProjectGroup[] = buildProjectGroupsFromNodes(mockGraphNodes)

/** Placeholder agent suggestions for UI states not yet wired to a real LLM. */
export const mockAgentSuggestions: Record<AgentMode, AgentSuggestion[]> = {
  inspiration: [
    {
      id: 'idea-ticket-cost',
      title: 'Add a price to the half-fare monthly pass',
      body: 'You could introduce a strange price: half-fare pass holders can ride endlessly, but every time they transfer, they forget the name of one real station.',
    },
    {
      id: 'idea-station-visual',
      title: 'Strengthen the station-horror visuals',
      body: 'You could unify the cursed-energy traces into moldy station signs, electronic boards scrolling in reverse, transfer corridors with no exit numbers, and turnstile lamps that bleed on their own.',
    },
    {
      id: 'idea-announcement-choice',
      title: 'Create pressure through the announcement choice',
      body: 'Make Itadori the ticket inspector choose between cutting off the midnight announcement and saving a named passenger: once the announcement stops, Platform Zero permanently moves one level deeper.',
    },
  ],
  research: [
    {
      id: 'research-zero-platform',
      title: 'Flesh out the Platform Zero rules',
      body: 'You could give underground Shibuya Platform Zero three layers of rules: what ordinary passengers can see, what sorcerers can see, and what people swallowed by the station become.',
    },
    {
      id: 'research-cursed-facilities',
      title: 'Organize the in-station cursed facilities',
      body: 'The current setting is ready for an added list of station facilities — e.g. turnstiles, ticket machines, lost-and-found, transfer elevators, and arrival boards, each hosting a different type of cursed spirit.',
    },
  ],
  structure: [
    {
      id: 'structure-last-train-chain',
      title: 'Organize the last-train chain',
      body: 'Recommend stringing the anomalous last train, Platform Zero manifesting, the half-fare pass awakening, the midnight announcement roll call, and the terminus transfer ritual into a continuous chain of plot nodes.',
    },
    {
      id: 'structure-character-relation',
      title: 'Build the station-staff relationship web',
      body: 'The relationships among Itadori the ticket inspector, Gojo the stationmaster, and Nobara the lost-and-found clerk can start from "station coworkers" and gradually become a makeshift sorcerer squad fighting Platform Zero together.',
    },
  ],
}

/** Workspace status placeholder; the save state is overridden by the real backend state in AppShell. */
export const mockWorkspaceStatus: WorkspaceStatus = {
  saveState: 'Platform Zero draft saved',
  indexState: 'Cursed-object reference index pending build',
  modelState: 'Model: local cursed-energy placeholder',
}
