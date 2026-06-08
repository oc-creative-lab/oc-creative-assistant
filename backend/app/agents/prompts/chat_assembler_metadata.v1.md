Your task: given an already-generated reply body, plus the original structured agent output,
extract two metadata fields:

1. **cited_node_ids**: the IDs of all context nodes you actually referenced when writing the reply (the nodes provided in the retrieved context). If none were used, return an empty list.
   - Source: the deduplicated union of the original output's referenced_node_ids and branches[*].affected_node_ids — these are the nodes provided in the retrieved context.
   - Include every id that informed or is mentioned in the reply body; drop only ids that had nothing to do with the reply.
   - Never fabricate an id that is not present in the original output.

2. **staging_summary**: a one-line short summary.
   - Fill it only when the original output's proposed_changes is non-empty: "I've added N items to the canvas — discard any you don't want."
   - Otherwise leave it as an empty string

Do not fabricate any node id, and do not repeat the content of reply_text.

---

## Output Example (few-shot)

**Generated reply**: Sure, I'm ready to link Erin and her mentor with a "mentorship" relation.  
**Original output**: proposed_changes contains 1 create_edge (char-airin → char-mentor, mentorship);
referenced_node_ids = ["char-airin", "char-mentor"]

**Ideal metadata**:

```json
{
  "cited_node_ids": ["char-airin", "char-mentor"],
  "staging_summary": "I've added 1 item to the canvas — discard it if you don't want it."
}
```
