# OC Creative Assistant System 项目设计文档

## 1. Introduction

### 1.1 Background: OC Creation

OC（Original Character）创作是指创作者独立设计原创角色，并围绕这些角色构建完整的世界观体系，包括角色背景、故事设定和人物关系等内容。

与同人创作不同，OC 创作者对自己的角色和叙事拥有完整的原创归属权，因此“创作所有权”是这一创作群体非常重要的核心价值。OC 创作中形成的世界观体系也具有较强的跨媒介潜力，可以进一步发展为漫画、小说、视觉小说和游戏叙事等内容。

---

### 1.2 Problem Statement

大语言模型（LLMs）的发展给 OC 创作群体带来了新的矛盾。一方面，OC 创作者越来越希望使用 AI 支持灵感发散和世界观构建；另一方面，他们又明显抵触 AI 直接生成文本，因为这可能威胁到作品的原创性和作者身份。

因此，OC 创作者希望 AI 成为创作过程中的催化剂，而不是最终内容的生成者。

此外，OC 创作过程本身具有非线性和碎片化特征。灵感经常在角色、设定和剧情之间跳跃，而传统线性文本界面难以有效支持这种创作方式。

现有工具只能部分解决这些问题：

- AI 聊天工具缺乏对世界观设定的持续记忆；
- 世界观管理工具通常依赖人工维护；
- 节点式平台更多面向通用生产力场景，而不是面向创作边界设计。

目前尚缺少一种能够同时结合上下文记忆、结构化创作流程和受限 AI 辅助机制的工具。

本项目提出一个面向 OC 创作者的轻量级 AI 辅助系统 PoC。系统通过节点式工作空间组织碎片化灵感，通过 RAG 将 AI 建议建立在已有设定之上，并通过受限 Agent 提供辅助建议而不是直接生成完整文本。项目希望验证一种核心观点：

> AI 应当辅助创作过程，而不是替代创作者完成创作。

---

## 2. User Analysis

### 2.1 Target Users

本项目的目标用户是 OC 创作者和原创小说作者，主要年龄段为 16–28 岁。

这类用户通常会长期维护自己的虚构世界，包括：

- 角色档案；
- 背景故事；
- 世界观设定；
- 人物关系网络；
- 剧情线索。

这些创作者处于持续创作周期中，一方面需要不断扩展新想法，另一方面也需要维护已有设定之间的一致性。他们更倾向于将 AI 视为思考辅助工具，而不是内容生成主体，并且高度重视创作过程中的原创性和主导权。

---

### 2.2 User Needs & Pain Points

基于市场调研和对八位目标用户的深度访谈，项目识别出四类核心需求。

#### 2.2.1 Idea Structuring

创作灵感往往以碎片形式出现，例如角色、场景、剧情片段等。用户缺少有效方式将这些零散内容连接并组织起来。

---

#### 2.2.2 Consistency Management

随着世界观复杂度增加，创作者越来越难以维护角色关系、时间线和世界观规则之间的一致性。

---

#### 2.2.3 Authorship Control

用户希望 AI 参与思考过程，例如提出问题、提供提示和辅助整理，但不希望 AI 直接生成完整文本。这样可以保留用户对作品的创作主导权和原创归属感。

---

#### 2.2.4 Structured Output

创作者需要将分散的创作内容整理为结构化文档，用于分享、参考或后续协作。

---

## 3. Project Scope

### 3.1 Core Features

本项目的 PoC 聚焦于验证“节点式创作流程 + 受限 AI 辅助”的可行性。系统功能被有意限制为四个核心模块。

---

### 3.1.1 Node-based Editor

系统提供基于 Vue Flow 的节点式工作空间。节点用于表示不同类型的创作片段，例如：

- 角色；
- 设定；
- 剧情。

节点之间的连接关系用于表达这些创作片段之间的逻辑关系。

该设计用于支持非线性和碎片化的创作过程，使用户能够以更灵活的方式组织灵感和世界观内容。

---

### 3.1.2 Constrained Autonomous AI Agents

系统设计了三类职责明确、能力受限的 AI Agent。这些 Agent 的作用被限制在创作辅助范围内，输出内容是引导、摘要或结构化建议，而不是完整叙事文本。

#### Inspiration Agent

Inspiration Agent 用于通过问题和提示帮助用户扩展想法。

它的主要作用包括：

- 提出启发性问题；
- 帮助用户继续发展角色、设定或剧情；
- 支持用户从初步灵感中展开更多创作方向。

---

#### Research Agent

Research Agent 用于进行结构化知识检索。

