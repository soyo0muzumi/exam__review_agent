# Exam-AI: v2 Phase B Design — Source Material Quality

## Context

Phase A (v2.0.0, 12 tools) is complete. Current architecture treats all topics as a flat merged list with no origin tracking — when a user syncs topics from multiple textbooks or notes, the system cannot distinguish "this concept came from source A" vs "this came from source B."

Phase B adds source material awareness: tracking which source documents each topic comes from (with dedup), and detecting topics that may be missing from the extracted material.

## Scope

**In scope:**
- `Topic.material_sources: list[str]` — track which source materials a topic appears in
- `sync_topics(topics, material_id)` — **required** parameter to tag/source-deduplicate topics
- `detect_knowledge_gaps(expected_topics)` — compare existing topics against AI-provided standard syllabus
- Tests for all new/modified functions
- MCP instructions update (new tool + workflow guidance)
- README update (13 tools, new tool row)

**Explicitly out of scope (Phase C):**
- Learning loop (explain → test → re-test)
- Adaptive planning
- Progress visualization
- Automated knowledge graph generation

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `material_id` vs `material_sources` | `material_sources: list[str]` on Topic | Multiple sources per topic; append-only with dedup |
| `material_id` required vs optional | **Required** — always tag topic origin | User confirmed; prevents untracked topics |
| `detect_knowledge_gaps` return type | JSON | AI provides expected list, tool does structured comparison |
| Gap detection approach | AI provides reference set, tool diffs | Avoids per-subject knowledge graph maintenance; LLM is the oracle |
| Old state compatibility | `material_sources` defaults to `[]` on load | New field is optional in Pydantic model; no migration needed |
| Source identity type | `str` (free-form label) | Flexible — "同济高数第七版" or "MIT OCW Notes"; user/AI chooses naming convention |

## Architecture

### Files Modified (5)

| File | Changes |
|------|---------|
| `exam_review/models.py` | Add `material_sources` to Topic |
| `exam_review/server.py` | Modify sync_topics (required material_id). Add 1 new tool: detect_knowledge_gaps. Update instructions. |
| `exam_review/diagnostic.py` | Add detect_knowledge_gaps (pure logic, separated from server) |
| `test_all.py` | Tests for new functions |
| `README.md` | Update tool count (12→13), add detect_knowledge_gaps row, changelog |

### Files Unchanged (6)

`state.py`, `scorer.py`, `structure.py`, `planner.py`, `parser.py`, `pyproject.toml` — no changes needed.

### Data Flow

```
parse_material(text_A) → AI identifies topics from A
  → sync_topics(topics_A, material_id="textbook_A")
parse_material(text_B) → AI identifies topics from B
  → sync_topics(topics_B, material_id="textbook_B")
  → existing topics get "textbook_B" appended to material_sources (deduped)

detect_knowledge_gaps(expected_topics)
  → AI provides standard syllabus from LLM knowledge
  → diffs against existing topic names
  → returns missing + partial + present breakdown
  → AI decides whether to fill gaps via sync_topics
```

## Detailed Changes

### models.py — Topic model

```python
class Topic(BaseModel):
    id: str
    name: str
    level: Literal["A", "B", "C"]
    importance: float = Field(ge=0.0, le=1.0)
    chapter: str = ""
    status: Literal["unknown", "mastered", "learning", "weak"] = "unknown"
    depends_on: list[str] = Field(default_factory=list)
    attributes: dict[str, list[str]] = Field(default_factory=dict)
    source: str = ""
    material_sources: list[str] = Field(default_factory=list)  # NEW
```

NOTES:
- Default `[]` ensures old state loads without errors
- Append-only: when sync_topics is called with material_id, the ID is added to material_sources if not already present
- No dedup is needed across re-syncs (the "if not already present" check prevents duplicates per material_id)

### server.py — sync_topics modification

**Parameter change:**
- `material_id: str` — required, replaced the previous optional absence

**Behavior change:**
- For NEW topics: `material_sources = [material_id]`
- For EXISTING topics: if `material_id` not already in `material_sources`, append it
- All other behavior (importance scoring, topological sort, merge logic) unchanged

**Return value change:**
- Add `material_id` to the returned JSON so AI can confirm it was applied

### server.py — New tool: detect_knowledge_gaps

```python
@mcp.tool()
def detect_knowledge_gaps(expected_topics: list[dict]) -> str:
    """Detect gaps by comparing current topics against an expected topic list. AI provides the expected syllabus from LLM subject knowledge; tool returns structured diff.

    Args:
        expected_topics: List of expected topic dicts, each with "name" (required), optional "level" (A/B/C) and "chapter".

    Returns JSON with missing, partial, present breakdown.
    Pure computation — no AI judgment.
    """
```

Logic (`diagnostic.py`):

1. Build `set(current_topic_names)` from state.topics
2. For each expected topic:
   - Name not found → add to `missing` list (with name, level, chapter from expected)
   - Name found but missing some expected attributes → add to `partial`
     - Check: check if topic has non-empty values for formulas, definitions, methods, distinctions, pitfalls
     - "Expected attributes" are inferred from what similar topics in state typically have, OR from expected item's own hints
   - Name found with reasonable attributes → count in `present`
3. Return structured JSON

Edge cases:
- No topics in state → `{"missing": expected_topics, "partial": [], "present": 0}`
- Empty expected_topics → `{"missing": [], "partial": [], "present": N}`
- Name matching: case-insensitive exact match (by name field). "泰勒展开" and "泰勒公式" are different topics; AI should normalize names before calling detect_knowledge_gaps
- If a topic name in state partially matches (substring), note it in `partial` with a `"suggestion"` field

### Output Format

**detect_knowledge_gaps return:**

```json
{
  "missing": [
    {"name": "泰勒展开", "level": "A", "chapter": "第3章"}
  ],
  "partial": [
    {
      "name": "梯度",
      "existing_attrs": ["formulas"],
      "missing_attrs": ["definitions", "methods"],
      "suggestion": "梯度缺少定义和方法描述"
    }
  ],
  "present": 35,
  "total_expected": 37
}
```

## Assumptions and Risks

| Risk | Mitigation |
|------|------------|
| `material_id` required breaks existing AI workflows | Update MCP instructions + README; AI adapts by providing a default material_id |
| Old state without material_sources loads but topics show no source origin | Cooperative — AI can prompt user to re-sync topics with material_id, or add material_id via patch_topic if needed |

## Verification

1. `python test_all.py` — all tests pass
2. `sync_topics(topics, material_id="教材A")` tags new topics with `material_sources=["教材A"]`
3. `sync_topics(topics, material_id="教材B")` appends "教材B" to existing topics' `material_sources`, tags new topics with `["教材B"]`
4. `detect_knowledge_gaps([{name: "新知识点"}])` returns it in `missing` list
5. Old state.json (v2.0.0, no material_sources) loads with `material_sources=[]`
