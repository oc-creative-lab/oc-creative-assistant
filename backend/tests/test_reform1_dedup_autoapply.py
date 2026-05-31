"""改造 1 验收测试：自动落库 + 按名去重(更新而非新建) + 撤销删除。

用 stub provider 注入确定的抽取结果，验证：
1. 第一轮抽出"角色A" → 自动落库到 character sub-graph（无需手动接受）；
2. 第二轮再次抽到同名"角色A"(带新属性) → 更新已有卡片，不新建第二张；
3. DELETE 端点能撤销该节点。
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
    return client.post("/api/projects", json={"name": f"改造1-{uuid.uuid4().hex[:6]}"}).json()


def _session_with_msg(project_id: str) -> tuple[str, str]:
    session = client.post("/api/sessions", json={"project_id": project_id, "title": "t"}).json()
    with SessionLocal.begin() as db:
        msg = append_message(db, session_id=session["id"], role="assistant", content="好")
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

    # 第一轮：创建角色A，自动落库（无需手动接受）
    res1 = _run_extractor(
        monkeypatch, session_id, project["id"], mid,
        StructuredEntity(type="character", name="角色A", attributes={"魔法": "火系"}),
        "创建一个角色叫角色A",
    )
    assert res1["extraction_count"] == 1
    # extraction_applied 暴露已落库卡片
    assert any(it["change_type"] == "create_node" and it["title"] == "角色A" for it in res1["extraction_applied"])

    nodes = _char_nodes(project)
    a_nodes = [n for n in nodes if n["title"] == "角色A"]
    assert len(a_nodes) == 1  # 已自动落库

    # 第二轮：补充特征 → 更新同一张卡，不新建
    res2 = _run_extractor(
        monkeypatch, session_id, project["id"], mid,
        StructuredEntity(type="character", name="角色A", attributes={"外貌": "红发"}),
        "角色A是红发",
    )
    assert any(it["change_type"] == "update_node" for it in res2["extraction_applied"])

    nodes2 = _char_nodes(project)
    a_nodes2 = [n for n in nodes2 if n["title"] == "角色A"]
    assert len(a_nodes2) == 1  # 仍然只有一张卡片
    assert "红发" in a_nodes2[0]["content"]  # 新信息已并入
    assert "火系" in a_nodes2[0]["content"]  # 旧信息保留


def _nodes_in(graph_id: str):
    return client.get(f"/api/graphs/{graph_id}").json()["nodes"]


def test_dedup_update_applies_to_world_and_plot(monkeypatch):
    """同样的去重→更新逻辑对世界观 / 剧情节点同样生效（不止角色）。"""
    cases = [
        ("world", "worldbuilding", "world_graph_id", "火焰王国", {"气候": "炎热"}, {"统治者": "炎帝"}),
        ("plot", "plot", "plot_graph_id", "第一章相遇", {"地点": "车站"}, {"结果": "结盟"}),
    ]
    for entity_type, _node_type, graph_key, name, attr1, attr2 in cases:
        project = _project()
        session_id, mid = _session_with_msg(project["id"])

        _run_extractor(
            monkeypatch, session_id, project["id"], mid,
            StructuredEntity(type=entity_type, name=name, attributes=attr1),
            f"提到{name}",
        )
        first = [n for n in _nodes_in(project[graph_key]) if n["title"] == name]
        assert len(first) == 1, f"{entity_type} 首轮应落库 1 张卡"

        # 再次提到同名 → 更新而非新建
        _run_extractor(
            monkeypatch, session_id, project["id"], mid,
            StructuredEntity(type=entity_type, name=name, attributes=attr2),
            f"补充{name}",
        )
        again = [n for n in _nodes_in(project[graph_key]) if n["title"] == name]
        assert len(again) == 1, f"{entity_type} 同名不应重复新建"
        content = again[0]["content"]
        assert list(attr1.values())[0] in content and list(attr2.values())[0] in content


def test_delete_node_endpoint_undoes(monkeypatch):
    project = _project()
    session_id, mid = _session_with_msg(project["id"])
    _run_extractor(
        monkeypatch, session_id, project["id"], mid,
        StructuredEntity(type="character", name="临时角色", attributes={}),
        "加个临时角色",
    )
    node_id = _char_nodes(project)[0]["id"]

    resp = client.delete(f"/api/projects/{project['id']}/nodes/{node_id}")
    assert resp.status_code == 204
    assert _char_nodes(project) == []
