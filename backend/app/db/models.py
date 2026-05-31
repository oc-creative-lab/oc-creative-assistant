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
    world_brief: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    # first_revision 决策 1：项目简介，供项目库卡片 / 工作台概览编辑与种子拼装使用。
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    # 一个 Project 下三个独立 sub-graph。这里刻意不加 DB 级 ForeignKey：
    # projects↔graphs 互相引用会形成建表环，且 SQLite 不支持 ALTER ADD CONSTRAINT；
    # 沿用本表对 EdgeORM 端点的处理方式，由服务层校验一致性（见 graph_validation）。
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
    # first_revision 决策 1：节点归属到具体 sub-graph。迁移期对旧库 nullable，
    # 由 backfill 按 node_type 回填；新建节点必须带 graph_id。
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
    """对话会话表。

    一个会话对应前端的一个聊天面板上下文; ``thread_id`` 给 LangGraph 的
    Checkpointer 使用, 让同一会话刷新页面后能从 sqlite 取回中间状态。
    ``conversation_summary`` 由摘要压缩节点定期更新, 用于长对话不爆 token。
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
    # 核心事实层: summary_compress 每轮抽取的关键设定 / 决定, 跨轮累积, 不会被
    # conversation_summary 的重压所覆盖, 解决"长对话后早期事实被忘"的核心痛点
    key_facts: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    # summary 已涵盖前 N 条消息的高水位; 用来做摘要压缩的增量节流, 避免每轮都重压
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
    """对话消息表。

    消息只追加, 不就地修改; ``meta`` 用于挂载 cited_node_ids / agent_type 等
    扩展字段, 避免每加一个上下文字段都要改表结构。
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
    """Agent 待确认变更表。

    Agent 想做的画布操作先沉淀在这里, 等用户在前端 staging 面板接受 / 编辑 / 拒绝
    再决定是否真正落到画布。同一 turn 产生的多条变更共享 ``batch_id``,
    支持"接受全部"/"拒绝全部"批量操作; ``pending_id`` 给同一 batch 内的新节点
    分配占位 id, 让边可以引用尚未落库的新节点, 提交时再回填真实 node_id。
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
    """Sub-graph 表（first_revision 决策 1）。

    一个 Project 下含三个独立 sub-graph：故事线(plot) / 角色卡(character) /
    世界观(world)。节点通过 ``NodeORM.graph_id`` 归属到具体 sub-graph；
    ``section`` 用字符串而非 DB Enum，与 ``NodeORM.node_type`` 的处理保持一致，
    迁移更简单。
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
    """项目种子表（first_revision 决策 3）。

    种子是对项目当前状态的压缩快照（worldview / characters / plot / style），
    供 Chat Agent 启动注入。版本随每次重建自增，``source`` 记录触发来源。
    seed_compressor 写入（阶段 5），这里先建表为阶段 1 的数据模型升级铺路。
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