它的主要作用包括：

- 根据用户需求查找相关知识；
- 返回结构化参考信息；
- 支持用户将外部知识用于世界观构建或设定设计。

---

#### Structure Agent

Structure Agent 用于重新组织节点内容，并帮助生成结构化创作成果。

它的主要作用包括：

- 整理角色卡；
- 构建关系图；
- 整理剧情框架；
- 将分散节点转化为更清晰的结构化内容。

---

### 3.1.3 RAG-based Memory Module

系统允许用户导入已有创作资料，并通过 RAG 机制让 AI 建议建立在已有内容之上。

RAG 记忆模块包含三个向量集合：

- worldbuilding；
- characters；
- plot。

系统通过基础相似度检索，从这些集合中检索与当前任务相关的内容，并将检索结果提供给 Agent 使用。

该模块的设计目标是验证“记忆机制本身”是否能够提升 AI 辅助建议与用户已有设定之间的一致性，而不是构建复杂的高级 RAG 基础设施。

---

### 3.1.4 Structural Visualization

系统可以直接基于已有节点和边数据生成结构化可视化视图，例如：

- 角色关系图；
- 剧情结构视图。

该模块不引入新的数据或复杂推理逻辑，而是从现有节点和连接关系中直接生成可视化结果。

---

### 3.2 Exclusions

为了保证 PoC 的可实现性，本项目明确排除以下功能。

---

#### 3.2.1 Advanced RAG Infrastructure

PoC 阶段不实现高级 RAG 基础设施，包括：

- 多索引结构；
- 语义路由；
- 长期记忆管理。

---

#### 3.2.2 Automated Workflow Execution

虽然系统采用节点式结构表示创作流程，但 PoC 阶段不实现自动化工作流执行，包括：

- 节点自动触发；
- 自动管线执行；
- 复杂流程自动编排。

---

#### 3.2.3 Collaborative Authoring

PoC 阶段不支持多人协作创作，包括：

- 多用户协作；
- 版本控制；
- 冲突解决。

---

### 3.3 Available Extensions

以下功能不属于 PoC 的核心交付范围，但如果时间允许，可以作为后续扩展方向。

#### 3.3.1 Auto-generated Relationship Graphs and Plot Timelines

系统可以进一步支持自动生成关系图谱和剧情时间线。

---

#### 3.3.2 World Inference and “What If” Plot Simulation

系统可以进一步支持世界观推演和“如果……会怎样”的剧情模拟。

---

#### 3.3.3 Multi-user Collaborative Worldbuilding

系统可以进一步支持多用户协作式世界观构建。

---

#### 3.3.4 Participant Mode

系统可以进一步支持用户以参与者身份加入他人已经建立的世界观框架。

---

## 4. High-Level Technical Specification

### 4.1 System Architecture

系统采用三层架构，将界面层、服务层和数据层分离，以保证系统结构清晰并便于维护。

---

### 4.1.1 Interface Layer

界面层采用 Electron + Vue 桌面客户端，包括：

- node editor；
- visualization panel；
- agent sidebar。

前端通过 REST API 与后端通信。

桌面优先的设计可以保证用户创作资产不会离开本地设备。

---

### 4.1.2 Service Layer

服务层采用 FastAPI 后端，主要负责：

- Agent orchestration；
- RAG retrieval；
- business logic。

系统使用 LangGraph 将 Agent 执行组织为 StateGraph，并通过 conditional edge routing 实现非线性的 Agent 执行流程，而不是简单的线性调用。

---

### 4.1.3 Data Layer

数据层包括：

- SQLite；
- ChromaDB；
- LLM API layer。

SQLite 用于存储结构化项目数据。

ChromaDB 用于维护三个向量集合：

- worldbuilding；
- characters；
- plot。

LLM API 层支持通过 Strategy Pattern 切换不同模型。

---

## 4.2 Technology Stack & Design Patterns

项目遵循 minimal incremental principle，即选择能够在同一系统生态中协同工作的组件，避免不必要的跨语言或跨框架复杂度。

---

### 4.2.1 Electron + Vue + Vue Flow

Electron + Vue + Vue Flow 用于构建桌面端节点式创作界面。

选择理由包括：

- 符合团队已有技术经验；
- 支持桌面端本地运行；
- 适合实现节点式 UI；
- 有助于保持用户数据在本地设备中。

每种节点类型都被封装为独立 Vue component，并通过 Factory Pattern 创建，使新增节点类型时不需要修改已有逻辑，符合 Open/Closed Principle。

---

