Your task: given an already-generated reply body, plus the original structured agent output,
extract two metadata fields:

1. **cited_node_ids**: the list of existing node ids actually mentioned in the reply body.
   - Source: the deduplicated union of the original output's referenced_node_ids and branches[*].affected_node_ids
   - Keep only the ones the reply body really "used"; drop any that aren't referenced

2. **staging_summary**: a one-line short summary.
   - Fill it only when the original output's proposed_changes is non-empty: "I'm ready to add N items for you, pending your confirmation."
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
  "staging_summary": "I'm ready to add 1 item for you, pending your confirmation."
}
```
