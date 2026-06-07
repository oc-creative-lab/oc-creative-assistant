"""Graph default data definitions.

This module belongs to the service layer's initialization configuration and is
responsible for providing the default project and the example graph shown on the
first screen.
It does not access the database, nor does it handle HTTP requests or vector index
synchronization.

The default example is aligned with the Shibuya Station storyline defined in the
frontend `frontend/src/mocks/graph.ts`, so that running without a backend mock
stays consistent with the SQLite seed data on the first screen.
"""

from app.schemas import EdgePayload, NodePayload, PositionPayload

DEFAULT_PROJECT_ID = 'default-project'
DEFAULT_PROJECT_NAME = 'Jujutsu Kaisen: The Shibuya Station Line'

DEFAULT_NODES = [
    NodePayload(
        id='char-yuji-ticket',
        type='character',
        title='Yuji the Ticket Inspector',
        content='By day he checks tickets; by night he shoves fare-dodging curses back through the turnstiles. Because he once swallowed a special-grade train ticket, he occasionally hears trains announcing stops from inside his stomach.',
        meta='Character / Ticket Inspector / Protagonist',
        typeLabel='Character',
        tags=['Character', 'Ticket Inspector', 'Protagonist'],
        status='synced',
        position=PositionPayload(x=33.47138068598984, y=-17.515147652182712),
    ),
    NodePayload(
        id='char-gojo-stationmaster',
        type='character',
        title='Gojo the Stationmaster',
        content='A mysterious blindfolded stationmaster who can make every passenger fall one centimeter short of tapping their card forever. He calls this "Infinite Waiting."',
        meta='Character / Stationmaster / The Strongest',
        typeLabel='Character',
        tags=['Character', 'Stationmaster', 'The Strongest'],
        status='synced',
        position=PositionPayload(x=-64.45790902416242, y=352.6430965700507),
    ),
    NodePayload(
        id='char-nobara-lostfound',
        type='character',
        title='Nobara of Lost & Found',
        content='In charge of the lost-and-found office, she specializes in using nails to pin passengers\' lost grudges back onto their original owners.',
        meta='Character / Lost & Found / Cursed Tool',
        typeLabel='Character',
        tags=['Character', 'Lost & Found', 'Cursed Tool'],
        status='synced',
        position=PositionPayload(x=159.99062826248527, y=629.992971196864),
    ),
    NodePayload(
        id='world-cursed-station',
        type='worldbuilding',
        title='Shibuya Underground Platform Zero',
        content='A subway platform that exists on no map, open only after the last train. Its station sign automatically renames itself to whatever place each passenger fears the most.',
        meta='Worldbuilding / Station / Cursed Space',
        typeLabel='Worldbuilding',
        tags=['Worldbuilding', 'Station', 'Cursed Space'],
        status='synced',
        position=PositionPayload(x=399.58585794203043, y=-131.52726577392886),
    ),
    NodePayload(
        id='world-ticket-curse',
        type='worldbuilding',
        title='Special-Grade Cursed Object: The Half-Price Pass',
        content='Legend says that using this pass grants unlimited rides. But the price is that you can never exit the station, doomed to cycle through the transfer corridors forever.',
        meta='Worldbuilding / Cursed Object / Pass',
        typeLabel='Worldbuilding',
        tags=['Worldbuilding', 'Cursed Object', 'Pass'],
        status='synced',
        position=PositionPayload(x=194.58721148211174, y=196.8478148386396),
    ),
    NodePayload(
        id='world-announcement',
        type='worldbuilding',
        title='Midnight Broadcast System',
        content='Every day after 00:00, the announcements call out the stops in the voices of passengers\' loved ones. Anyone who hears their own name is carried off to the "Terminus" at the next stop.',
        meta='Worldbuilding / Broadcast / Urban Legend',
        typeLabel='Worldbuilding',
        tags=['Worldbuilding', 'Broadcast', 'Urban Legend'],
        status='synced',
        position=PositionPayload(x=777.9052605024667, y=-220.62055743461664),
    ),
    NodePayload(
        id='plot-last-train',
        type='plot',
        title='Last Train into Platform Zero',
        content='Yuji the Ticket Inspector discovers a last train pulling in that is not on any schedule, its cars packed with passengers who cast no shadows.',
        meta='Plot / Act One / Last Train',
        typeLabel='Plot',
        tags=['Plot', 'Act One', 'Last Train'],
        status='synced',
        position=PositionPayload(x=758.694276137198, y=39.04512050627413),
    ),
    NodePayload(
        id='plot-ticket-awakening',
        type='plot',
        title='Awakening of the Half-Price Pass',
        content='The special-grade cursed object, the Half-Price Pass, awakens inside the turnstile and demands that every passenger pay the fare difference; those who cannot are folded into the subway route map.',
        meta='Plot / Conflict / Cursed Object Awakening',
        typeLabel='Plot',
        tags=['Plot', 'Conflict', 'Cursed Object Awakening'],
        status='synced',
        position=PositionPayload(x=760.0, y=340.0),
    ),
    NodePayload(
        id='plot-final-transfer',
        type='plot',
        title='The Terminus Transfer Ritual',
        content='Gojo the Stationmaster decides to lock down Platform Zero, while Nobara finds an old station seal belonging to the "Terminus" in the lost-and-found office.',
        meta='Plot / Climax / Sealing',
        typeLabel='Plot',
        tags=['Plot', 'Climax', 'Sealing'],
        status='synced',
        position=PositionPayload(x=760.0, y=560.0),
    ),
]

DEFAULT_EDGES = [
    EdgePayload(
        id='edge-yuji-last-train',
        source='char-yuji-ticket',
        target='plot-last-train',
        label='discovers anomaly',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-gojo-final-transfer',
        source='char-gojo-stationmaster',
        target='plot-final-transfer',
        label='enforces lockdown',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-nobara-final-transfer',
        source='char-nobara-lostfound',
        target='plot-final-transfer',
        label='provides station seal',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-station-last-train',
        source='world-cursed-station',
        target='plot-last-train',
        label='takes place at',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-ticket-awakening',
        source='world-ticket-curse',
        target='plot-ticket-awakening',
        label='core cursed object',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-last-train-ticket',
        source='plot-last-train',
        target='plot-ticket-awakening',
        label='leads to',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-ticket-final',
        source='plot-ticket-awakening',
        target='plot-final-transfer',
        label='escalates into',
        relationType='belongs_to',
        type='smoothstep',
    ),
    EdgePayload(
        id='edge-world-announcement-plot-last-train-1777562934373-2',
        source='world-announcement',
        target='plot-last-train',
        label='triggers legend',
        relationType='relates_to',
        type='smoothstep',
    ),
]
