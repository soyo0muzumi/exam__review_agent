# Batch 2 Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add practice history tracking, review document generation, and question bank display to the exam-review MCP server.

**Architecture:** Three new capabilities built on existing patterns. `PracticeRecord` is a new Pydantic model added to `ReviewState`. `generate_review_doc` and `get_question_bank` are new MCP tool functions. The review document renderer lives in `planner.py` alongside the existing plan generator. `record_answer` gains an auto-append to `practice_history`. `sync_topics` docstring gets sourcing guidelines. Two commits: Commit 1 = all three features; Commit 2 = review_doc enhancement (examples/homework_refs in output).

**Tech Stack:** Python 3.13, Pydantic v2, MCP SDK, existing test_all.py integration test pattern.

---

## File Structure

| File | Responsibility | Change type |
|------|---------------|-------------|
| `exam_review/models.py` | Add `PracticeRecord`, add `practice_history` field to `ReviewState` | Modify |
| `exam_review/server.py` | Add `generate_review_doc` tool, add `get_question_bank` tool, update `record_answer`, update `sync_topics` docstring, update `instructions` | Modify |
| `exam_review/planner.py` | Add `_render_review_doc()` helper, add `render_review_doc()` public function | Modify |
| `test_all.py` | Add tests for `PracticeRecord`, `record_answer` history append, `generate_review_doc`, `get_question_bank` | Modify |
| `README.md` | Update tool tables (EN/ZH) from 7→9 tools | Modify |

---

## Commit 1: practice_history + generate_review_doc + get_question_bank

### Task 1: Add PracticeRecord model

**Files:**
- Modify: `exam_review/models.py`
- Test: `test_all.py`

- [ ] **Step 1: Add `PracticeRecord` to models.py**

Add after the `Topic` class (around line 31):

```python
class PracticeRecord(BaseModel):
    topic_id: str
    date: str       # ISO format: "2026-06-16"
    result: Literal["mastered", "learning", "weak"]
```

Add `practice_history` field to `ReviewState`:

```python
class ReviewState(BaseModel):
    version: int = 2
    topic_version: int = 0
    exam_date: str = ""
    daily_hours: float = 3.0
    mode: str = "normal"
    chapter_weights: dict[str, float] = Field(default_factory=dict)
    chapters: list[ChapterRef] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    learning_order: list[str] = Field(default_factory=list)
    tested_topic_ids: list[str] = Field(default_factory=list)
    practice_history: list[PracticeRecord] = Field(default_factory=list)  # NEW
```

Add `PracticeRecord` to the imports in `server.py` — currently line 22 imports `Topic` and `ReviewState`:

```python
from .models import (
    Topic,
    ReviewState,
    PracticeRecord,
)
```

- [ ] **Step 2: Add test for PracticeRecord model**

In `test_all.py`, Test 1, after the existing `topic_with_attrs` assertions, add:

```python
from exam_review.models import PracticeRecord
pr = PracticeRecord(topic_id="lr", date="2026-06-16", result="weak")
assert pr.topic_id == "lr"
assert pr.date == "2026-06-16"
assert pr.result == "weak"
state_with_history = ReviewState(exam_date="2026-07-15", daily_hours=3, mode="normal")
assert state_with_history.practice_history == []  # default empty
print("  PracticeRecord OK")
```

- [ ] **Step 3: Run tests to verify model changes**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All existing tests pass (backward compat — old state.json would load with `practice_history=[]`).

- [ ] **Step 4: Commit**

```bash
git add exam_review/models.py exam_review/server.py test_all.py
git commit -m "feat: add PracticeRecord model and practice_history field to ReviewState"
```

---

### Task 2: Auto-append practice history in record_answer

**Files:**
- Modify: `exam_review/server.py` (record_answer function)
- Test: `test_all.py`

- [ ] **Step 1: Add history append to record_answer**

In `server.py`, inside `record_answer`, after the line `topic.status = result` (around line 261) and before `save_state(state)`, add:

