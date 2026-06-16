# Exam-AI: Batch 2 Feature Design

## Context

Exam-AI MCP Server currently has 7 tools for exam review planning. Topics carry `attributes` and `source` fields (added in Batch 1). This design adds three capabilities: review document generation, practice history tracking, and question bank display.

## Decisions

- **generate_review_doc output**: Returns Markdown text; AI (Hermes) writes the file. Tool does not accept file paths.
- **practice_history granularity**: Minimal — `{topic_id, date, result}` only. No `question` field.
- **Question bank extraction**: AI extracts during `sync_topics` into `attributes.examples` / `attributes.homework_refs`. No regex extraction in tools. Sourcing rules: prioritize textbook; web search allowed but must confirm with user and mark "(来源: 网络搜索)"; never fabricate from model knowledge.
- **Implementation order**: Two commits — Commit 1 covers items 1+2+3; Commit 2 covers item 4 (review_doc enhancement).

---

## 1. practice_history

### Model change

```python
class PracticeRecord(BaseModel):
    topic_id: str
    date: str       # ISO format: "2026-06-16"
    result: Literal["mastered", "learning", "weak"]

class ReviewState(BaseModel):
    # ... existing fields ...
    practice_history: list[PracticeRecord] = Field(default_factory=list)
```

### Behavior change

- `record_answer` appends a `PracticeRecord(topic_id, date.today().isoformat(), result)` automatically after each call.
- `tested_topic_ids` remains — it tracks "which topics have been tested" for diagnostic flow; `practice_history` is the full chronological record.
- Backward compatible: old `state.json` without `practice_history` gets an empty list via Pydantic defaults.

---

## 2. generate_review_doc

### Tool signature

```python
@mcp.tool()
def generate_review_doc(
    sort_by: Literal["chapter", "learning_order"] = "chapter"
) -> str:
```

### Output format (Markdown)

```markdown
# 复习手册 — 2026-06-16

## 第3章 线性回归 [A] 🔴 weak

> 线性回归是研究变量间线性关系的统计方法...（source excerpt）

**公式**: β̂ = (X'X)⁻¹X'y
**易错**: R²高≠模型好, 多重共线性

**练习记录**: 6/15 weak, 6/16 weak

---

## 第1章 统计基础 [B] ⚪ unknown

(无 source 原文)

**公式**: (无)
**易错**: (无)

**练习记录**: (未测试)
```

### Internal logic

1. Group by `sort_by`: `chapter` → group by `topic.chapter`; `learning_order` → flat list following `state.learning_order`.
2. For each topic: name + level badge + status emoji + source (if any) + attributes expansion + practice_history filtered to this topic.
3. Status emoji: 🔴 weak / 🟡 learning / 🟢 mastered / ⚪ unknown.
4. Returns Markdown string. No file path parameter.

### Files to modify

- `exam_review/models.py` — add `PracticeRecord`, add `practice_history` to `ReviewState`
- `exam_review/server.py` — add `generate_review_doc` tool (7→8), update `record_answer` to append history, update instructions
- `exam_review/planner.py` — add `_render_review_doc` helper function (keeps server.py thin)
- `test_all.py` — test `PracticeRecord`, test `record_answer` appends history, test `generate_review_doc`

---

## 3. Question bank helpers

### 3a. sync_topics docstring update

Add recommended `attributes` keys to the docstring:

```
Recommended attributes keys:
  "formulas"      — core formulas
  "definitions"  — key definitions
  "pitfalls"      — common misconceptions
  "examples"      — example problems. Prioritize textbook "例"/"例题" markers.
                    If textbook lacks examples, AI may call web_search for supplementary
                    problems, but MUST confirm with the user and mark each item with
                    "(来源: 网络搜索)". NEVER fabricate from model knowledge.
  "homework_refs" — homework/exercise references. Same sourcing rules as examples:
                    textbook first, web_search with confirmation + attribution second,
                    never fabricated.
```

This is advisory only — no hard constraint on key names.

### 3b. get_question_bank tool

```python
@mcp.tool()
def get_question_bank(
    topic_ids: list[str] | None = None
) -> str:
```

### Logic

1. Filter topics: if `topic_ids` provided, only those; otherwise all topics.
2. For each topic, extract `attributes.examples` and `attributes.homework_refs`.
3. Only include topics that have at least one of these keys with non-empty lists.
4. Sort by chapter/learning_order.
5. Return JSON with topic details and their examples/homework refs.

### Return example

```json
{
  "topics_with_examples": [
    {
      "topic_id": "linear_regression",
      "name": "线性回归",
      "chapter": "第3章",
      "examples": ["例3.1: 已知...求回归方程"],
      "homework_refs": ["习题3.2", "习题3.5"]
    }
  ],
  "total_topics_with_examples": 1
}
```

### Files to modify

- `exam_review/server.py` — add `get_question_bank` tool (8→9), update `sync_topics` docstring, update instructions

---

## 4. generate_review_doc enhancement (Commit 2)

After items 1-3 are in place, `generate_review_doc` output expands to include:

- **例题** from `attributes.examples`
- **作业建议** from `attributes.homework_refs`

This is purely a template change inside `_render_review_doc` — no new tools or models needed.

```markdown
## 第3章 线性回归 [A] 🔴 weak

> 线性回归是研究变量间线性关系的统计方法...

**公式**: β̂ = (X'X)⁻¹X'y
**易错**: R²高≠模型好, 多重共线性

**例题**: 例3.1 已知...求回归方程
**作业**: 习题3.2, 习题3.5

**练习记录**: 6/15 weak → 6/16 weak
```

---

## Tool count summary

| Phase | Tool count | New tools |
|-------|-----------|------------|
| Batch 1 (done) | 7 | patch_topic |
| Commit 1 of Batch 2 | 9 | generate_review_doc, get_question_bank |
| Commit 2 of Batch 2 | 9 | (no new tools, enhance generate_review_doc) |

## Verification

1. `python test_all.py` — all test sections pass
2. `record_answer` called twice → `practice_history` has 2 entries with correct dates
3. `generate_review_doc(sort_by="chapter")` returns valid Markdown with status emoji and practice history
4. `generate_review_doc(sort_by="learning_order")` returns topics in learning order
5. `get_question_bank()` returns only topics with examples/homework_refs
6. `get_question_bank(topic_ids=["lr"])` filters correctly
7. Old `state.json` without `practice_history` loads without error (backward compat)