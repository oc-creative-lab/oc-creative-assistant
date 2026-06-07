"""first_revision phase 6 acceptance tests (cross-sub-graph references).

1. After creating a character -> world cross-subgraph edge, cross_references can find the reference and tag its section;
2. In the reverse direction (viewed from the world node) the direction is incoming;
3. Edges within the same sub-graph don't count as cross-subgraph references.
"""

import uuid

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM
from app.main import app

client = TestClient(app)


def _project() -> dict:
    return client.post("/api/projects", json={"name": f"cross-ref-{uuid.uuid4().hex[:6]}"}).json()


def _add_node(project_id: str, graph_id: str, node_type: str, title: str) -> str:
    node_id = uuid.uuid4().hex
    with SessionLocal.begin() as db:
        db.add(
            NodeORM(
                id=node_id,
                project_id=project_id,
                graph_id=graph_id,
                node_type=node_type,
                title=title,
                content="",
            )
        )
    return node_id


def _add_edge(project_id: str, source: str, target: str, label: str, relation: str) -> str:
    edge_id = uuid.uuid4().hex
    with SessionLocal.begin() as db:
        db.add(
            EdgeORM(
                id=edge_id,
                project_id=project_id,
                source=source,
                target=target,
                label=label,
                relation_type=relation,
            )
        )
    return edge_id


def test_cross_graph_reference_visible_from_both_sides():
    project = _project()
    char_id = _add_node(project["id"], project["character_graph_id"], "character", "Xiaoming")
    world_id = _add_node(project["id"], project["world_graph_id"], "worldbuilding", "Flame Kingdom")
    _add_edge(project["id"], char_id, world_id, "belongs to", "belongs_to")

    # From the character's view: 1 cross-subgraph reference, pointing to world, direction outgoing
    resp = client.get(f"/api/projects/{project['id']}/nodes/{char_id}/cross_references").json()
    assert resp["section"] == "character"
    assert len(resp["references"]) == 1
    ref = resp["references"][0]
    assert ref["other_section"] == "world"
    assert ref["other_title"] == "Flame Kingdom"
    assert ref["direction"] == "outgoing"
    assert ref["relation_label"] == "belongs to"

    # From the worldbuilding view: the same edge, direction incoming, pointing back to character
    back = client.get(f"/api/projects/{project['id']}/nodes/{world_id}/cross_references").json()
    assert len(back["references"]) == 1
    assert back["references"][0]["other_section"] == "character"
    assert back["references"][0]["direction"] == "incoming"


def test_intra_graph_edge_not_counted_as_cross_reference():
    project = _project()
    a = _add_node(project["id"], project["character_graph_id"], "character", "A")
    b = _add_node(project["id"], project["character_graph_id"], "character", "B")
    _add_edge(project["id"], a, b, "nemesis", "conflicts_with")

    resp = client.get(f"/api/projects/{project['id']}/nodes/{a}/cross_references").json()
    assert resp["references"] == []  # both in the character sub-graph, not a cross-subgraph reference