### 4.2.2 FastAPI + LangGraph + LangChain

FastAPI + LangGraph + LangChain 构成服务层。

LangGraph 的 StateGraph 与前端节点编辑器在概念上保持一致：两者都将节点视为状态，将边视为转移条件。这种设计使系统在前端交互和后端 Agent 执行之间具有架构一致性。

Agent 类型共享统一接口，并通过 LangGraph 动态路由。OpenAI 和 DeepSeek 可在 API 层切换。

---

### 4.2.3 ChromaDB + SQLite

ChromaDB 和 SQLite 都是 local-first 的选择，与 Electron 的离线策略一致。

当节点内容发生变化时，Observer Pattern 会触发 ChromaDB 的增量重新索引，使向量状态与当前创作内容保持同步，避免上下文漂移。

---

## 4.3 Component Descriptions

### 4.3.1 Node Editor

Node Editor 基于 Vue Flow 实现。

每个节点都是一个 Vue component，并通过 Factory Pattern 实例化。节点维护自身状态，并通过 Observer Pattern 将变化广播给 RAG 索引层。

---

### 4.3.2 AI Agent Layer

AI Agent Layer 以 LangGraph StateGraph 作为核心骨架，并使用 conditional edge routing。

系统通过三层方式执行“assist, not generate”的约束：

1. system prompt 限制输出形式；
2. `.with_structured_output()` 强制使用预定义 JSON schema；
3. UI 只渲染结构化卡片。

这种设计用于确保 Agent 提供辅助建议，而不是直接生成完整文本。

---

### 4.3.3 RAG Memory Module

RAG Memory Module 使用三个 ChromaDB collections。

当节点内容变化时，系统会进行 incremental re-indexing。

当用户触发 Agent 时，相似度检索结果会被注入 LangGraph shared state，用于支持后续 Agent 输出。

---

### 4.3.4 Structural Visualization

Structural Visualization 直接读取 SQLite 中的 node 和 edge 数据。

当状态变化时，系统通过 Observer Pattern 重新绘制可视化视图。

该模块没有独立业务逻辑。

---

## 5. Development Methodology

### 5.1 Chosen Methodology

项目采用 Agile Scrum，并以两周为一个 Sprint。

选择 Scrum 的原因包括：

- 创作工具需求具有不确定性，适合通过迭代不断细化；
- 十人团队需要结构化协调机制；
- Sprint review 可以作为面向目标用户群体收集反馈的自然检查点。

每个 Sprint 的基本流程为：