```python
from datetime import date as _date

# ... inside record_answer function, after topic.status = result:
state.practice_history.append(
    PracticeRecord(topic_id=topic_id, date=_date.today().isoformat(), result=result)
)
```

Note: `date` is already imported at the top of server.py as `from datetime import date`. Verify this import exists; if so, use `date.today().isoformat()` instead of `_date`. Check the current imports.

Looking at server.py line 17: `from datetime import date` — so use `date.today().isoformat()`.

Add the append after `if topic_id not in state.tested_topic_ids:` block:

```python
topic.status = result
if topic_id not in state.tested_topic_ids:
    state.tested_topic_ids.append(topic_id)
state.practice_history.append(
    PracticeRecord(topic_id=topic_id, date=date.today().isoformat(), result=result)
)
save_state(state)
```

- [ ] **Step 2: Add test for history append in test_all.py**

In Test 8, after the first `record_answer` call (around line 312-318), add:

```python
# Verify practice history was appended
state_check = load_state()
assert len(state_check.practice_history) >= 1
assert state_check.practice_history[0].topic_id == next_topic["topic_id"]
assert state_check.practice_history[0].result == "weak"
print("  practice_history append OK")
```

We need to import `load_state` in the test. Currently `load_state` is not imported in the server tools test section. Add it to the imports at the start of test section 8:

```python
from exam_review.state import load_state
```

- [ ] **Step 3: Run tests**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All tests pass, including the new `practice_history append OK` assertion.

- [ ] **Step 4: Commit**

```bash
git add exam_review/server.py test_all.py
git commit -m "feat: auto-append PracticeRecord in record_answer"
```

---

### Task 3: Add generate_review_doc tool

**Files:**
- Modify: `exam_review/planner.py` (add render function)
- Modify: `exam_review/server.py` (add tool)
- Test: `test_all.py`

- [ ] **Step 1: Add render_review_doc to planner.py**

Add at the end of `planner.py`:

```python
def render_review_doc(
    topics: list[Topic],
    practice_history: list,
    learning_order: list[str] | None = None,
    sort_by: str = "chapter",
) -> str:
    """Render a Markdown review document from current state."""
    status_emoji = {
        "weak": "🔴",
        "learning": "🟡",
        "mastered": "🟢",
        "unknown": "⚪",
    }

    # Build practice history index: topic_id -> list of (date, result)
    history_by_topic: dict[str, list[tuple[str, str]]] = {}
    for rec in practice_history:
        history_by_topic.setdefault(rec.topic_id, []).append((rec.date, rec.result))

    # Group topics
    if sort_by == "chapter":
        # Group by chapter, empty chapter last
        chapters: dict[str, list[Topic]] = {}
        no_chapter: list[Topic] = []
        for t in topics:
            if t.chapter:
                chapters.setdefault(t.chapter, []).append(t)
            else:
                no_chapter.append(t)
        # Sort chapter names, then group topics within each chapter by importance
        sorted_groups: list[tuple[str, list[Topic]]] = []
        for ch_name in sorted(chapters.keys()):
            sorted_groups.append((ch_name, sorted(chapters[ch_name], key=lambda t: t.importance, reverse=True)))
        if no_chapter:
            sorted_groups.append(("未分类", sorted(no_chapter, key=lambda t: t.importance, reverse=True)))
    else:
        # Sort by learning_order
        order_map = {tid: i for i, tid in enumerate(learning_order or [])}
        sorted_topics = sorted(topics, key=lambda t: order_map.get(t.id, 999))
        sorted_groups = [("学习顺序", sorted_topics)]

    today = date.today().isoformat()
    lines = [f"# 复习手册 — {today}", ""]

    for group_name, group_topics in sorted_groups:
        for t in group_topics:
            emoji = status_emoji.get(t.status, "⚪")
            lines.append(f"## {group_name} {t.name} [{t.level}] {emoji} {t.status}")
            lines.append("")

            # Source
            if t.source:
                lines.append(f"> {t.source}")
                lines.append("")
            else:
                lines.append("（无 source 原文）")
                lines.append("")

            # Attributes
            if t.attributes:
                for key, vals in t.attributes.items():
                    # Map common keys to Chinese labels
                    key_labels = {
                        "formulas": "公式",
                        "definitions": "定义",
                        "pitfalls": "易错",
                        "examples": "例题",
                        "homework_refs": "作业",
                    }
                    label = key_labels.get(key, key)
                    lines.append(f"**{label}**: {', '.join(vals)}")
            else:
                lines.append("（无属性）")
            lines.append("")

            # Practice history
            recs = history_by_topic.get(t.id, [])
            if recs:
                history_str = ", ".join(f"{d} {r}" for d, r in recs)
                lines.append(f"**练习记录**: {history_str}")
            else:
                lines.append("**练习记录**: （未测试）")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Import and add generate_review_doc tool in server.py**

Add import at top of server.py:

```python
from .planner import generate_plan as _generate_plan
from .planner import render_review_doc as _render_review_doc
```

Add the tool function after `generate_plan` (before the Entry Point section):

```python
# ─── Tool 7: generate_review_doc ─────────────────────────────────


