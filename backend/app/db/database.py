"""SQLAlchemy database connection and initialization.

This module only handles the SQLite engine, the Session factory, ORM metadata
initialization, and lightweight compatibility for legacy databases. Business
validation lives in the service layer, and the vector index in `app.indexing`.
"""

import json
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.paths import DATABASE_PATH


DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


class Base(DeclarativeBase):
    """The declarative base shared by all ORM models."""


# The local SQLite file lives under backend/data; the path is centralized in app.core.paths to avoid being affected by package hierarchy levels.
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _deserialize_json(value: str | None) -> Any:
    """Deserialize a SQLite JSON field, while staying compatible with plain-string meta in legacy databases.

    Args:
        value: The raw text before SQLAlchemy JSON deserialization.

    Returns:
        The parsed Python object; legacy non-JSON strings are returned as-is.
    """
    if value is None:
        return {}

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    json_deserializer=_deserialize_json,
    future=True,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Enable foreign key constraints for each SQLite connection.

    SQLite does not enforce foreign keys by default; this ensures `ondelete=\"CASCADE\"` actually takes effect in the local desktop database.
    """
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Initialize the ORM table schema and backfill lightweight compatibility fields for legacy PoC databases."""
    # Import the models lazily, ensuring Base.metadata has registered all tables before create_all.
    from app.db.models import (  # noqa: F401
        AgentStagingORM,
        ChatMessageORM,
        ChatSessionORM,
        EdgeORM,
        GraphORM,
        NodeORM,
        ProjectORM,
        ProjectSeedORM,
    )

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema_compatibility()
    _ensure_subgraph_backfill()


def _ensure_sqlite_schema_compatibility() -> None:
    """Backfill newly added columns for legacy PoC databases.

    The project has not yet introduced a full migration system; this only handles
    the minimum compatibility needed for already-shipped local databases.
    """
    with engine.begin() as connection:
        edge_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(edges)").fetchall()
        }

        if "relation_type" not in edge_columns:
            connection.exec_driver_sql(
                "ALTER TABLE edges ADD COLUMN relation_type VARCHAR NOT NULL DEFAULT 'relates_to'"
            )

        if "waypoint" not in edge_columns:
            connection.exec_driver_sql("ALTER TABLE edges ADD COLUMN waypoint TEXT")

        project_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(projects)").fetchall()
        }
        if "world_brief" not in project_columns:
            connection.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN world_brief TEXT NOT NULL DEFAULT ''"
            )

        session_columns = {
            row[1]
            for row in connection.exec_driver_sql(
                "PRAGMA table_info(chat_sessions)"
            ).fetchall()
        }
        if "summary_message_count" not in session_columns:
            connection.exec_driver_sql(
                "ALTER TABLE chat_sessions ADD COLUMN summary_message_count INTEGER NOT NULL DEFAULT 0"
            )

        # first_revision phase 1: new columns needed by the multi sub-graph architecture.
        # create_all only creates the new tables (graphs / project_seeds) and does not add columns to old tables, so add them manually here.
        if "description" not in project_columns:
            connection.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN description TEXT NOT NULL DEFAULT ''"
            )
        if "cover_image" not in project_columns:
            connection.exec_driver_sql(
                "ALTER TABLE projects ADD COLUMN cover_image TEXT NOT NULL DEFAULT ''"
            )
        for column in ("plot_graph_id", "character_graph_id", "world_graph_id"):
            if column not in project_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE projects ADD COLUMN {column} VARCHAR"
                )

        node_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(nodes)").fetchall()
        }
        if "graph_id" not in node_columns:
            connection.exec_driver_sql("ALTER TABLE nodes ADD COLUMN graph_id VARCHAR")


# Assignment rules for node_type → sub-graph section.
# Decision: plot/character/world each belong to their own section; all other types such as idea/research/structure are temporarily assigned to plot.
_SECTION_BY_NODE_TYPE: dict[str, str] = {
    "character": "character",
    "worldbuilding": "world",
    "plot": "plot",
}
_DEFAULT_SECTION = "plot"


def _ensure_subgraph_backfill() -> None:
    """Backfill three sub-graphs for legacy projects that lack them, and place existing nodes accordingly.

    Idempotent: only handles projects whose ``plot_graph_id`` is still empty;
    already-migrated projects are skipped.
    The migration does not break legacy data — node / edge records are kept as-is,
    only the ``graph_id`` dimension is added.
    """
    import uuid

    from app.db.models import GraphORM, NodeORM, ProjectORM

    with SessionLocal.begin() as session:
        projects = session.query(ProjectORM).all()
        for project in projects:
            if project.plot_graph_id:
                continue  # already migrated

            graph_ids: dict[str, str] = {}
            for section in ("plot", "character", "world"):
                graph_id = uuid.uuid4().hex
                session.add(GraphORM(id=graph_id, project_id=project.id, section=section))
                graph_ids[section] = graph_id

            project.plot_graph_id = graph_ids["plot"]
            project.character_graph_id = graph_ids["character"]
            project.world_graph_id = graph_ids["world"]

            nodes = session.query(NodeORM).filter(NodeORM.project_id == project.id).all()
            for node in nodes:
                section = _SECTION_BY_NODE_TYPE.get(node.node_type, _DEFAULT_SECTION)
                node.graph_id = graph_ids[section]