"""项目应用服务。

负责项目 CRUD 与种子读取，并在创建项目时自动建立三个 sub-graph
（plot / character / world）。索引与 graph 节点读写仍由 graph_store 负责，
本模块只维护项目与 sub-graph 的生命周期边界。
"""

import json
import uuid

from fastapi import HTTPException

from app.db.database import SessionLocal
from app.db.models import GraphORM, ProjectORM, ProjectSeedORM
from app.schemas import (
    ProjectCreateRequest,
    ProjectDetailPayload,
    ProjectSeedPayload,
    ProjectSummaryPayload,
    ProjectUpdateRequest,
)
from app.services.graph_repository import require_project


_SECTIONS = ("plot", "character", "world")


def _latest_seed_orm(session, project_id: str) -> ProjectSeedORM | None:
    """读取项目最新版本的种子；不存在返回 None。"""
    return (
        session.query(ProjectSeedORM)
        .filter(ProjectSeedORM.project_id == project_id)
        .order_by(ProjectSeedORM.version.desc())
        .first()
    )


def _seed_to_payload(seed: ProjectSeedORM | None) -> ProjectSeedPayload | None:
    if seed is None:
        return None
    return ProjectSeedPayload(
        id=seed.id,
        project_id=seed.project_id,
        version=seed.version,
        seed_json=seed.seed_json,
        source=seed.source,
        created_at=seed.created_at,
    )


def _project_to_detail(session, project: ProjectORM) -> ProjectDetailPayload:
    return ProjectDetailPayload(
        id=project.id,
        name=project.name,
        description=project.description,
        plot_graph_id=project.plot_graph_id,
        character_graph_id=project.character_graph_id,
        world_graph_id=project.world_graph_id,
        latest_seed=_seed_to_payload(_latest_seed_orm(session, project.id)),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _create_subgraphs(session, project: ProjectORM) -> None:
    """为项目创建三个 sub-graph 并回填 FK（与迁移 backfill 同构）。"""
    graph_ids: dict[str, str] = {}
    for section in _SECTIONS:
        graph_id = uuid.uuid4().hex
        session.add(GraphORM(id=graph_id, project_id=project.id, section=section))
        graph_ids[section] = graph_id

    project.plot_graph_id = graph_ids["plot"]
    project.character_graph_id = graph_ids["character"]
    project.world_graph_id = graph_ids["world"]


def list_projects() -> list[ProjectSummaryPayload]:
    """列出全部项目，供项目库卡片展示。"""
    with SessionLocal() as session:
        projects = (
            session.query(ProjectORM).order_by(ProjectORM.updated_at.desc()).all()
        )
        return [
            ProjectSummaryPayload(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
        ]


def get_project_detail(project_id: str) -> ProjectDetailPayload:
    """读取项目详情（含三个 graph_id 与最新种子）。"""
    with SessionLocal() as session:
        project = require_project(session, project_id)
        return _project_to_detail(session, project)


def create_project(payload: ProjectCreateRequest) -> ProjectDetailPayload:
    """创建项目并自动创建三个 sub-graph。"""
    with SessionLocal.begin() as session:
        project = ProjectORM(
            id=uuid.uuid4().hex,
            name=payload.name,
            description=payload.description,
        )
        session.add(project)
        session.flush()
        _create_subgraphs(session, project)
        session.flush()
        return _project_to_detail(session, project)


def update_project(project_id: str, payload: ProjectUpdateRequest) -> ProjectDetailPayload:
    """更新项目 name / description（None 表示不改）。"""
    with SessionLocal.begin() as session:
        project = require_project(session, project_id)
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        session.flush()
        return _project_to_detail(session, project)


def delete_project(project_id: str) -> None:
    """级联删除项目（graphs / nodes / edges / sessions / seeds 随外键级联）。"""
    with SessionLocal.begin() as session:
        project = require_project(session, project_id)
        session.delete(project)


def get_latest_seed(project_id: str) -> ProjectSeedPayload | None:
    """读取项目当前种子。"""
    with SessionLocal() as session:
        require_project(session, project_id)
        return _seed_to_payload(_latest_seed_orm(session, project_id))


def rebuild_seed(project_id: str) -> ProjectSeedPayload:
    """强制重建项目种子，版本自增。

    调用 seed_compressor 真正压缩项目当前状态；项目尚无内容或 LLM
    失败时回退到空结构占位，保证接口始终返回一条种子。
    """
    # 延迟导入避免与 agents 包的潜在循环依赖。
    from app.agents.seed_compressor import build_seed_json

    seed_json = build_seed_json(project_id) or json.dumps(
        {
            "worldview_summary": "",
            "main_characters": [],
            "plot_outline": "",
            "style_notes": "",
        },
        ensure_ascii=False,
    )
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        latest = _latest_seed_orm(session, project_id)
        next_version = (latest.version + 1) if latest else 1
        seed = ProjectSeedORM(
            id=uuid.uuid4().hex,
            project_id=project_id,
            version=next_version,
            seed_json=seed_json,
            source="user_edit",
        )
        session.add(seed)
        session.flush()
        payload = _seed_to_payload(seed)

    if payload is None:  # pragma: no cover - 仅为类型收敛
        raise HTTPException(status_code=500, detail="Failed to rebuild seed")
    return payload
