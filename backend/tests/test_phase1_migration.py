"""first_revision phase 1 acceptance tests.

Covers three acceptance cases:
1. Legacy projects (no sub-graph) load correctly after migration, with nodes backfilled into the matching sub-graph by type;
2. Newly created projects automatically get three sub-graphs;
3. plot / character / world nodes can be loaded separately by graph_id.

The data directory is pointed at a temporary directory by conftest, leaving the dev database untouched.
"""

import uuid

from fastapi.testclient import TestClient

from app.db.database import SessionLocal, init_db, _ensure_subgraph_backfill
from app.db.models import NodeORM, ProjectORM
from app.main import app
from app.services.graph_store import get_subgraph


client = TestClient(app)


def _seed_legacy_project() -> str:
    """Insert a "legacy" project directly: no sub-graph, with empty node graph_id."""
    init_db()
    project_id = uuid.uuid4().hex
    with SessionLocal.begin() as session:
        session.add(ProjectORM(id=project_id, name="Legacy Project"))
        session.flush()
        for node_type in ("character", "worldbuilding", "plot", "idea"):
            session.add(
                NodeORM(
                    id=f"{project_id}-{node_type}",
                    project_id=project_id,
                    graph_id=None,
                    node_type=node_type,
                    title=f"{node_type} node",
                    content="",
                )
            )
    return project_id


def test_legacy_project_migrates_and_loads():
    """After backfilling a legacy project: three sub-graphs are created and nodes land by type (idea goes into plot for now)."""
    project_id = _seed_legacy_project()

    # Simulate the application startup migration.
    _ensure_subgraph_backfill()

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["plot_graph_id"]
    assert detail["character_graph_id"]
    assert detail["world_graph_id"]

    # Character nodes should only appear in the character sub-graph.
    char_graph = get_subgraph(detail["character_graph_id"])
    assert {n.type for n in char_graph.nodes} == {"character"}

    world_graph = get_subgraph(detail["world_graph_id"])
    assert {n.type for n in world_graph.nodes} == {"worldbuilding"}

    # The plot sub-graph holds both plot and "other types" (idea).
    plot_graph = get_subgraph(detail["plot_graph_id"])
    assert {n.type for n in plot_graph.nodes} == {"plot", "idea"}

    # No nodes lost: all four legacy nodes are placed.
    total = len(char_graph.nodes) + len(world_graph.nodes) + len(plot_graph.nodes)
    assert total == 4


def test_create_project_makes_three_subgraphs():
    """A new project automatically creates three sub-graphs, all initially empty."""
    resp = client.post("/api/projects", json={"name": "New Project", "description": "x"})
    assert resp.status_code == 200
    detail = resp.json()

    graph_ids = [
        detail["plot_graph_id"],
        detail["character_graph_id"],
        detail["world_graph_id"],
    ]
    assert all(graph_ids)
    assert len(set(graph_ids)) == 3  # three distinct sub-graphs

    for gid in graph_ids:
        graph = client.get(f"/api/graphs/{gid}")
        assert graph.status_code == 200
        assert graph.json()["nodes"] == []


def test_default_project_loads_by_subgraph():
    """After migration, the default sample project can load each partition's nodes separately by graph_id."""
    pid = client.get("/api/projects/default").json()["id"]
    detail = client.get(f"/api/projects/{pid}").json()

    char_graph = client.get(f"/api/graphs/{detail['character_graph_id']}").json()
    assert len(char_graph["nodes"]) > 0
    assert {n["type"] for n in char_graph["nodes"]} == {"character"}