@mcp.tool()
def generate_review_doc(
    sort_by: Literal["chapter", "learning_order"] = "chapter",
) -> str:
    """Generate a Markdown review document organized by chapter or learning order. Returns Markdown text for AI to present or save.

    Args:
        sort_by: "chapter" groups topics by chapter, "learning_order" follows topological sort order.
    """
    state = load_state()
    if state is None or not state.topics:
        return json.dumps({"error": "没有知识点。请先完成 setup + sync_topics。"})

    md = _render_review_doc(
        topics=state.topics,
        practice_history=state.practice_history,
        learning_order=state.learning_order,
        sort_by=sort_by,
    )
    return md
```

- [ ] **Step 3: Update server.py instructions and docstring header**

Change the module docstring from `7 tools` to `9 tools` and add `generate_review_doc` and `get_question_bank` to the list. Update the `instructions` string to add the new tools to the workflow.

In the module docstring (lines 1-10), update:

```python
"""MCP Server for exam review — 9 tools, minimal state, pure computation.

Tools:
  1. setup_review    — Initialize/reset state (exam date, hours, mode)
  2. parse_material  — Split text into chapter-based chunks (LLM extracts text first via pdf-mcp)
  3. sync_topics     — AI submits all knowledge points at once; tool scores + sorts
  4. record_answer   — Record diagnostic answer for a topic
  5. get_next_topic  — Get next untested A-level topic
  5.5 patch_topic    — Incrementally update a single topic
  6. generate_plan   — Compute priority scores and daily schedule
  7. generate_review_doc — Generate Markdown review document
  8. get_question_bank — Return topics that have examples or homework references
"""
```

In the `instructions` string, add after the `Additional tools:` section:

```
  - generate_review_doc(sort_by?) → Markdown review document (chapter or learning_order)
  - get_question_bank(topic_ids?) → Topics with examples/homework_refs
```

- [ ] **Step 4: Add test for generate_review_doc**

In `test_all.py`, add after the `generate_plan` test (around end of Test 8 section, before the `# Cleanup` line):

```python
# Test generate_review_doc
from exam_review.server import generate_review_doc

doc_result = generate_review_doc(sort_by="chapter")
assert "复习手册" in doc_result
assert "线性回归" in doc_result
assert "🔴" in doc_result  # weak emoji
print("  generate_review_doc (chapter) OK")

doc_lo = generate_review_doc(sort_by="learning_order")
assert "练习记录" in doc_lo
print("  generate_review_doc (learning_order) OK")
```

- [ ] **Step 5: Run tests**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All tests pass, including `generate_review_doc (chapter) OK` and `generate_review_doc (learning_order) OK`.

- [ ] **Step 6: Commit**

```bash
git add exam_review/planner.py exam_review/server.py test_all.py
git commit -m "feat: add generate_review_doc tool with Markdown output"
```

---

### Task 4: Add get_question_bank tool and update sync_topics docstring

