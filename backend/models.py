from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# 项目是 graph 的归属边界；当前 PoC 只创建默认项目，但表结构支持后续多项目。
class ProjectORM(Base):
    __tablename__ = "projects"

    # 项目主键，前端后续用它请求对应 graph。
    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 项目展示名称。
    name: Mapped[str] = mapped_column(String, nullable=False)
    # 项目创建时间，由数据库写入默认值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # 项目最后更新时间，ORM 更新记录时自动刷新。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ORM 关系：当前项目下的所有节点，不是独立数据库列。
    nodes: Mapped[list["NodeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    # ORM 关系：当前项目下的所有边，不是独立数据库列。
    edges: Mapped[list["EdgeORM"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


# 节点表保存画布上的角色、世界观、剧情等业务节点。
class NodeORM(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        # 读取项目 graph 时按保存顺序稳定返回，避免前端列表/画布顺序抖动。
        Index("ix_nodes_project_sort_order", "project_id", "sort_order"),
    )

    # 节点主键，与前端 Vue Flow node id 保持一致。
    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 所属项目 id，删除项目时级联删除节点。
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 选择方案 B：Python 侧使用 node_type，数据库列名仍保持 type，减少表结构破坏。
    # 节点业务类型，例如 character、worldbuilding、plot。
    node_type: Mapped[str] = mapped_column("type", String, nullable=False)
    # 节点标题，展示在画布卡片和左侧列表中。
    title: Mapped[str] = mapped_column(String, nullable=False)
    # 节点正文内容，前端 DTO 中对应 summary/content。
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # meta 使用 JSON 是为了兼容后续结构化标签；API 层目前仍暴露为字符串。
    # 节点元信息，当前主要保存 text 字段。
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    # 节点类型展示标签，例如“角色”“世界观”。
    type_label: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    # 节点在画布上的横向坐标。
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    # 节点在画布上的纵向坐标。
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default=text("0"))
    # 节点保存顺序，用于读取时稳定排序。
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    # 节点创建时间，由数据库写入默认值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # 节点最后更新时间，ORM 更新记录时自动刷新。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ORM 关系：节点所属项目，不是独立数据库列。
    project: Mapped[ProjectORM] = relationship(back_populates="nodes")


# 边表保存 Vue Flow 连线以及用于恢复连线位置的 handle 信息。
class EdgeORM(Base):
    __tablename__ = "edges"
    __table_args__ = (
        # sort_order 用于整体保存后稳定排序；source/target 索引用于后续关系查询扩展。
        Index("ix_edges_project_sort_order", "project_id", "sort_order"),
        Index("ix_edges_source", "source"),
        Index("ix_edges_target", "target"),
    )

    # 边主键，与前端 Vue Flow edge id 保持一致。
    id: Mapped[str] = mapped_column(String, primary_key=True)
    # 所属项目 id，删除项目时级联删除边。
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 起点节点 id，删除节点时级联删除相关边。
    source: Mapped[str] = mapped_column(
        String,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 终点节点 id，删除节点时级联删除相关边。
    target: Mapped[str] = mapped_column(
        String,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 边展示标签，当前 UI 尚未编辑。
    label: Mapped[str] = mapped_column(String, nullable=False, default="", server_default="")
    # 起点连接桩 id，用于恢复 Vue Flow 连线位置。
    source_handle: Mapped[str | None] = mapped_column(String, nullable=True)
    # 终点连接桩 id，用于恢复 Vue Flow 连线位置。
    target_handle: Mapped[str | None] = mapped_column(String, nullable=True)
    # 选择方案 B：Python 侧使用 edge_type，数据库列名仍保持 type，兼容当前 API/表语义。
    # 边渲染类型，例如 smoothstep。
    edge_type: Mapped[str] = mapped_column(
        "type",
        String,
        nullable=False,
        default="smoothstep",
        server_default="smoothstep",
    )
    # 是否启用 Vue Flow 边动画效果。
    animated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # 边保存顺序，用于读取时稳定排序。
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    # 边创建时间，由数据库写入默认值。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # 边最后更新时间，ORM 更新记录时自动刷新。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ORM 关系：边所属项目，不是独立数据库列。
    project: Mapped[ProjectORM] = relationship(back_populates="edges")
    # ORM 关系：起点节点对象，不是独立数据库列。
    source_node: Mapped[NodeORM] = relationship(
        "NodeORM",
        foreign_keys=[source],
        passive_deletes=True,
    )
    # ORM 关系：终点节点对象，不是独立数据库列。
    target_node: Mapped[NodeORM] = relationship(
        "NodeORM",
        foreign_keys=[target],
        passive_deletes=True,
    )

    # 数据库层已保证 source/target 必须指向存在的节点。
    # source/target 与 edge.project_id 的项目一致性由 graph_store 业务层校验，避免引入复杂联合外键。
