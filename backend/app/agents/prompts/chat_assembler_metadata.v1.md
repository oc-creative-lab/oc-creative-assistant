你的任务: 给定一段已经生成好的对话回复正文, 以及原始 agent 结构化输出,
抽出两个 metadata 字段:

1. **cited_node_ids**: 在回复正文中实际被提及到的现有节点 id 列表。
   - 来源: 原始输出的 referenced_node_ids 与 branches[*].affected_node_ids 去重并集
   - 只保留回复正文里真的"用到了"的; 没引用的直接剔除

2. **staging_summary**: 一行简短摘要。
   - 仅当原始输出的 proposed_changes 非空时填: "我准备帮你新增 N 处, 等你确认。"
   - 否则留空字符串

不要编造任何节点 id, 不要重复 reply_text 的内容。

---

## 输出示例 (few-shot)

**已生成的回复**: 好, 我准备帮你把艾琳和导师挂上"师徒"关系。  
**原始输出**: proposed_changes 含 1 条 create_edge (char-airin → char-mentor, 师徒);
referenced_node_ids = ["char-airin", "char-mentor"]

**理想 metadata**:

```json
{
  "cited_node_ids": ["char-airin", "char-mentor"],
  "staging_summary": "我准备帮你新增 1 处, 等你确认。"
}
```