**Files:**
- Modify: `exam_review/server.py` (add tool, update docstring)
- Test: `test_all.py`

- [ ] **Step 1: Add get_question_bank tool in server.py**

Add after the `generate_review_doc` tool:

```python
# ─── Tool 8: get_question_bank ────────────────────────────────────


@mcp.tool()
def get_question_bank(
    topic_ids: list[str] | None = None,
) -> str:
    """Return topics that have examples or homework references in their attributes. Structured JSON for AI to reference when generating questions.

    Args:
        topic_ids: Optional list of topic IDs to filter. If None, returns all topics with examples/homework_refs.
    """
    state = load_state()
    if state is None or not state.topics:
        return json.dumps({"error": "没有知识点。请先完成 setup + sync_topics。"})

    topics = state.topics
    if topic_ids is not None:
        id_set = set(topic_ids)
        topics = [t for t in topics if t.id in id_set]

    result_topics = []
    for t in topics:
        examples = t.attributes.get("examples", [])
        homework = t.attributes.get("homework_refs", [])
        if examples or homework:
            result_topics.append({
                "topic_id": t.id,
                "name": t.name,
                "chapter": t.chapter,
                "examples": examples,
                "homework_refs": homework,
            })

    return json.dumps(
        {
            "topics_with_examples": result_topics,
            "total_topics_with_examples": len(result_topics),
        },
        ensure_ascii=False,
        indent=2,
    )
```

- [ ] **Step 2: Update sync_topics docstring with sourcing guidelines**

In the `sync_topics` docstring (around line 154-157), replace the `Args` section. Current:

```python
    Args:
        topics: List of topic dicts. Each must have "name" and "level" (A/B/C). Optional: "chapter", "depends_on" (list of other topic names), "attributes" (dict of semantic-type→list[str], e.g. {"formulas": ["y=wx+b"], "pitfalls": ["过拟合"]}), "source" (relevant textbook excerpt for this topic).
```

Replace with:

```python
    Args:
        topics: List of topic dicts. Each must have "name" and "level" (A/B/C). Optional: "chapter", "depends_on" (list of other topic names), "attributes" (dict of semantic-type→list[str]), "source" (relevant textbook excerpt for this topic).
            Recommended attributes keys:
              "formulas"      — core formulas
              "definitions"   — key definitions
              "pitfalls"      — common misconceptions
              "examples"      — example problems. Prioritize textbook "例"/"例题" markers.
                                If textbook lacks examples, AI may call web_search for supplementary
                                problems, but MUST confirm with the user and mark each item with
                                "(来源: 网络搜索)". NEVER fabricate from model knowledge.
              "homework_refs" — homework/exercise references. Same sourcing rules as examples:
                                textbook first, web_search with confirmation + attribution second,
                                never fabricated.
```

- [ ] **Step 3: Add test for get_question_bank**

In `test_all.py`, add after the `generate_review_doc` tests:

```python
# Test get_question_bank
from exam_review.server import get_question_bank

# No topics have examples/homework_refs yet (we didn't add them)
qb_empty = json.loads(get_question_bank())
assert qb_empty["total_topics_with_examples"] == 0
print("  get_question_bank (empty) OK")

# Patch a topic to add examples
patch_topic(topic_id=lr_id, attributes_merge={"examples": ["例3.1: 求回归方程"], "homework_refs": ["习题3.2"]})
qb_result = json.loads(get_question_bank())
assert qb_result["total_topics_with_examples"] == 1
assert qb_result["topics_with_examples"][0]["topic_id"] == lr_id
assert "习题3.2" in qb_result["topics_with_examples"][0]["homework_refs"]
print("  get_question_bank (with data) OK")

# Filter by topic_ids
qb_filtered = json.loads(get_question_bank(topic_ids=[lr_id]))
assert qb_filtered["total_topics_with_examples"] == 1
qb_filtered_empty = json.loads(get_question_bank(topic_ids=["nonexistent_id"]))
assert qb_filtered_empty["total_topics_with_examples"] == 0
print("  get_question_bank (filter) OK")
```

