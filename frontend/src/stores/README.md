# Pinia Stores

Cross-route shared state (first_revision decision 6). Fine-grained operations within a single canvas are still handled by `composables/`.

| Store | Responsibility | Introduced in |
| --- | --- | --- |
| `useLibraryStore` | Project list CRUD | Phase 2 |
| `useProjectStore` | Current project metadata (name/description/three graph_ids/latest seed) | Phase 2 |
| `useGraphStore` | Currently open sub-graph (nodes/edges/selection state) | Phase 3 |
| `useChatStore` | Current session message stream + staging list + SSE state | Phase 4 |
