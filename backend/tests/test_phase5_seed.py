"""first_revision 阶段 5 验收测试（种子机制）。

1. rebuild_seed 产出含 worldview/characters/plot/style 的种子 JSON，版本自增；
2. load_context_node 能把最新种子读进 state.seed_context。

用 stub provider 注入确定的 SeedOutput，避免依赖真实 LLM。
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
    project = client.post("/api/projects", json={"name": f"种子-{uuid.uuid4().hex[:6]}"}).json()
    pid = project["id"]
    # 直接塞一个节点，让 seed_compressor 有内容可压。
    with SessionLocal.begin() as db:
        db.add(
            NodeORM(
                id=uuid.uuid4().hex,
                project_id=pid,
                graph_id=project["character_graph_id"],
                node_type="character",
                title="暮岩",
                content="矮人铁匠, 身世存疑",
            )
        )
    return pid


def test_rebuild_seed_produces_real_seed_and_bumps_version(monkeypatch):
    pid = _project_with_node()

    seed_out = SeedOutput(
        worldview_summary="矮人铁匠部族的低魔世界",
        main_characters=["暮岩"],
        plot_outline="暮岩因身世与族群冲突",
        style_notes="厚重内省",
    )
    monkeypatch.setattr(seed_mod, "get_llm_provider", lambda: _StubProvider(seed_out))

    first = rebuild_seed(pid)
    assert first.version == 1
    data = json.loads(first.seed_json)
    assert set(data.keys()) == {"worldview_summary", "main_characters", "plot_outline", "style_notes"}
    assert data["main_characters"] == ["暮岩"]

    second = rebuild_seed(pid)
    assert second.version == 2  # 版本自增


def test_load_context_injects_latest_seed(monkeypatch):
    pid = _project_with_node()
    seed_out = SeedOutput(worldview_summary="测试世界", main_characters=[], plot_outline="", style_notes="")
    monkeypatch.setattr(seed_mod, "get_llm_provider", lambda: _StubProvider(seed_out))
    rebuild_seed(pid)

    # 建会话 + 一条消息，让 load_context 有 session 可加载。
    session = client.post("/api/sessions", json={"project_id": pid, "title": "t"}).json()
    with SessionLocal.begin() as db:
        append_message(db, session_id=session["id"], role="user", content="hi")

    out = load_context_node({"session_id": session["id"], "selected_node_ids": []})
    assert "测试世界" in out["seed_context"]
