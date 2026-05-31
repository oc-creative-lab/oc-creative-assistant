"""first_revision 阶段 4 验收测试（后台 B-agent）。

用 stub LLM 覆盖三条核心行为：
1. extraction_enabled 关闭时，question_planner / structured_extractor 全程 no-op
   （旧 FloatingChatDock 流程不受影响）；
2. extraction_enabled 开启时，structured_extractor 从对话抽出实体并写入 staging；
3. 接受抽出的 character staging 后，节点落到该项目的 character sub-graph。

不依赖真实 LLM / 网络：直接调用节点函数并 monkeypatch 其 provider。
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
    """返回预置结构化输出的假 provider。"""

    def __init__(self, output):
        self._output = output

    def structured(self, messages, schema):
        return self._output


def _new_project() -> dict:
    return client.post("/api/projects", json={"name": f"阶段4-{uuid.uuid4().hex[:6]}"}).json()


def _new_session_with_assistant_msg(project_id: str) -> tuple[str, str]:
    """建会话 + 一条 assistant 消息（structured_extractor 需要 message_id）。"""
    session = client.post("/api/sessions", json={"project_id": project_id, "title": "t"}).json()
    session_id = session["id"]
    with SessionLocal.begin() as db:
        msg = append_message(db, session_id=session_id, role="assistant", content="好的")
        message_id = msg.id
    return session_id, message_id


def test_gate_off_is_noop():
    """gate 关闭：两个节点都返回空 dict，不产生任何副作用。"""
    assert question_planner_node({}) == {}
    assert extractor_mod.structured_extractor_node({}) == {}


def test_extraction_creates_staging_and_lands_in_character_graph(monkeypatch):
    project = _new_project()
    session_id, message_id = _new_session_with_assistant_msg(project["id"])

    extraction = StructuredExtractionOutput(
        reasoning="抽出小明与火焰王国",
        entities=[
            StructuredEntity(type="character", name="小明", attributes={"魔法": "火系"}),
            StructuredEntity(type="world", name="火焰王国", attributes={}),
        ],
        relations=[StructuredRelation(source_name="小明", target_name="火焰王国", label="属于")],
        deferred_fields=[],
    )
    monkeypatch.setattr(extractor_mod, "get_llm_provider", lambda: _StubProvider(extraction))

    result = extractor_mod.structured_extractor_node(
        {
            "extraction_enabled": True,
            "session_id": session_id,
            "project_id": project["id"],
            "assistant_message_id": message_id,
            "user_message": "我有个主角叫小明, 会火系魔法, 属于火焰王国",
            "recent_messages": [],
        }
    )

    # 2 个 create_node + 1 个 create_edge = 3 条 staging
    assert result["extraction_count"] == 3
    batch_id = result["extraction_batch_id"]
    assert batch_id

    # 接受整批 → canvas_apply 落库
    resp = client.patch(f"/api/staging/batch/{batch_id}", json={"action": "accept_all"})
    assert resp.status_code == 200

    # 小明应落到 character sub-graph；火焰王国落到 world sub-graph
    char_nodes = client.get(f"/api/graphs/{project['character_graph_id']}").json()["nodes"]
    world_nodes = client.get(f"/api/graphs/{project['world_graph_id']}").json()["nodes"]
    assert "小明" in {n["title"] for n in char_nodes}
    assert "火焰王国" in {n["title"] for n in world_nodes}
    # 角色卡不画线，但关系数据仍在 character sub-graph 内（小明→火焰王国跨子图，阶段6处理）


def test_question_planner_writes_hint(monkeypatch):
    import app.agents.nodes.question_planner as planner_mod

    planned = QuestionPlannerOutput(reasoning="补能力来源", next_question="火系魔法怎么来的?", target_field="能力来源")
    monkeypatch.setattr(planner_mod, "get_llm_provider", lambda: _StubProvider(planned))

    out = planner_mod.question_planner_node(
        {"extraction_enabled": True, "recent_messages": [], "user_message": "小明会火系魔法"}
    )
    assert out["next_question_hint"] == "火系魔法怎么来的?"
