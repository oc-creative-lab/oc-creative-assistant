"""first_revision phase 4 acceptance tests (background B-agent).

Uses a stub LLM to cover three core behaviors:
1. When extraction_enabled is off, question_planner / structured_extractor are no-ops throughout
   (the legacy FloatingChatDock flow is unaffected);
2. When extraction_enabled is on, structured_extractor extracts entities from the conversation and writes them to staging;
3. After accepting an extracted character staging entry, the node lands in the project's character sub-graph.

No dependency on a real LLM / network: the node functions are called directly with their provider monkeypatched.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.agents.nodes.structured_extractor as extractor_mod
from app.agents.nodes.question_planner import question_planner_node
from app.agents.schemas import (
    QuestionPlannerOutput,
    StructuredEntity,
    StructuredExtractionOutput,
    StructuredRelation,
)
from app.db.database import SessionLocal
from app.db.models import ChatSessionORM
from app.main import app
from app.services.chat_repository import append_message

client = TestClient(app)


class _StubProvider:
    """Fake provider that returns a preset structured output."""

    def __init__(self, output):
        self._output = output

    def structured(self, messages, schema):
        return self._output


def _new_project() -> dict:
    return client.post("/api/projects", json={"name": f"phase4-{uuid.uuid4().hex[:6]}"}).json()


def _new_session_with_assistant_msg(project_id: str) -> tuple[str, str]:
    """Create a session + one assistant message (structured_extractor needs a message_id)."""
    session = client.post("/api/sessions", json={"project_id": project_id, "title": "t"}).json()
    session_id = session["id"]
    with SessionLocal.begin() as db:
        msg = append_message(db, session_id=session_id, role="assistant", content="OK")
        message_id = msg.id
    return session_id, message_id


def test_gate_off_is_noop():
    """Gate off: both nodes return an empty dict and produce no side effects."""
    assert question_planner_node({}) == {}
    assert extractor_mod.structured_extractor_node({}) == {}


def test_extraction_creates_staging_and_lands_in_character_graph(monkeypatch):
    project = _new_project()
    session_id, message_id = _new_session_with_assistant_msg(project["id"])

    extraction = StructuredExtractionOutput(
        reasoning="Extract Xiaoming and Flame Kingdom",
        entities=[
            StructuredEntity(type="character", name="Xiaoming", attributes={"magic": "fire-type"}),
            StructuredEntity(type="world", name="Flame Kingdom", attributes={}),
        ],
        relations=[StructuredRelation(source_name="Xiaoming", target_name="Flame Kingdom", label="belongs to")],
        deferred_fields=[],
    )
    monkeypatch.setattr(extractor_mod, "get_llm_provider", lambda: _StubProvider(extraction))

    result = extractor_mod.structured_extractor_node(
        {
            "extraction_enabled": True,
            "session_id": session_id,
            "project_id": project["id"],
            "assistant_message_id": message_id,
            "user_message": "I have a protagonist named Xiaoming who uses fire-type magic and belongs to the Flame Kingdom",
            "recent_messages": [],
        }
    )

    # 2 create_node + 1 create_edge = 3 staging entries
    assert result["extraction_count"] == 3
    batch_id = result["extraction_batch_id"]
    assert batch_id

    # Accept the whole batch -> canvas_apply persists it
    resp = client.patch(f"/api/staging/batch/{batch_id}", json={"action": "accept_all"})
    assert resp.status_code == 200

    # Xiaoming should land in the character sub-graph; Flame Kingdom in the world sub-graph
    char_nodes = client.get(f"/api/graphs/{project['character_graph_id']}").json()["nodes"]
    world_nodes = client.get(f"/api/graphs/{project['world_graph_id']}").json()["nodes"]
    assert "Xiaoming" in {n["title"] for n in char_nodes}
    assert "Flame Kingdom" in {n["title"] for n in world_nodes}
    # Character cards draw no edges, but the relation data still lives in the character sub-graph (Xiaoming -> Flame Kingdom is cross-subgraph, handled in phase 6)


def test_question_planner_writes_hint(monkeypatch):
    import app.agents.nodes.question_planner as planner_mod

    planned = QuestionPlannerOutput(reasoning="Fill in the source of the ability", next_question="Where does fire-type magic come from?", target_field="ability source")
    monkeypatch.setattr(planner_mod, "get_llm_provider", lambda: _StubProvider(planned))

    out = planner_mod.question_planner_node(
        {"extraction_enabled": True, "recent_messages": [], "user_message": "Xiaoming uses fire-type magic"}
    )
    assert out["next_question_hint"] == "Where does fire-type magic come from?"


def test_question_planner_tolerates_none_structured_output(monkeypatch):
    import app.agents.nodes.question_planner as planner_mod

    monkeypatch.setattr(planner_mod, "get_llm_provider", lambda: _StubProvider(None))

    out = planner_mod.question_planner_node(
        {"extraction_enabled": True, "recent_messages": [], "user_message": "hello"}
    )
    assert out == {}


def test_structured_extractor_tolerates_none_structured_output(monkeypatch):
    monkeypatch.setattr(extractor_mod, "get_llm_provider", lambda: _StubProvider(None))

    out = extractor_mod.structured_extractor_node(
        {
            "extraction_enabled": True,
            "session_id": "sess-1",
            "project_id": "proj-1",
            "assistant_message_id": "msg-1",
            "user_message": "hello",
            "recent_messages": [],
        }
    )
    assert out == {}
