"""first_revision 阶段 6 验收测试（跨 sub-graph 引用）。

1. character → world 的跨子图边创建后，cross_references 能查到该引用并标注 section；
2. 反向（从 world 节点看）方向为 incoming；
3. 同子图内的边不计入跨子图引用。
"""

import uuid

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM
from app.main import app

client = TestClient(app)


def _project() -> dict:
    return client.post("/api/projects", json={"name": f"跨引用-{uuid.uuid4().hex[:6]}"}).json()


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
    char_id = _add_node(project["id"], project["character_graph_id"], "character", "小明")
    world_id = _add_node(project["id"], project["world_graph_id"], "worldbuilding", "火焰王国")
    _add_edge(project["id"], char_id, world_id, "属于", "belongs_to")

    # 从角色看：1 条跨子图引用，指向 world，方向 outgoing
    resp = client.get(f"/api/projects/{project['id']}/nodes/{char_id}/cross_references").json()
    assert resp["section"] == "character"
    assert len(resp["references"]) == 1
    ref = resp["references"][0]
    assert ref["other_section"] == "world"
    assert ref["other_title"] == "火焰王国"
    assert ref["direction"] == "outgoing"
    assert ref["relation_label"] == "属于"

    # 从世界观看：同一条边，方向 incoming，指回 character
    back = client.get(f"/api/projects/{project['id']}/nodes/{world_id}/cross_references").json()
    assert len(back["references"]) == 1
    assert back["references"][0]["other_section"] == "character"
    assert back["references"][0]["direction"] == "incoming"


def test_intra_graph_edge_not_counted_as_cross_reference():
    project = _project()
    a = _add_node(project["id"], project["character_graph_id"], "character", "甲")
    b = _add_node(project["id"], project["character_graph_id"], "character", "乙")
    _add_edge(project["id"], a, b, "死敌", "conflicts_with")

    resp = client.get(f"/api/projects/{project['id']}/nodes/{a}/cross_references").json()
    assert resp["references"] == []  # 同属 character 子图，不算跨子图引用
