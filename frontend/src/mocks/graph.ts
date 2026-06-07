import { MarkerType, Position } from '@vue-flow/core'
import type { CreativeFlowEdge, CreativeFlowNode } from '../types/node'
import { createNodeData } from '../utils/nodeFactory'

/**
 * Jujutsu Kaisen Shibuya-station-line style mock nodes (aligned with the backend default sample in `app/services/graph_seed.py`).
 *
 * Premise: a subway station polluted by cursed energy. After the last train each night, the station announcements begin calling out station names that do not exist.
 */
export const mockGraphNodes: CreativeFlowNode[] = [
  {
    id: 'char-yuji-ticket',
    type: 'character',
    position: { x: 33.47138068598984, y: -17.515147652182712 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: 'Yuji the Ticket Inspector',
      content:
        'Checks tickets by day and stuffs fare-dodging curses back into the turnstiles by night. Having once swallowed a special-grade ticket, he occasionally hears a train calling out stations from inside his stomach.',
      typeLabel: 'Character',
      tags: ['Character', 'Ticket Inspector', 'Protagonist'],
      status: 'synced',
    },
  },
  {
    id: 'char-gojo-stationmaster',
    type: 'character',
    position: { x: -64.45790902416242, y: 352.6430965700507 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: 'Stationmaster Gojo',
      content: 'A mysterious blindfolded stationmaster who can make every passenger forever fall one centimeter short of tapping their card. He calls it "Infinite Waiting".',
      typeLabel: 'Character',
      tags: ['Character', 'Stationmaster', 'The Strongest'],
      status: 'synced',
    },
  },
  {
    id: 'char-nobara-lostfound',
    type: 'character',
    position: { x: 159.99062826248527, y: 629.992971196864 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('character'),
      title: 'Nobara the Lost-and-Found Clerk',
      content: 'Runs the lost-and-found office and is skilled at using nails to pin passengers\' lost grudges back onto their original owners.',
      typeLabel: 'Character',
      tags: ['Character', 'Lost and Found', 'Cursed Tool'],
      status: 'synced',
    },
  },
  {
    id: 'world-cursed-station',
    type: 'worldbuilding',
    position: { x: 399.58585794203043, y: -131.52726577392886 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: 'Shibuya Underground Platform Zero',
      content: 'A subway platform that does not exist on any map, opening only after the last train. The station signs rename themselves to whatever place each passenger fears most.',
      typeLabel: 'Worldbuilding',
      tags: ['Worldbuilding', 'Station', 'Cursed Space'],
      status: 'synced',
    },
  },
  {
    id: 'world-ticket-curse',
    type: 'worldbuilding',
    position: { x: 194.58721148211174, y: 196.8478148386396 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: 'Special-Grade Cursed Object: The Half-Price Monthly Pass',
      content: 'Legend says that with this monthly pass you can ride forever. The price is that you can never exit the station, doomed to loop endlessly through the transfer corridors.',
      typeLabel: 'Worldbuilding',
      tags: ['Worldbuilding', 'Cursed Object', 'Monthly Pass'],
      status: 'synced',
    },
  },
  {
    id: 'world-announcement',
    type: 'worldbuilding',
    position: { x: 777.9052605024667, y: -220.62055743461664 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('worldbuilding'),
      title: 'The Midnight Announcement System',
      content:
        'After 00:00 each day, the announcements call out stations in the voices of passengers\' loved ones. Anyone who hears their own name is sent to the "Final Stop" at the next station.',
      typeLabel: 'Worldbuilding',
      tags: ['Worldbuilding', 'Announcement', 'Urban Legend'],
      status: 'synced',
    },
  },
  {
    id: 'plot-last-train',
    type: 'plot',
    position: { x: 758.694276137198, y: 39.04512050627413 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: 'Last Train Strays onto Platform Zero',
      content: 'Yuji the ticket inspector finds a last train that is not on any timetable pulling in, its cars full of passengers who cast no shadows.',
      typeLabel: 'Plot',
      tags: ['Plot', 'Act One', 'Last Train'],
      status: 'synced',
    },
  },
  {
    id: 'plot-ticket-awakening',
    type: 'plot',
    position: { x: 760, y: 340 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: 'The Half-Price Monthly Pass Awakens',
      content: 'The special-grade cursed object, the half-price monthly pass, awakens inside the turnstiles and demands that all passengers settle their fares; those who cannot are folded into the subway route map.',
      typeLabel: 'Plot',
      tags: ['Plot', 'Conflict', 'Cursed Object Awakening'],
      status: 'synced',
    },
  },
  {
    id: 'plot-final-transfer',
    type: 'plot',
    position: { x: 760, y: 560 },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    data: {
      ...createNodeData('plot'),
      title: 'The Final Stop Transfer Ritual',
      content: 'Stationmaster Gojo decides to lock down Platform Zero, while Nobara finds an old station seal belonging to the "Final Stop" in the lost-and-found office.',
      typeLabel: 'Plot',
      tags: ['Plot', 'Climax', 'Sealing'],
      status: 'synced',
    },
  },
]

/** Jujutsu Kaisen Shibuya-station-line style mock edges (consistent with the backend `graph_seed.py`). */
export const mockGraphEdges: CreativeFlowEdge[] = [
  {
    id: 'edge-yuji-last-train',
    source: 'char-yuji-ticket',
    target: 'plot-last-train',
    label: 'discovers anomaly',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'discovers anomaly',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-gojo-final-transfer',
    source: 'char-gojo-stationmaster',
    target: 'plot-final-transfer',
    label: 'enforces lockdown',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'enforces lockdown',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-nobara-final-transfer',
    source: 'char-nobara-lostfound',
    target: 'plot-final-transfer',
    label: 'provides station seal',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'provides station seal',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-station-last-train',
    source: 'world-cursed-station',
    target: 'plot-last-train',
    label: 'takes place at',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'takes place at',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-ticket-awakening',
    source: 'world-ticket-curse',
    target: 'plot-ticket-awakening',
    label: 'core cursed object',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'core cursed object',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-last-train-ticket',
    source: 'plot-last-train',
    target: 'plot-ticket-awakening',
    label: 'leads to',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'leads to',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-ticket-final',
    source: 'plot-ticket-awakening',
    target: 'plot-final-transfer',
    label: 'escalates into',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'escalates into',
      relationType: 'belongs_to',
    },
  },
  {
    id: 'edge-world-announcement-plot-last-train-1777562934373-2',
    source: 'world-announcement',
    target: 'plot-last-train',
    label: 'triggers legend',
    type: 'smoothstep',
    markerEnd: MarkerType.ArrowClosed,
    data: {
      label: 'triggers legend',
      relationType: 'relates_to',
    },
  },
]
