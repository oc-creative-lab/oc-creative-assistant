"""Graph 业务的 SQLAlchemy ORM 模型。

项目是 graph 的生命周期边界，节点和边都归属于项目。
本模块只描述数据库结构和 ORM 关系，不处理 API DTO 转换或业务校验。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ProjectORM(Base):
    """项目表。

    当前 PoC 只创建默认项目，但表结构保留多项目能力。
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

    nodes: Mapped[list["NodeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    edges: Mapped[list["EdgeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class NodeORM(Base):
    """画布节点表。

    节点保存角色、世界观、剧情等创作内容，并作为向量索引的主要数据来源。
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
    """画布连线表。

    边保存 Vue Flow 端点、handle 和创作关系类型。端点同项目一致性由服务层校验，
    避免在 PoC 阶段引入复杂联合外键。
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
