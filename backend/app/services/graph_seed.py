"""Graph default data definitions.

This module belongs to the service layer's initialization configuration and is
responsible for providing the default project and the example graph shown on the
first screen. It does not access the database, nor does it handle HTTP requests
or vector index synchronization.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas import EdgePayload, NodePayload, PositionPayload


_DEFAULT_OC_JSON = r"""
{
  "format": "oc",
  "version": 1,
  "project": {
    "name": "Hogwarts: The Final Siege",
    "description": "A dramatic Harry Potter-inspired test story set during the final siege of Hogwarts. As dark forces attack the castle, Harry, Hermione, Draco, and the defenders must decide whether to protect the school through force, sacrifice, trust, or forbidden magic. The story focuses on the collapse of the Ancient Shield, the dangerous Astronomy Passage, and the emotional cost of defending Hogwarts."
  },
  "nodes": [
    {
      "id": "char-draft-1780894131147-1",
      "node_type": "character",
      "title": "Harry Potter",
      "content": "Harry Potter is a young wizard at Hogwarts. In this test story, he stands at the center of the final siege. He wants to protect the school and his friends, but he fears that victory may require someone to sacrifice their happiest memory to strengthen the ancient shield.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0,
        "fields": {}
      },
      "position_x": 260,
      "position_y": 40,
      "sort_order": 0
    },
    {
      "id": "plot-draft-1780894228405-1",
      "node_type": "plot",
      "title": "The Shield Begins to Fall",
      "content": "As fear spreads inside Hogwarts, silver cracks appear across the Ancient Shield. Hermione realizes that the shield is weakening not only because of enemy attacks, but because the defenders are beginning to distrust each other.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 574.2315508696063,
      "position_y": -117.8156434069039,
      "sort_order": 0
    },
    {
      "id": "world-draft-1780894208212-2",
      "node_type": "worldbuilding",
      "title": "The Astronomy Passage",
      "content": "The Astronomy Passage is a hidden tunnel beneath the Astronomy Tower. It was originally designed as an emergency evacuation route, but during the final siege it becomes a double-edged tactical asset. If trusted and secured, it can help move students away from danger; if compromised, it may allow enemies to breach the inner castle or track the evacuation group. Draco reveals the passage to Harry and Hermione, forcing the defenders to decide whether his warning is sincere and whether trust can still exist between former enemies.",
      "meta": {
        "text": "Worldbuilding",
        "tags": [
          "Worldbuilding"
        ],
        "status": "draft",
        "sortOrder": 1
      },
      "position_x": 0,
      "position_y": 0,
      "sort_order": 0
    },
    {
      "id": "char-draft-1780894159667-2",
      "node_type": "character",
      "title": "Hermione Granger",
      "content": "Hermione Granger is Harry's close friend and the main strategist during the siege. She discovers that the ancient shield around Hogwarts is powered not only by defensive spells, but also by personal memories willingly given by its defenders.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 480,
      "position_y": 40,
      "sort_order": 1
    },
    {
      "id": "plot-draft-1780894408716-1",
      "node_type": "plot",
      "title": "Draco Reveals the Passage",
      "content": "Draco approaches Harry and Hermione with a warning about the Astronomy Passage beneath the tower. He reveals that the passage is no longer a safe evacuation route. Voldemort's followers have already marked the tunnel with a tracking curse, so anyone who enters it will expose the location of the Great Hall evacuation group.\n\nDraco does not ask the defenders to use the passage. Instead, he urges them to seal it before the enemy can track the students through it. This changes his role from offering an escape route to preventing a hidden breach.\n\nHermione realizes that Draco's information is valuable not because it opens a path, but because it helps the defenders avoid a trap. Harry must decide whether to trust Draco's warning before the enemy activates the tracking curse.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 734.0237394405855,
      "position_y": 188.1203416224279,
      "sort_order": 1
    },
    {
      "id": "83d522abc7e64a258bceb56329845501",
      "node_type": "worldbuilding",
      "title": "Hogwarts Castle (Siege Setting)",
      "content": "Hogwarts Castle is the central battlefield of the final siege. During the attack, it is no longer only a school, but a layered defensive stronghold shaped by magic, memory, hidden routes, and human trust. Its survival depends not only on walls and spells, but also on whether the defenders can remain united under fear, deception, and direct assault.",
      "meta": {
        "text": "AI suggestion",
        "tags": [
          "AI suggestion"
        ],
        "status": "synced",
        "sortOrder": 0
      },
      "position_x": 120,
      "position_y": 120,
      "sort_order": 1
    },
    {
      "id": "char-draft-1780894179760-3",
      "node_type": "character",
      "title": "Draco Malfoy",
      "content": "Draco Malfoy knows a hidden passage beneath the astronomy tower. The passage could allow enemies to enter Hogwarts, but Draco also has the chance to reveal it to Harry and change the course of the battle.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 700,
      "position_y": 40,
      "sort_order": 2
    },
    {
      "id": "plot-draft-1780894432449-2",
      "node_type": "plot",
      "title": "The Memory Offering Debate",
      "content": "As the Ancient Shield continues to weaken, Harry offers to give up his happiest memory of friendship. He argues that one painful sacrifice is better than watching Hogwarts fall. Some defenders support him because they are desperate for a quick solution.\n\nHermione challenges the decision. She argues that if Harry gives up the memory that helps him trust others, the defenders may save the castle but lose the very emotional bond that gives their resistance meaning. McGonagall also warns that a commander cannot allow a student to bear the entire moral cost of the battle.\n\nThe debate divides the defenders. The shield needs strength soon, but no one agrees on whether sacrifice, trust, or strategy should come first.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 425.22666423113617,
      "position_y": 289.0150388419254,
      "sort_order": 2
    },
    {
      "id": "002d03da411c445bae8c225f5e5a6da4",
      "node_type": "worldbuilding",
      "title": "Battlefield Structure",
      "content": "",
      "meta": {
        "text": "AI suggestion",
        "tags": [
          "AI suggestion"
        ],
        "status": "synced",
        "sortOrder": 0
      },
      "position_x": 120,
      "position_y": 120,
      "sort_order": 2
    },
    {
      "id": "char-draft-1780894321663-4",
      "node_type": "character",
      "title": "Professor McGonagall",
      "content": "Professor McGonagall commands the castle's organized defense during the final siege. She is responsible for protecting students, coordinating teachers, and holding the main gates long enough for evacuation plans to work.\n\nUnlike Harry, McGonagall must think in terms of the whole battlefield. She cannot make decisions based only on personal loyalty. Her greatest fear is that emotional decisions will expose the younger students to danger.\n\nMcGonagall respects Harry's courage, but she also recognizes that courage without coordination can become reckless. She needs Hermione's strategy, Harry's resolve, and Draco's information to work together before the castle falls.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 40,
      "position_y": 200,
      "sort_order": 3
    },
    {
      "id": "plot-draft-1780894467462-4",
      "node_type": "plot",
      "title": "The Choice at the Astronomy Passage",
      "content": "Harry, Hermione, Draco, and a small group of defenders reach the entrance to the Astronomy Passage. The passage demands a spoken vow before it will open. Draco must name who he intends to protect, knowing that a false vow will trap them underground.\n\nDraco hesitates because he knows many defenders still doubt him. Harry must decide whether to publicly trust him. Hermione watches carefully, understanding that this moment may affect the Ancient Shield itself: if trust is restored among the defenders, the shield may strengthen without requiring Harry's memory.\n\nThe passage opens only when Draco names the students trapped in the Great Hall. This proves that his intention is genuine, but it also reveals that enemies are already approaching from the other end of the tunnel.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 857.2025969602732,
      "position_y": 457.34182973433155,
      "sort_order": 3
    },
    {
      "id": "world-draft-1780911210385-1",
      "node_type": "worldbuilding",
      "title": "Ancient Shield",
      "content": "The Ancient Shield is an old protective enchantment surrounding Hogwarts during the final siege. It blocks dark magic from directly entering the castle grounds, but its strength depends on the emotional unity of the defenders. When fear, distrust, or despair spreads among students and teachers, silver cracks begin to appear across the shield. Hermione discovers that the shield is not only a defensive spell, but also a reflection of whether the defenders still trust one another.",
      "meta": {
        "text": "Worldbuilding",
        "tags": [
          "Worldbuilding"
        ],
        "status": "draft",
        "parentId": "83d522abc7e64a258bceb56329845501",
        "sortOrder": 0
      },
      "position_x": 0,
      "position_y": 0,
      "sort_order": 3
    },
    {
      "id": "char-draft-1780894543399-5",
      "node_type": "character",
      "title": "Lord Voldemort",
      "content": "Lord Voldemort leads the dark forces during the final siege of Hogwarts. His goal is not only to destroy the castle's physical defenses, but also to break the emotional unity of the defenders. He understands that the Ancient Shield is weakened by distrust, fear, and despair, so he attacks both the walls of Hogwarts and the morale of the people inside.\n\nVoldemort believes that love, memory, and loyalty are weaknesses that can be exploited. He orders his followers to spread false rumors, threaten captured students, and force the defenders into morally impossible choices. He wants Harry to believe that sacrifice is the only way to save others, because that belief isolates Harry from his friends.\n\nHis main battlefield strategy is psychological siege. He does not simply want to enter Hogwarts; he wants the defenders to open the way themselves by losing trust in each other.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 260,
      "position_y": 200,
      "sort_order": 4
    },
    {
      "id": "plot-draft-1780894630727-1",
      "node_type": "plot",
      "title": "The Siege Begins",
      "content": "The final siege begins when Voldemort's forces surround Hogwarts and attack the outer defensive line. Bellatrix leads the first wave, targeting magical statues, protective barriers, and visible symbols of resistance.\n\nAt first, the Ancient Shield holds. However, Voldemort's strategy is not only to break the shield with dark magic. He also spreads fear by sending messages into the castle, claiming that the defenders have already been betrayed from within.\n\nThis opening attack establishes two battlefields: the physical siege outside the castle and the psychological siege inside it.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 246.4574637352742,
      "position_y": -218.21014349179498,
      "sort_order": 4
    },
    {
      "id": "world-draft-1780911237009-2",
      "node_type": "worldbuilding",
      "title": "Memory Offering",
      "content": "Memory Offering is a dangerous ritual that can restore part of the Ancient Shield by converting a defender's happiest memory into magical power. The ritual is effective but irreversible: the person who offers the memory loses not only the event itself, but also the emotional warmth attached to it. Harry considers using this ritual because he believes one personal sacrifice may save the castle, while Hermione fears that losing a memory of friendship may weaken the very trust the shield needs.",
      "meta": {
        "text": "Worldbuilding",
        "tags": [
          "Worldbuilding"
        ],
        "status": "draft",
        "parentId": "83d522abc7e64a258bceb56329845501",
        "sortOrder": 1
      },
      "position_x": 0,
      "position_y": 0,
      "sort_order": 4
    },
    {
      "id": "char-draft-1780894558600-6",
      "node_type": "character",
      "title": "Bellatrix Lestrange",
      "content": "Bellatrix Lestrange serves as Voldemort's most aggressive battlefield commander. She leads the direct assault against the outer Siege Lines and uses violent spectacle to spread panic among the defenders.\n\nUnlike Voldemort, who focuses on psychological collapse, Bellatrix believes terror should be visible and immediate. She targets the magical statues, defensive barriers, and student morale at the same time. Her attacks are designed to make the defenders feel that resistance is meaningless.\n\nBellatrix also becomes a personal threat to Hermione. She recognizes Hermione as the strategic mind behind the defense and tries to force her into making rushed decisions. Her presence turns the battle from a tactical conflict into an emotional one.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 480,
      "position_y": 200,
      "sort_order": 5
    },
    {
      "id": "plot-draft-1780894655049-2",
      "node_type": "plot",
      "title": "Snape's Notes Are Found",
      "content": "Hermione discovers a set of coded notes that may have been left by Severus Snape. The notes describe the Ancient Shield as a magic that responds to trust between former enemies, not merely to individual sacrifice.\n\nSome defenders refuse to believe the notes because they do not trust Snape. Others argue that the information matches what they have observed: the shield weakens most when distrust spreads.\n\nThe notes introduce a new possibility. If Draco genuinely chooses to protect the students, his vow may strengthen the shield more safely than Harry's Memory Offering.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 171.33814107237288,
      "position_y": 26.375504933693037,
      "sort_order": 5
    },
    {
      "id": "world-draft-1780911277525-3",
      "node_type": "worldbuilding",
      "title": "Siege Lines",
      "content": "Siege Lines are the defensive layers formed around Hogwarts during the battle. The outer line is held by enchanted statues, barriers, and senior defenders; the middle line is protected by teachers, wards, and moving barricades; the inner line surrounds the Great Hall and protects younger students. When Bellatrix breaks the outer line, the defenders are forced inward, making every later decision about the shield, the passage, and Harry's sacrifice more urgent.",
      "meta": {
        "text": "Worldbuilding",
        "tags": [
          "Worldbuilding"
        ],
        "status": "draft",
        "parentId": "002d03da411c445bae8c225f5e5a6da4",
        "sortOrder": 0
      },
      "position_x": 0,
      "position_y": 0,
      "sort_order": 5
    },
    {
      "id": "char-draft-1780894573094-7",
      "node_type": "character",
      "title": "Lucius Malfoy",
      "content": "Lucius Malfoy acts as a political and psychological weapon during the siege. He knows that Draco may reveal the Astronomy Passage to Harry, and he tries to stop Draco by reminding him of family loyalty, fear, and shame.\n\nLucius does not command the battlefield as directly as Bellatrix, but he understands how to pressure people through reputation and obligation. He tries to convince Draco that the defenders will never truly accept him, even if he helps them.\n\nLucius's role intensifies Draco's trust dilemma. If Draco follows his father, the Astronomy Passage may become an enemy route into Hogwarts. If Draco rejects him, he must publicly choose the defenders over his own family.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 700,
      "position_y": 200,
      "sort_order": 6
    },
    {
      "id": "plot-draft-1780894683414-3",
      "node_type": "plot",
      "title": "Bellatrix Breaks the Outer Line",
      "content": "Bellatrix intensifies the attack on the outer Siege Line. Her forces destroy several magical statues and force the defenders to retreat toward the middle line. The visible collapse creates panic among students inside the castle.\n\nMcGonagall orders the teachers and older students to stabilize the middle line. She refuses to abandon the younger students in the Great Hall, even though reinforcing the outer defense would be tactically useful.\n\nThis event increases pressure on every other decision. The defenders have less time to debate the shield, the passage, and Draco's loyalty.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 635.7768198736337,
      "position_y": 1035.140051805151,
      "sort_order": 6
    },
    {
      "id": "world-draft-1780911302972-4",
      "node_type": "worldbuilding",
      "title": "Great Hall Inner Defense",
      "content": "The Great Hall Inner Defense is the last protective zone inside Hogwarts. It shelters younger students, wounded defenders, and evacuation groups while the battle moves closer to the heart of the castle. McGonagall commands this line because abandoning it would mean sacrificing the most vulnerable people in the school. The Great Hall becomes the moral center of the siege: every strategic decision must be judged by whether it protects the people gathered there.",
      "meta": {
        "text": "Worldbuilding",
        "tags": [
          "Worldbuilding"
        ],
        "status": "draft",
        "parentId": "002d03da411c445bae8c225f5e5a6da4",
        "sortOrder": 1
      },
      "position_x": 0,
      "position_y": 0,
      "sort_order": 6
    },
    {
      "id": "char-draft-1780894592022-8",
      "node_type": "character",
      "title": "Severus Snape",
      "content": "Severus Snape appears in the defenders' information network as an ambiguous figure. Some defenders believe he left behind secret notes about the Ancient Shield before the siege began, while others suspect the notes may be a trap.\n\nThe notes suggest that the Ancient Shield was never meant to be restored by one person's sacrifice. Instead, it responds most strongly when former enemies choose to protect the same people. This information, if trusted, could connect Draco's vow at the Astronomy Passage with the recovery of the shield.\n\nSnape's role is indirect but crucial. He is not present as a battlefield commander, yet the uncertainty around his notes forces the defenders to decide whether truth can come from someone they do not fully trust.",
      "meta": {
        "text": "Character",
        "tags": [
          "Character"
        ],
        "status": "draft",
        "sortOrder": 0,
        "fields": {}
      },
      "position_x": 40,
      "position_y": 360,
      "sort_order": 7
    },
    {
      "id": "plot-draft-1780894712655-4",
      "node_type": "plot",
      "title": "Voldemort Exploits the Division",
      "content": "Voldemort realizes that Draco's vow has strengthened the Ancient Shield, so he changes strategy. Instead of attacking the shield directly, he spreads the claim that Draco only opened the passage to lead enemies inside.\n\nThe defenders are forced to decide whether to defend Draco publicly. If they hesitate, the renewed distrust may weaken the shield again. If they stand with him, they risk believing someone whose family still serves Voldemort.\n\nThis moment tests the true meaning of the shield. It is no longer only about memory or magic, but about whether the defenders can choose trust while under attack.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 993.548292077676,
      "position_y": 715.7094495092341,
      "sort_order": 7
    },
    {
      "id": "plot-draft-1780894744502-5",
      "node_type": "plot",
      "title": "The Final Stand at the Great Hall",
      "content": "The battle reaches the Great Hall as the inner Siege Line comes under attack. McGonagall coordinates the defenders, Hermione protects the evacuation route, and Harry confronts the choice between sacrificing his memory or trusting the fragile unity that has begun to form.\n\nDraco's information helps evacuate younger students through the Astronomy Passage, but Voldemort's forces attempt to enter from the other end. Bellatrix attacks the defenders' line to force Hermione away from the passage.\n\nThe final stand brings every conflict together: Harry's sacrifice, Hermione's strategy, Draco's loyalty, McGonagall's command, Voldemort's psychological siege, and the Ancient Shield's dependence on trust.",
      "meta": {
        "text": "Plot",
        "tags": [
          "Plot"
        ],
        "status": "draft",
        "sortOrder": 0
      },
      "position_x": 1164.7518772122514,
      "position_y": 1237.2137469243823,
      "sort_order": 8
    }
  ],
  "edges": [
    {
      "source": "plot-draft-1780894228405-1",
      "target": "plot-draft-1780894432449-2",
      "label": "causes",
      "relation_type": "causes",
      "edge_type": "bezier",
      "sort_order": 0
    },
    {
      "source": "world-draft-1780911210385-1",
      "target": "83d522abc7e64a258bceb56329845501",
      "label": "belongs to",
      "relation_type": "belongs_to",
      "edge_type": "bezier",
      "sort_order": 0
    },
    {
      "source": "plot-draft-1780894408716-1",
      "target": "plot-draft-1780894467462-4",
      "label": "causes",
      "relation_type": "causes",
      "edge_type": "bezier",
      "sort_order": 1
    },
    {
      "source": "world-draft-1780911237009-2",
      "target": "83d522abc7e64a258bceb56329845501",
      "label": "belongs to",
      "relation_type": "belongs_to",
      "edge_type": "bezier",
      "sort_order": 1
    },
    {
      "source": "plot-draft-1780894467462-4",
      "target": "plot-draft-1780894712655-4",
      "label": "develops into",
      "relation_type": "develops_into",
      "edge_type": "bezier",
      "sort_order": 2
    },
    {
      "source": "world-draft-1780911277525-3",
      "target": "002d03da411c445bae8c225f5e5a6da4",
      "label": "belongs to",
      "relation_type": "belongs_to",
      "edge_type": "bezier",
      "sort_order": 2
    },
    {
      "source": "plot-draft-1780894630727-1",
      "target": "plot-draft-1780894228405-1",
      "label": "causes",
      "relation_type": "causes",
      "edge_type": "bezier",
      "sort_order": 3
    },
    {
      "source": "world-draft-1780911302972-4",
      "target": "002d03da411c445bae8c225f5e5a6da4",
      "label": "belongs to",
      "relation_type": "belongs_to",
      "edge_type": "bezier",
      "sort_order": 3
    },
    {
      "source": "plot-draft-1780894683414-3",
      "target": "plot-draft-1780894744502-5",
      "label": "breach forces final stand",
      "relation_type": "causes",
      "edge_type": "bezier",
      "sort_order": 7
    },
    {
      "source": "plot-draft-1780894712655-4",
      "target": "plot-draft-1780894744502-5",
      "label": "leads to the final battle",
      "relation_type": "causes",
      "edge_type": "bezier",
      "sort_order": 8
    },
    {
      "source": "plot-draft-1780894432449-2",
      "target": "plot-draft-1780894467462-4",
      "label": "conflicts with",
      "relation_type": "conflicts_with",
      "edge_type": "bezier",
      "sort_order": 10
    },
    {
      "source": "plot-draft-1780894655049-2",
      "target": "plot-draft-1780894228405-1",
      "label": "reveals the shield's secret",
      "relation_type": "references",
      "edge_type": "bezier",
      "sort_order": 13
    }
  ]
}
"""

_DEFAULT_OC: dict[str, Any] = json.loads(_DEFAULT_OC_JSON)
_DEFAULT_PROJECT = _DEFAULT_OC["project"]

DEFAULT_PROJECT_ID = "default-project"
DEFAULT_PROJECT_NAME = str(_DEFAULT_PROJECT["name"])
DEFAULT_PROJECT_DESCRIPTION = str(_DEFAULT_PROJECT.get("description") or "")

_TYPE_LABEL_BY_NODE_TYPE = {
    "character": "Character",
    "plot": "Plot",
    "worldbuilding": "Worldbuilding",
}


def _coerce_tags(meta: dict[str, Any]) -> list[str]:
    tags = meta.get("tags", [])
    if not isinstance(tags, list):
        return []
    return [tag for tag in tags if isinstance(tag, str)]


def _coerce_sort_order(meta: dict[str, Any]) -> int:
    value = meta.get("sortOrder", 0)
    return value if isinstance(value, int) else 0


def _node_from_snapshot(raw: dict[str, Any]) -> NodePayload:
    node_type = str(raw.get("node_type") or "plot")
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    parent_id = meta.get("parentId")

    return NodePayload(
        id=str(raw["id"]),
        type=node_type,
        nodeType=node_type,
        title=str(raw.get("title") or "Untitled"),
        content=str(raw.get("content") or ""),
        meta=str(meta.get("text") or ""),
        typeLabel=_TYPE_LABEL_BY_NODE_TYPE.get(node_type, node_type.title()),
        tags=_coerce_tags(meta),
        status=str(meta.get("status") or "draft"),
        parentId=parent_id if isinstance(parent_id, str) and parent_id else None,
        sortOrder=_coerce_sort_order(meta),
        position=PositionPayload(
            x=float(raw.get("position_x") or 0.0),
            y=float(raw.get("position_y") or 0.0),
        ),
    )


def _edge_from_snapshot(index: int, raw: dict[str, Any]) -> EdgePayload:
    return EdgePayload(
        id=f"edge-default-{index:02d}",
        source=str(raw["source"]),
        target=str(raw["target"]),
        label=str(raw.get("label") or "related"),
        relationType=str(raw.get("relation_type") or "relates_to"),
        type=str(raw.get("edge_type") or "bezier"),
    )


DEFAULT_NODES = [_node_from_snapshot(raw) for raw in _DEFAULT_OC["nodes"]]
DEFAULT_EDGES = [
    _edge_from_snapshot(index, raw)
    for index, raw in enumerate(_DEFAULT_OC["edges"])
]
