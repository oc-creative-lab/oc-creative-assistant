"""Agent 结构化输出 Schema。

每个 Schema 同时承担三个职责:
1. LangChain `with_structured_output()` 的 JSON Schema 来源, 满足 proposal 4.3.2 第②层约束;
2. FastAPI 响应模型, 供前端 TypeScript DTO 复用;
3. UI 渲染契约——前端只渲染这些字段, 满足 proposal 4.3.2 第③层约束。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SuggestedNode(BaseModel):
    """Inspiration / Structure Agent 建议创建的节点摘要。"""

    nodeType: str = Field(description="character / worldbuilding / plot 等节点类型")
    title: str = Field(description="建议节点标题")
    reason: str = Field(description="解释为什么需要这个节点")


class InspirationOutput(BaseModel):
    """Inspiration Agent 输出。"""

    summary: str = Field(description="一句话概括当前节点的创作状态")
    questions: list[str] = Field(description="启发用户继续创作的问题")
    missing_parts: list[str] = Field(description="当前设定中缺失的关键点")
    suggested_nodes: list[SuggestedNode] = Field(description="建议新增的节点")
    boundary_notice: str = Field(description="提醒用户这些只是建议, 由用户决定是否采纳")


class ResearchReference(BaseModel):
    """Research Agent 输出的单条参考资料。"""

    title: str = Field(description="参考资料标题")
    source: str = Field(description="来源节点 ID 或外部资料标识")
    snippet: str = Field(description="关键内容摘要, 不超过两句话")
    relevance: str = Field(description="与当前节点的关联说明")


class ResearchOutput(BaseModel):
    """Research Agent 输出。"""

    summary: str = Field(description="一句话概括检索到的整体结论")
    references: list[ResearchReference] = Field(description="结构化参考资料列表")
    suggested_tags: list[str] = Field(description="便于后续分类的标签建议")
    boundary_notice: str = Field(description="提醒用户这些只是参考, 不是事实定论")


class CharacterCard(BaseModel):
    """Structure Agent 整理出的角色卡。"""

    name: str = Field(description="角色名称")
    one_liner: str = Field(description="一句话简介")
    motivation: str = Field(description="核心动机")
    key_relationships: list[str] = Field(description="关键关系列表, 形如 '与 X: 师徒'")


class Relationship(BaseModel):
    """Structure Agent 输出的关系图三元组。"""

    source: str = Field(description="起点角色名称")
    relation: str = Field(description="关系类型")
    target: str = Field(description="终点角色名称")


class PlotBeat(BaseModel):
    """Structure Agent 输出的剧情节拍。"""

    order: int = Field(description="节拍顺序, 从 1 开始")
    title: str = Field(description="节拍标题")
    involved_characters: list[str] = Field(description="该节拍涉及的角色名")
    summary: str = Field(description="不超过两句话的节拍概述, 不允许写完整对白")


class StructureOutput(BaseModel):
    """Structure Agent 输出。"""

    summary: str = Field(description="一句话概括整理后的结构骨架")
    character_cards: list[CharacterCard] = Field(description="结构化角色卡列表")
    relationship_graph: list[Relationship] = Field(description="关系三元组列表")
    plot_outline: list[PlotBeat] = Field(description="剧情节拍列表")
    boundary_notice: str = Field(description="提醒用户这是骨架而非成文")