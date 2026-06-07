"""Reform 1 acceptance tests: auto-persist + dedup by name (update instead of create) + undo delete.

A stub provider injects deterministic extraction results to verify:
1. First round extracts "Character A" -> auto-persisted into the character sub-graph (no manual accept needed);
2. Second round extracts the same-named "Character A" again (with new attributes) -> updates the existing card, doesn't create a second one;
3. The DELETE endpoint can undo (delete) the node.
"""

import uuid

from fastapi.testclient import TestClient

import app.agents.nodes.structured_extractor as extractor_mod
from app.agents.schemas import StructuredEntity, StructuredExtractionOutput
from app.db.database import SessionLocal
from app.main import app
from app.services.chat_repository import append_message

client = TestClient(app)


class _StubProvider:
    def __init__(self, output):
        self._output = output

    def structured(self, messages, schema):
        return self._output


def _project() -> dict:
    return client.post("/api/projects", json={"name": f"reform1-{uuid.uuid4().hex[:6]}"}).json()


def _session_with_msg(project_id: str) -> tuple[str, str]:
    session = client.post("/api/sessions", json={"project_id": project_id, "title": "t"}).json()
    with SessionLocal.begin() as db:
        msg = append_message(db, session_id=session["id"], role="assistant", content="OK")
        mid = msg.id
    return session["id"], mid


def _run_extractor(monkeypatch, session_id, project_id, message_id, entity, user_msg):
    out = StructuredExtractionOutput(reasoning="x", entities=[entity], relations=[], deferred_fields=[])
    monkeypatch.setattr(extractor_mod, "get_llm_provider", lambda: _StubProvider(out))
    return extractor_mod.structured_extractor_node(
        {
            "extraction_enabled": True,
            "session_id": session_id,
            "project_id": project_id,
            "assistant_message_id": message_id,
            "user_message": user_msg,
            "recent_messages": [],
        }
    )


def _char_nodes(project):
    return client.get(f"/api/graphs/{project['character_graph_id']}").json()["nodes"]


def test_autoapply_then_dedup_updates_same_card(monkeypatch):
    project = _project()
    session_id, mid = _session_with_msg(project["id"])

    # First round: create Character A, auto-persisted (no manual accept needed)
    res1 = _run_extractor(
        monkeypatch, session_id, project["id"], mid,
        StructuredEntity(type="character", name="Character A", attributes={"magic": "fire-type"}),
        "Create a character called Character A",
    )
    assert res1["extraction_count"] == 1
    # extraction_applied exposes the persisted card
    assert any(it["change_type"] == "create_node" and it["title"] == "Character A" for it in res1["extraction_applied"])

    nodes = _char_nodes(project)
    a_nodes = [n for n in nodes if n["title"] == "Character A"]
    assert len(a_nodes) == 1  # already auto-persisted

    # Second round: add a trait -> update the same card, don't create a new one
    res2 = _run_extractor(
        monkeypatch, session_id, project["id"], mid,
        StructuredEntity(type="character", name="Character A", attributes={"appearance": "red hair"}),
        "Character A has red hair",
    )
    assert any(it["change_type"] == "update_node" for it in res2["extraction_applied"])

    nodes2 = _char_nodes(project)
    a_nodes2 = [n for n in nodes2 if n["title"] == "Character A"]
    assert len(a_nodes2) == 1  # still only one card
    assert "red hair" in a_nodes2[0]["content"]  # new info merged in
    assert "fire-type" in a_nodes2[0]["content"]  # old info preserved


def _nodes_in(graph_id: str):
    return client.get(f"/api/graphs/{graph_id}").json()["nodes"]


def test_dedup_update_applies_to_world_and_plot(monkeypatch):
    """The same dedup -> update logic works for worldbuilding / plot nodes too (not just characters)."""
    cases = [
        ("world", "worldbuilding", "world_graph_id", "Flame Kingdom", {"climate": "hot"}, {"ruler": "Flame Emperor"}),
        ("plot", "plot", "plot_graph_id", "Chapter 1: The Encounter", {"location": "station"}, {"result": "alliance"}),
    ]
    for entity_type, _node_type, graph_key, name, attr1, attr2 in cases:
        project = _project()
        session_id, mid = _session_with_msg(project["id"])

        _run_extractor(
            monkeypatch, session_id, project["id"], mid,
            StructuredEntity(type=entity_type, name=name, attributes=attr1),
            f"Mention {name}",
        )
        first = [n for n in _nodes_in(project[graph_key]) if n["title"] == name]
        assert len(first) == 1, f"{entity_type} should persist 1 card on the first round"

        # Mention the same name again -> update instead of create
        _run_extractor(
            monkeypatch, session_id, project["id"], mid,
            StructuredEntity(type=entity_type, name=name, attributes=attr2),
            f"Add to {name}",
        )
        again = [n for n in _nodes_in(project[graph_key]) if n["title"] == name]
        assert len(again) == 1, f"{entity_type} should not create a duplicate for the same name"
        content = again[0]["content"]
        assert list(attr1.values())[0] in content and list(attr2.values())[0] in content


def test_delete_node_endpoint_undoes(monkeypatch):
    project = _project()
    session_id, mid = _session_with_msg(project["id"])
    _run_extractor(
        monkeypatch, session_id, project["id"], mid,
        StructuredEntity(type="character", name="Temp Character", attributes={}),
        "Add a temp character",
    )
    node_id = _char_nodes(project)[0]["id"]

    resp = client.delete(f"/api/projects/{project['id']}/nodes/{node_id}")
    assert resp.status_code == 204
    assert _char_nodes(project) == []