```text
planning → development → testing → review → retrospective
````

项目 backlog 使用 GitHub Projects 维护。

---

### 5.2 Development Practices

#### 5.2.1 Version Control & CI/CD

项目使用 Git feature-branch workflow。

每个 Pull Request 必须经过代码评审。

GitHub Actions 会在每个 Pull Request 上运行：

* linting；
* unit tests；
* integration tests。

Electron 构建将自动化覆盖 Windows 和 macOS。

---

#### 5.2.2 Code Quality & AI-Assisted Development

前端使用：

* ESLint；
* Prettier。

后端使用：

* Ruff；
* MyPy。

团队每两周进行一次代码评审，重点关注设计模式遵循情况。

团队可以使用 AI assistants，例如 Copilot 和 Claude，加速样板代码生成，但所有架构决策仍由人工监督。

---

#### 5.2.3 Testing Strategy

项目测试包括：

* unit tests；
* API integration tests；
* end-to-end tests。

端到端测试覆盖关键路径：

```text
project creation → node editing → export
```

此外，所有进入 RAG pipeline 的输入都需要进行 sanitisation。

---

## 6. Timeline

### Sprint 1: Week 1–2 — Foundation

主要目标：

* finalise architecture；
* 搭建 Electron + Vue scaffold；
* 搭建 FastAPI skeleton；
* 完成 ChromaDB prototype；
* 完成全体成员开发环境配置。

---

### Sprint 2: Week 3–4 — Core Interaction

主要目标：

* 实现 Vue Flow node editor；
* 支持基本节点类型，包括 brainstorm、research、orchestration；
* 支持 node creation、connection 和 deletion；
* 实现 basic agent service stubs。

---

### Sprint 3: Week 5–6 — Intelligence Injection

主要目标：

* 实现 RAG memory engine；
* 支持 document ingestion；
* 支持 three-collection indexing；
* 支持 context-aware retrieval；
* 为三类 Agent 集成 LLM。

---

### Sprint 4: Week 7–8 — Integration & Polish

主要目标：

* 实现端到端工作流；
* 支持 spark entry → node editing → structured export；
* 实现 export engine，包括 Markdown 和 PDF；
* 进行 UI/UX refinement；
* 进行 integrated testing。

---

### Sprint 5: Week 9–10 — Hardening & Demo

主要目标：

* performance optimisation；
* security review；
* user testing；
* 邀请 15–20 名目标社区中的 OC 创作者参与测试；
* 完成最终文档和演示准备。

---

## 7. Resources Overview

### 7.1 Core Technology Stack

| Layer    | Technology                              |
| -------- | --------------------------------------- |
| Frontend | Vue + TypeScript, Vue Flow, Electron    |
| Backend  | Python, FastAPI, LangGraph, LangChain   |
| Data     | SQLite, ChromaDB, OpenAI / DeepSeek API |
| Tooling  | Electron Builder, Pandoc                |

---

### 7.2 Compute & Library Audit

PoC 阶段不需要本地模型训练。

项目计算需求主要集中在：

* API calls；
* vector retrieval。

这些任务可以在标准开发机上运行。

如果需要 GPU，可以使用：

* Google Colab；
* university clusters。

项目关键依赖包括：

* Vue Flow；
* FastAPI；
* LangGraph；
* ChromaDB。

这些依赖具有较成熟的社区支持和维护情况，因此兼容性风险较低。

---

### 7.3 Risk Assessment & Metrics

项目基于 Pre-Mortem SPOF analysis，并参考 RAND Report，识别出四类关键风险。

---

#### 7.3.1 External LLM API Unavailability

风险说明：

外部 LLM API 可能不可用，影响 Agent 的可用性。

缓解措施：

* multi-model hot-swap；
* Strategy Pattern；
* exponential backoff。

---

#### 7.3.2 ChromaDB Index Corruption

风险说明：

ChromaDB 索引损坏可能影响 RAG pipeline 的可用性。

缓解措施：

* transactional writes；
* startup integrity checks；
* automatic rebuild from SQLite。

---

#### 7.3.3 Node–Index Sync Failure

风险说明：

节点内容和向量索引可能不同步，导致上下文漂移。

缓解措施：

* hash-based consistency check；
* forced re-indexing。

---

#### 7.3.4 LangGraph State Object Bloat

风险说明：

LangGraph state object 可能随着项目规模增长而变得过大，影响响应延迟。

缓解措施：

* 2000-token RAG cap；
* summary compression。

---

### 7.4 Success Metrics

项目成功指标包括 AI effectiveness、system quality 和 user experience 三个方面。

| Metric                         | Target / Purpose                                         |
| ------------------------------ | -------------------------------------------------------- |
| Context Relevance Gain         | cosine similarity delta > 0.1，用于验证 RAG-based memory 的可行性 |
| Authorship Boundary Compliance | ≥ 90%，用于验证受限 Agent 设计是否有效                                |
| Index Sync Latency             | 用于确认节点更新后索引同步是否及时                                        |
| End-to-End Latency             | 用于确认系统在真实负载下的响应性                                         |
| Perceived Assistance Quality   | 5-point scale，target mean ≥ 3.5                          |

系统不需要外部训练数据，所有上下文来自用户导入内容。

系统可以在标准开发硬件上运行，因此 Data Void 和 compute access 不构成主要项目风险。

---

### 7.5 Team Roles & Responsibilities

| Role                     | No. | Responsibilities                                            |
| ------------------------ | --: | ----------------------------------------------------------- |
| Project lead / architect |   1 | System architecture; sprint planning; integration oversight |
| Frontend developers      |   3 | Electron shell; node editor; export UI                      |
| Backend developers       |   2 | FastAPI service layer; LangGraph agent orchestration        |
| RAG / AI engineers       |   2 | LangChain pipeline; ChromaDB indexing; prompt engineering   |
| QA / DevOps              |   1 | CI/CD; automated testing; security testing                  |
| UX / documentation       |   1 | UI/UX design; user testing; report writing                  |

---

## 8. Project Summary

OC Creative Assistant System 是一个面向 OC 创作者的轻量级 AI 辅助创作系统。项目通过节点式工作空间组织碎片化灵感，通过 RAG 机制将 Agent 建议建立在已有世界观内容之上，并通过受限 Agent 提供问题、摘要和结构化建议。

系统的核心定位不是让 AI 直接创作完整文本，而是让 AI 在明确边界内辅助创作者进行思考、整理和规划。PoC 阶段将重点验证节点式创作流程、RAG 记忆机制和受限 Agent 设计在 OC 创作场景中的可行性。
