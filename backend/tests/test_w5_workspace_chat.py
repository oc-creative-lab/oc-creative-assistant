"""W5 验收：工作台被动灵感 agent + /workspace_chat SSE。"""

import uuid

from fastapi.testclient import TestClient

import app.agents.workspace_inspiration as wi
from app.agents.schemas import WorkspaceInspirationOutput
from app.main import app

client = TestClient(app)


class _StubProvider:
    def __init__(self, output):
        self._output = output

    def structured(self, messages, schema):
        return self._output


def _project() -> dict:
    return client.post("/api/projects", json={"name": f"W5-{uuid.uuid4().hex[:6]}"}).json()


def test_generate_workspace_output_typed(monkeypatch):
    out = WorkspaceInspirationOutput(reasoning="卡壳", type="question", content="小明最怕什么?")
    monkeypatch.setattr(wi, "get_llm_provider", lambda: _StubProvider(out))
    result = wi.generate_workspace_output("p1", "我卡住了", [])
    assert result.type == "question"
    assert "小明" in result.content


def test_workspace_chat_sse(monkeypatch):
    out = WorkspaceInspirationOutput(reasoning="分享", type="feedback", content="这个反转很赞")
    monkeypatch.setattr(wi, "get_llm_provider", lambda: _StubProvider(out))
    project = _project()
    resp = client.post(
        f"/api/projects/{project['id']}/workspace_chat",
        json={"message": "我想到一个反转", "quoted_node_ids": []},
    )
    assert resp.status_code == 200
    body = resp.text
    assert '"type": "output"' in body
    assert '"output_type": "feedback"' in body
    assert "这个反转很赞" in body
    assert '"type": "done"' in body
