"""first_revision 阶段 1 验收测试。

覆盖三条验收用例：
1. 旧项目（无 sub-graph）migration 后能正常加载，节点按类型回填到对应 sub-graph；
2. 新建项目能自动创建三个 sub-graph；
3. 通过 graph_id 能分别加载 plot / character / world 的节点。

数据目录由 conftest 指向临时目录，不影响开发库。
"""

import uuid

from fastapi.testclient import TestClient

from app.db.database import SessionLocal, init_db, _ensure_subgraph_backfill
from app.db.models import NodeORM, ProjectORM
from app.main import app
from app.services.graph_store import get_subgraph


client = TestClient(app)


def _seed_legacy_project() -> str:
    """直接插入一个“旧版”项目：无 sub-graph、节点 graph_id 为空。"""
    init_db()
    project_id = uuid.uuid4().hex
    with SessionLocal.begin() as session:
        session.add(ProjectORM(id=project_id, name="旧项目"))
        session.flush()
        for node_type in ("character", "worldbuilding", "plot", "idea"):
            session.add(
                NodeORM(
                    id=f"{project_id}-{node_type}",
                    project_id=project_id,
                    graph_id=None,
                    node_type=node_type,
                    title=f"{node_type} 节点",
                    content="",
                )
            )
    return project_id


def test_legacy_project_migrates_and_loads():
    """旧项目回填后：三个 sub-graph 建好，节点按类型归位（idea 暂归 plot）。"""
    project_id = _seed_legacy_project()

    # 模拟应用启动迁移。
    _ensure_subgraph_backfill()

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["plot_graph_id"]
    assert detail["character_graph_id"]
    assert detail["world_graph_id"]

    # character 节点应只出现在 character sub-graph。
    char_graph = get_subgraph(detail["character_graph_id"])
    assert {n.type for n in char_graph.nodes} == {"character"}

    world_graph = get_subgraph(detail["world_graph_id"])
    assert {n.type for n in world_graph.nodes} == {"worldbuilding"}

    # plot sub-graph 同时收纳 plot 与“其他类型”(idea)。
    plot_graph = get_subgraph(detail["plot_graph_id"])
    assert {n.type for n in plot_graph.nodes} == {"plot", "idea"}

    # 无节点丢失：四个旧节点全部归位。
    total = len(char_graph.nodes) + len(world_graph.nodes) + len(plot_graph.nodes)
    assert total == 4


def test_create_project_makes_three_subgraphs():
    """新建项目自动创建三个 sub-graph，且初始为空。"""
    resp = client.post("/api/projects", json={"name": "新项目", "description": "x"})
    assert resp.status_code == 200
    detail = resp.json()

    graph_ids = [
        detail["plot_graph_id"],
        detail["character_graph_id"],
        detail["world_graph_id"],
    ]
    assert all(graph_ids)
    assert len(set(graph_ids)) == 3  # 三个不同的 sub-graph

    for gid in graph_ids:
        graph = client.get(f"/api/graphs/{gid}")
        assert graph.status_code == 200
        assert graph.json()["nodes"] == []


def test_default_project_loads_by_subgraph():
    """默认示例项目迁移后能按 graph_id 分别加载各分区节点。"""
    pid = client.get("/api/projects/default").json()["id"]
    detail = client.get(f"/api/projects/{pid}").json()

    char_graph = client.get(f"/api/graphs/{detail['character_graph_id']}").json()
    assert len(char_graph["nodes"]) > 0
    assert {n["type"] for n in char_graph["nodes"]} == {"character"}
