from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ProjectORM(Base):
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

    nodes: Mapped[list["NodeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    edges: Mapped[list["EdgeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class NodeORM(Base):
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
    # 选择方案 B：Python 侧使用 node_type，数据库列名仍保持 type，减少表结构破坏。
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
    # 选择方案 B：Python 侧使用 edge_type，数据库列名仍保持 type，兼容当前 API/表语义。
    edge_type: Mapped[str] = mapped_column(
        "type",
        String,
        nullable=False,
        default="smoothstep",
        server_default="smoothstep",
    )
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

    # 数据库层已保证 source/target 必须指向存在的节点。
    # source/target 与 edge.project_id 的项目一致性由 graph_store 业务层校验，避免引入复杂联合外键。
