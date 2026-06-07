"""Project application service (first_revision phase 1).

Responsible for project CRUD and seed reading, and automatically creating three
sub-graphs (plot / character / world) when a project is created. Index and graph
node read/write are still handled by graph_store; this module only maintains the
lifecycle boundary of projects and sub-graphs.
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
    """Read the latest version of a project's seed; returns None if it does not exist."""
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
        cover_image=project.cover_image,
        plot_graph_id=project.plot_graph_id,
        character_graph_id=project.character_graph_id,
        world_graph_id=project.world_graph_id,
        latest_seed=_seed_to_payload(_latest_seed_orm(session, project.id)),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _create_subgraphs(session, project: ProjectORM) -> None:
    """Create three sub-graphs for a project and backfill the FKs (structurally identical to the migration backfill)."""
    graph_ids: dict[str, str] = {}
    for section in _SECTIONS:
        graph_id = uuid.uuid4().hex
        session.add(GraphORM(id=graph_id, project_id=project.id, section=section))
        graph_ids[section] = graph_id

    project.plot_graph_id = graph_ids["plot"]
    project.character_graph_id = graph_ids["character"]
    project.world_graph_id = graph_ids["world"]


def list_projects() -> list[ProjectSummaryPayload]:
    """List all projects, for display as cards in the project library."""
    with SessionLocal() as session:
        projects = (
            session.query(ProjectORM).order_by(ProjectORM.updated_at.desc()).all()
        )
        return [
            ProjectSummaryPayload(
                id=p.id,
                name=p.name,
                description=p.description,
                cover_image=p.cover_image,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in projects
        ]


def get_project_detail(project_id: str) -> ProjectDetailPayload:
    """Read project details (including the three graph_ids and the latest seed)."""
    with SessionLocal() as session:
        project = require_project(session, project_id)
        return _project_to_detail(session, project)


def create_project(payload: ProjectCreateRequest) -> ProjectDetailPayload:
    """Create a project and automatically create three sub-graphs."""
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
    """Update a project's name / description / cover image (None means no change)."""
    with SessionLocal.begin() as session:
        project = require_project(session, project_id)
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        if payload.cover_image is not None:
            project.cover_image = payload.cover_image
        session.flush()
        return _project_to_detail(session, project)


def delete_project(project_id: str) -> None:
    """Cascade-delete a project (graphs / nodes / edges / sessions / seeds cascade via foreign keys)."""
    with SessionLocal.begin() as session:
        project = require_project(session, project_id)
        session.delete(project)


def get_latest_seed(project_id: str) -> ProjectSeedPayload | None:
    """Read a project's current seed."""
    with SessionLocal() as session:
        require_project(session, project_id)
        return _seed_to_payload(_latest_seed_orm(session, project_id))


def rebuild_seed(project_id: str) -> ProjectSeedPayload:
    """Force-rebuild a project's seed, with the version auto-incrementing.

    Phase 5: call seed_compressor to actually compress the project's current
    state; when the project has no content yet or the LLM fails, fall back to an
    empty-structure placeholder, ensuring the endpoint always returns a seed.
    """
    # Deferred import to avoid a potential circular dependency with the agents package.
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

    if payload is None:  # pragma: no cover - for type narrowing only
        raise HTTPException(status_code=500, detail="Failed to rebuild seed")
    return payload
