"""SQLAlchemy ORM models for the graph domain.

A project is the lifecycle boundary of a graph; nodes and edges both belong to a
project. This module only describes the database schema and ORM relationships; it
does not handle API DTO conversion or business validation.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ProjectORM(Base):
    """Projects table.

    The current PoC only creates a default project, but the schema retains
    multi-project capability.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    world_brief: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    # first_revision decision 1: project brief, used by project library cards / workspace overview editing and seed assembly.
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    # Optional cover image, stored as a base64 data URL; shown on the overview page and as the library card background.
    cover_image: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    # Three independent sub-graphs under one Project. DB-level ForeignKeys are
    # deliberately omitted here: projects<->graphs referencing each other would
    # form a table-creation cycle, and SQLite does not support ALTER ADD CONSTRAINT;
    # following this table's handling of EdgeORM endpoints, consistency is validated
    # by the service layer (see graph_validation).
    plot_graph_id: Mapped[str | None] = mapped_column(String, nullable=True)
    character_graph_id: Mapped[str | None] = mapped_column(String, nullable=True)
    world_graph_id: Mapped[str | None] = mapped_column(String, nullable=True)
    nodes: Mapped[list["NodeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    edges: Mapped[list["EdgeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    graphs: Mapped[list["GraphORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    seeds: Mapped[list["ProjectSeedORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class NodeORM(Base):
    """Canvas nodes table.

    Nodes store creative content such as characters, worldbuilding, and plot, and
    serve as the primary data source for the vector index.
    """

    __tablename__ = "nodes"
    __table_args__ = (
        Index("ix_nodes_project_sort_order", "project_id", "sort_order"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # first_revision decision 1: nodes belong to a specific sub-graph. Nullable for
    # legacy databases during migration, backfilled by node_type via backfill;
    # newly created nodes must carry a graph_id.
    graph_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("graphs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[str] = mapped_column("type", String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    type_label: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ProjectORM] = relationship(back_populates="nodes")


class EdgeORM(Base):
    """Canvas edges table.

    Edges store Vue Flow endpoints, handles, and the creative relation type.
    Same-project consistency of the endpoints is validated by the service layer,
    avoiding the introduction of complex composite foreign keys during the PoC
    stage.
    """

    __tablename__ = "edges"
    __table_args__ = (
        Index("ix_edges_project_sort_order", "project_id", "sort_order"),
        Index("ix_edges_source", "source"),
        Index("ix_edges_target", "target"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(
        String,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    source_handle: Mapped[str | None] = mapped_column(String, nullable=True)
    target_handle: Mapped[str | None] = mapped_column(String, nullable=True)
    edge_type: Mapped[str] = mapped_column(
        "type",
        String,
        nullable=False,
        default="smoothstep",
        server_default="smoothstep",
    )
    relation_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="relates_to",
        server_default="relates_to",
    )
    waypoint: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    animated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ProjectORM] = relationship(back_populates="edges")
    source_node: Mapped[NodeORM] = relationship(
        "NodeORM",
        foreign_keys=[source],
        passive_deletes=True,
    )
    target_node: Mapped[NodeORM] = relationship(
        "NodeORM",
        foreign_keys=[target],
        passive_deletes=True,
    )


class ChatSessionORM(Base):
    """Chat sessions table.

    One session corresponds to one chat panel context on the frontend;
    ``thread_id`` is used by LangGraph's Checkpointer, so the same session can
    retrieve its intermediate state from sqlite after a page refresh.
    ``conversation_summary`` is periodically updated by the summary compression
    node, used to keep long conversations from blowing the token budget.
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    conversation_summary: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    # Core facts layer: key settings / decisions extracted by summary_compress each
    # turn, accumulated across turns, not overwritten by the heavy recompression of
    # conversation_summary, solving the core pain point of "early facts being forgotten after long conversations"
    key_facts: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    # high-water mark of how many leading messages the summary already covers; used for incremental throttling of summary compression, to avoid recompressing every turn
    summary_message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ProjectORM] = relationship()
    messages: Mapped[list["ChatMessageORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageORM.created_at",
    )
    staging_items: Mapped[list["AgentStagingORM"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ChatMessageORM(Base):
    """Chat messages table.

    Messages are append-only, never modified in place; ``meta`` is used to attach
    extension fields such as cited_node_ids / agent_type, avoiding a schema change
    every time a context field is added.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped[ChatSessionORM] = relationship(back_populates="messages")
    staging_items: Mapped[list["AgentStagingORM"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class AgentStagingORM(Base):
    """Agent pending-changes table.

    The canvas operations the Agent wants to perform are first staged here, and
    only after the user accepts / edits / rejects them in the frontend staging
    panel is it decided whether to actually apply them to the canvas. Multiple
    changes produced in the same turn share a ``batch_id``, supporting batch
    "accept all" / "reject all" operations; ``pending_id`` assigns a placeholder id
    to new nodes within the same batch, so edges can reference new nodes not yet
    persisted, with the real node_id backfilled at commit time.
    """

    __tablename__ = "agent_staging"
    __table_args__ = (
        Index("ix_agent_staging_session_status", "session_id", "status"),
        Index("ix_agent_staging_batch_order", "batch_id", "order_in_batch"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[str] = mapped_column(String, nullable=False)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    payload_edited: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    agent_type: Mapped[str] = mapped_column(
        String, nullable=False, default="", server_default=""
    )
    reasoning: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    order_in_batch: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    session: Mapped[ChatSessionORM] = relationship(back_populates="staging_items")
    message: Mapped[ChatMessageORM] = relationship(back_populates="staging_items")


class GraphORM(Base):
    """Sub-graphs table (first_revision decision 1).

    A Project contains three independent sub-graphs: storyline (plot) /
    character cards (character) / worldbuilding (world). Nodes belong to a specific
    sub-graph via ``NodeORM.graph_id``; ``section`` uses a string rather than a DB
    Enum, consistent with the handling of ``NodeORM.node_type``, making migration
    simpler.
    """

    __tablename__ = "graphs"
    __table_args__ = (
        Index("ix_graphs_project_section", "project_id", "section"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # section ∈ {'plot', 'character', 'world'}
    section: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[ProjectORM] = relationship(back_populates="graphs")


class ProjectSeedORM(Base):
    """Project seeds table (first_revision decision 3).

    A seed is a compressed snapshot of the project's current state (worldview /
    characters / plot / style), injected at Chat Agent startup. The version
    increments on each rebuild, and ``source`` records the trigger origin.
    Written by seed_compressor (phase 5); the table is created here first to pave
    the way for the phase 1 data model upgrade.
    """

    __tablename__ = "project_seeds"
    __table_args__ = (
        Index("ix_project_seeds_project_version", "project_id", "version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    seed_json: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # source ∈ {'chat_end', 'user_edit'}
    source: Mapped[str] = mapped_column(String, nullable=False, default="user_edit", server_default="user_edit")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[ProjectORM] = relationship(back_populates="seeds")
