# Pinia Stores

跨路由共享状态（first_revision 决策 6）。单画布内的细粒度操作仍由 `composables/` 负责。

| Store | 职责 | 引入阶段 |
| --- | --- | --- |
| `useLibraryStore` | 项目列表 CRUD | 阶段 2 |
| `useProjectStore` | 当前 project 元数据（name/description/三个 graph_id/最新 seed） | 阶段 2 |
| `useGraphStore` | 当前打开的 sub-graph（nodes/edges/选中状态） | 阶段 3 |
| `useChatStore` | 当前会话消息流 + staging 列表 + SSE 状态 | 阶段 4 |