- [ ] **Step 4: Run tests**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All tests pass.

- [ ] **Step 5: Update README.md**

In the English section:
- Change `7 tools` → `9 tools` (appears in header, Hermes config description, and Tools section header)
- Change `## Tools (7)` → `## Tools (9)`
- Add two rows to the tool table after `generate_plan`:

```
| `generate_review_doc` | sort_by? (chapter/learning_order) | Markdown review document | Generate review document organized by chapter or learning order |
| `get_question_bank` | topic_ids? | JSON with topics that have examples/homework_refs | Show available examples and homework references |
```

- Add to workflow section after step 5:

```
   (Optional: generate_review_doc → Markdown review document for human review)
   (Optional: get_question_bank → List topics with example problems for study)
```

In the Chinese section:
- Change `7 个工具` → `9 个工具`
- Change `## 工具 (7)` → `## 工具 (9)`
- Add two rows to the tool table:

```
| `generate_review_doc` | sort_by? (chapter/learning_order) | Markdown 复习文档 | 按章节或学习顺序生成复习手册 |
| `get_question_bank` | topic_ids? | 包含例题/作业的知识点 JSON | 展示可用的例题和作业题目 |
```

- Add to Chinese workflow after step 5:

```
   （可选：generate_review_doc → 生成 Markdown 复习文档供人阅读）
   （可选：get_question_bank → 列出有例题的知识点）
```

- [ ] **Step 6: Commit**

```bash
git add exam_review/server.py test_all.py README.md
git commit -m "feat: add get_question_bank tool, update sync_topics docstring with sourcing guidelines"
```

---

## Commit 2: review_doc enhancement (examples + homework in Markdown output)

### Task 5: Enhance generate_review_doc to include examples and homework

**Files:**
- Modify: `exam_review/planner.py` (`render_review_doc` function)
- Test: `test_all.py`

- [ ] **Step 1: Update render_review_doc template in planner.py**

The attribute rendering section currently has:

```python
if t.attributes:
    for key, vals in t.attributes.items():
        key_labels = {
            "formulas": "公式",
            "definitions": "定义",
            "pitfalls": "易错",
            "examples": "例题",
            "homework_refs": "作业",
        }
        label = key_labels.get(key, key)
        lines.append(f"**{label}**: {', '.join(vals)}")
```

This already renders `examples` as **例题** and `homework_refs` as **作业** — so the Markdown output already includes them if they exist in attributes. The only change needed is to verify the `key_labels` dict has both entries. It does. No code change needed in the template.

The enhancement is already complete because `render_review_doc` iterates over ALL `attributes` keys and the `key_labels` mapping already includes `examples` → `例题` and `homework_refs` → `作业`.

- [ ] **Step 2: Add a test that verifies examples/homework appear in review doc**

In `test_all.py`, after the `generate_review_doc` tests, add:

```python
# Verify examples and homework appear in review doc
doc_with_examples = generate_review_doc(sort_by="chapter")
# After patch_topic added examples, they should appear in the doc
assert "例题" in doc_with_examples or "例3.1" in doc_with_examples
print("  generate_review_doc (with examples) OK")
```

- [ ] **Step 3: Run tests**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add exam_review/planner.py test_all.py
git commit -m "feat: verify examples and homework_refs in review doc output"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Each spec item (practice_history, generate_review_doc, get_question_bank, sync_topics docstring, review_doc enhancement) maps to a task
- [x] **Placeholder scan**: No TBD, TODO, or "implement later" in any step
- [x] **Type consistency**: `PracticeRecord` is defined in models.py and imported in server.py; `render_review_doc` is defined in planner.py and imported in server.py; `get_question_bank` returns JSON string consistent with other tools
- [x] **Backward compat**: `practice_history` has `default_factory=list` so old state.json loads fine
- [x] **Import paths**: `PracticeRecord` imported from `.models`; `render_review_doc` imported from `.planner`; `date` already imported in server.py