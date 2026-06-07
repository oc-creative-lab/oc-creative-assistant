"""first_revision phase 5 acceptance tests (seed mechanism).

1. rebuild_seed produces a seed JSON containing worldview/characters/plot/style, with the version auto-incrementing;
2. load_context_node can read the latest seed into state.seed_context.

A stub provider injects a deterministic SeedOutput to avoid depending on a real LLM.
"""

import json
import uuid

from fastapi.testclient import TestClient

import app.agents.seed_compressor as seed_mod
from app.agents.nodes.load_context import load_context_node
from app.agents.schemas import SeedOutput
from app.db.database import SessionLocal
from app.db.models import NodeORM
from app.main import app
from app.services.chat_repository import append_message
from app.services.project_service import rebuild_seed

client = TestClient(app)


class _StubProvider:
    def __init__(self, output):
        self._output = output

    def structured(self, messages, schema):
        return self._output


def _project_with_node() -> str:
    project = client.post("/api/projects", json={"name": f"seed-{uuid.uuid4().hex[:6]}"}).json()
    pid = project["id"]
    # Insert a node directly so seed_compressor has content to compress.
    with SessionLocal.begin() as db:
        db.add(
            NodeORM(
                id=uuid.uuid4().hex,
                project_id=pid,
                graph_id=project["character_graph_id"],
                node_type="character",
                title="Duskstone",
                content="A dwarven blacksmith with a questionable past",
            )
        )
    return pid


def test_rebuild_seed_produces_real_seed_and_bumps_version(monkeypatch):
    pid = _project_with_node()

    seed_out = SeedOutput(
        worldview_summary="A low-magic world of dwarven blacksmith clans",
        main_characters=["Duskstone"],
        plot_outline="Duskstone clashes with the clan over his origins",
        style_notes="Heavy and introspective",
    )
    monkeypatch.setattr(seed_mod, "get_llm_provider", lambda: _StubProvider(seed_out))

    first = rebuild_seed(pid)
    assert first.version == 1
    data = json.loads(first.seed_json)
    assert set(data.keys()) == {"worldview_summary", "main_characters", "plot_outline", "style_notes"}
    assert data["main_characters"] == ["Duskstone"]

    second = rebuild_seed(pid)
    assert second.version == 2  # version auto-increments


def test_load_context_injects_latest_seed(monkeypatch):
    pid = _project_with_node()
    seed_out = SeedOutput(worldview_summary="Test World", main_characters=[], plot_outline="", style_notes="")
    monkeypatch.setattr(seed_mod, "get_llm_provider", lambda: _StubProvider(seed_out))
    rebuild_seed(pid)

    # Create a session + one message so load_context has a session to load.
    session = client.post("/api/sessions", json={"project_id": pid, "title": "t"}).json()
    with SessionLocal.begin() as db:
        append_message(db, session_id=session["id"], role="user", content="hi")

    out = load_context_node({"session_id": session["id"], "selected_node_ids": []})
    assert "Test World" in out["seed_context"]
