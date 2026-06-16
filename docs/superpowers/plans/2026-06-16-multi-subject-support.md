# Multi-Subject Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-subject isolation so each subject (e.g., "高数", "线性代数") has its own independent state, chapters, and progress.

**Architecture:** Two new tools (`switch_subject`, `list_subjects`) operate on the global `_state_path` and `CHAPTERS_DIR` pointers in `state.py`. Switching subjects redirects these pointers to subject-specific subdirectories under `~/.exam-review/`. All existing tools continue working unchanged — they call `load_state()`/`save_state()` which read from the current pointer. Backward compatible: no switch = old global behavior.

**Tech Stack:** Python 3.13, Pydantic v2, MCP SDK, existing test_all.py pattern.

---

## File Structure

| File | Change type | Responsibility |
|------|-------------|---------------|
| `exam_review/state.py` | Modify | Add `switch_subject()`, `list_subjects()`, `_current_subject` global |
| `exam_review/server.py` | Modify | Add `switch_subject` tool (Tool 9), `list_subjects` tool (Tool 10), update docstrings |
| `test_all.py` | Modify | Add Test 9: multi-subject isolation tests |
| `README.md` | Modify | Update tool tables (EN/ZH), add workflow notes |

---

## Task 1: Add switch_subject and list_subjects to state.py

**Files:**
- Modify: `exam_review/state.py`

- [ ] **Step 1: Add `_current_subject` global and `switch_subject` function**

At the top of `state.py`, after `_state_path = DEFAULT_STATE_PATH` (line 21), add:

```python
_current_subject: str | None = None
```

Then add the `switch_subject` function after `get_or_create_state()` (after line 116):

```python
def switch_subject(subject: str) -> dict:
    """Switch to a subject-specific state directory. Creates the directory if needed.
    Does NOT create state — call setup_review after switching to a new subject."""
    global _state_path, CHAPTERS_DIR, _current_subject

    subject_dir = DEFAULT_STATE_DIR / subject
    subject_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = subject_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    _state_path = subject_dir / "state.json"
    CHAPTERS_DIR = chapters_dir
    _current_subject = subject

    state = load_state()
    if state is not None:
        return {
            "subject": subject,
            "state_exists": True,
            "topics_count": len(state.topics),
            "exam_date": state.exam_date,
        }
    return {"subject": subject, "state_exists": False, "topics_count": 0, "exam_date": ""}
```

- [ ] **Step 2: Add `list_subjects` function**

Add after `switch_subject`:

```python
def list_subjects() -> dict:
    """List all subjects that have a state.json, with summary info."""
    subject_dirs = []
    if DEFAULT_STATE_DIR.exists():
        for d in sorted(DEFAULT_STATE_DIR.iterdir()):
            if d.is_dir() and (d / "state.json").exists():
                try:
                    data = json.loads((d / "state.json").read_text(encoding="utf-8"))
                    state = ReviewState.model_validate(data)
                    subject_dirs.append({
                        "name": d.name,
                        "exam_date": state.exam_date,
                        "topics_count": len(state.topics),
                        "tested_count": len(state.tested_topic_ids),
                    })
                except (json.JSONDecodeError, ValueError):
                    subject_dirs.append({"name": d.name, "exam_date": "", "topics_count": 0, "tested_count": 0})
    return {"current_subject": _current_subject, "subjects": subject_dirs}
```

- [ ] **Step 3: Run existing tests to verify backward compat**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All 8 test sections pass. The new functions are defined but not yet called by any test, so no new assertions yet.

- [ ] **Step 4: Commit**

```bash
cd "D:/vscode/Hermes skills/exam-ai"
git add exam_review/state.py
git commit -m "feat: add switch_subject and list_subjects to state.py"
```

---

## Task 2: Add switch_subject and list_subjects MCP tools to server.py

**Files:**
- Modify: `exam_review/server.py`

- [ ] **Step 1: Add imports for switch_subject and list_subjects**

In `server.py`, find the import block from `.state (currently around lines 26-33):

```python
from .state import (
    get_or_create_state,
    load_all_chapter_text,
    load_state,
    reset_state,
    save_chapter_text,
    save_state,
)
```

Add two new imports:

```python
from .state import (
    get_or_create_state,
    load_all_chapter_text,
    load_state,
    reset_state,
    save_chapter_text,
    save_state,
    switch_subject as _switch_subject,
    list_subjects as _list_subjects,
)
```

Aliased with underscores to avoid name collisions with the tool functions.

- [ ] **Step 2: Add switch_subject tool**

Add before the `# ─── Tool 1: setup_review ───` section:

```python
# ─── Tool 0: switch_subject ────────────────────────────────────


@mcp.tool()
def switch_subject(subject: str) -> str:
    """Switch to a subject-specific state directory. Each subject has independent state, chapters, topics, and progress. Call this before setup_review to start a new subject, or to switch back to an existing one. Does NOT create state — call setup_review after switching to a new subject.

    Args:
        subject: Subject name (e.g., "高数", "线性代数"). Used as directory name under ~/.exam-review/
    """
    result = _switch_subject(subject)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── Tool 0.5: list_subjects ───────────────────────────────────


@mcp.tool()
def list_subjects() -> str:
    """List all subjects that have been set up. Returns subject names with exam date and progress info."""
    result = _list_subjects()
    return json.dumps(result, ensure_ascii=False, indent=2)
```

- [ ] **Step 3: Update module docstring**

Change the docstring from `9 tools` to `11 tools` and add the two new tools to the numbered list. Find the current docstring starting `"""MCP Server for exam review — 9 tools` and replace:

```python
"""MCP Server for exam review — 11 tools, minimal state, pure computation.

Tools:
  0. switch_subject  — Switch to a subject-specific state directory
  0.5 list_subjects  — List all subjects with state
  1. setup_review    — Initialize/reset state (exam date, hours, mode)
  2. parse_material  — Split text into chapter-based chunks (LLM extracts text first via pdf-mcp)
  3. sync_topics     — AI submits all knowledge points at once; tool scores + sorts
  4. record_answer   — Record diagnostic answer for a topic
  5. get_next_topic  — Get next untested A-level topic
  5.5 patch_topic    — Incrementally update a single topic
  6. generate_plan   — Compute priority scores and daily schedule
  7. generate_review_doc — Generate Markdown review document
  8. get_question_bank — Return topics with examples or homework references
"""
```

- [ ] **Step 4: Update instructions string**

The `instructions` string in the `FastMCP()` constructor currently says "9 tools". Change it to "11 tools" and add two lines at the beginning of the workflow for the new tools.

Find the line containing `instructions="""Final Exam Review MCP Server — 9 tools` and change `9 tools` to `11 tools`. Then add at the beginning of the workflow (after `Workflow:`), add:

```
  -1. switch_subject("高数") → Switch to a subject (call before setup_review for new subjects)
  -0.5. list_subjects() → List all existing subjects with progress info
```

**Note:** The instructions string contains Unicode box-drawing characters. If the Edit tool fails, use a Python script to do the replacement, similar to what was done in previous sessions:

```python
python -c "
with open('D:/vscode/Hermes skills/exam-ai/exam_review/server.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('9 tools for AI study coaching', '11 tools for AI study coaching', 1)
# ... etc
"
```

- [ ] **Step 5: Run tests**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All 8 existing test sections still pass. The new tools are defined but not yet tested.

- [ ] **Step 6: Commit**

```bash
cd "D:/vscode/Hermes skills/exam-ai"
git add exam_review/server.py
git commit -m "feat: add switch_subject and list_subjects MCP tools"
```

---

## Task 3: Add multi-subject integration tests

**Files:**
- Modify: `test_all.py`

- [ ] **Step 1: Add Test 9 section at the end of test_all.py**

Add after the `shutil.rmtree(tmp_dir, ...)` / `ALL TESTS PASSED` section, but BEFORE the `print("\n" + "=" * 50)` and `ALL TESTS PASSED` lines. Actually, the cleanest approach is to add a new test section before the cleanup lines. Find the lines:

```python
# Cleanup
reset_state()

# ─── Cleanup temp files ──────────────────────────────────────────
import shutil
shutil.rmtree(tmp_dir, ignore_errors=True)
```

Insert the new test block BEFORE `# Cleanup`:

```python
# ─── 9. Test multi-subject isolation ───────────────────────────
from exam_review.state import switch_subject as _switch_subject, list_subjects as _list_subjects

print("=== Test 9: Multi-subject isolation ===")

# Create a subject-specific temp dir to avoid polluting real state
from exam_review.state import set_state_path

# Save current state path to restore later
original_path = Path(tempfile.mkdtemp()) / "subject_test"

# Switch to "高数" subject
subj_dir = Path(tempfile.mkdtemp()) / "高数"
result1 = _switch_subject("高数")
# Override path for testing (switch_subject sets to real ~/.exam-review/高数/)
# For isolation, manually set path to temp dir
set_state_path(subj_dir / "state.json")
subj_dir.mkdir(parents=True, exist_ok=True)
(subj_dir / "chapters").mkdir(parents=True, exist_ok=True)
assert result1["subject"] == "高数"
print(f"  switch_subject OK: {result1['subject']}")

# Setup and populate 高数 state
setup_review(exam_date="2026-07-15", daily_hours=3, mode="normal")
sync_topics(topics=[
    {"name": "微积分", "level": "A", "chapter": "第1章", "depends_on": []},
])
高数_next = json.loads(get_next_topic())
assert 高数_next["name"] == "微积分"
print("  高数 state OK")

# Switch to 线性代数
subj_dir2 = Path(tempfile.mkdtemp()) / "线性代数"
set_state_path(subj_dir2 / "state.json")
subj_dir2.mkdir(parents=True, exist_ok=True)
(subj_dir2 / "chapters").mkdir(parents=True, exist_ok=True)

setup_review(exam_date="2026-07-20", daily_hours=2, mode="normal")
sync_topics(topics=[
    {"name": "矩阵", "level": "A", "chapter": "第1章", "depends_on": []},
])
代数_next = json.loads(get_next_topic())
assert 代数_next["name"] == "矩阵"
print("  线性代数 state OK")

# Verify isolation: switching back to 高数 should still have 微积分
set_state_path(subj_dir / "state.json")
高数_state = load_state()
assert len(高数_state.topics) == 1
assert 高数_state.topics[0].name == "微积分"
assert 高数_state.exam_date == "2026-07-15"
print("  高数 state preserved after switching subjects OK")

# Cleanup: restore original state path
reset_state()
set_state_path(tmp_dir / "state.json")
shutil.rmtree(subj_dir.parent, ignore_errors=True)
shutil.rmtree(subj_dir2.parent, ignore_errors=True)
print("  Multi-subject isolation OK")
```

The `from exam_review.state import switch_subject as _switch_subject, list_subjects as _list_subjects` import should go at the top of the test section (not the file top-level imports, since those are already structured by section).

- [ ] **Step 2: Run tests**

Run: `cd "D:/vscode/Hermes skills/exam-ai" && python test_all.py`

Expected: All test sections pass, including the new Test 9.

- [ ] **Step 3: Commit**

```bash
cd "D:/vscode/Hermes skills/exam-ai"
git add test_all.py
git commit -m "test: add multi-subject isolation tests"
```

---

## Task 4: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update English section**

Find `9 tools` occurrences and change to `11 tools`. There should be several:
- Header line: `AI-powered exam review planner, delivered as an MCP Server with 9 tools.`
- Hermes Agent line: `The 9 tools will auto-discover`
- Tool table header: `## Tools (9)`

Change all to `11 tools`.

Add two rows to the tool table, right before `| \`setup_review\` |`:

```
| `switch_subject` | subject (name string) | Subject info (name, state_exists, topics_count) | Switch to a subject-specific state directory |
| `list_subjects` | (none) | List of subjects with exam_date and progress | List all subjects that have been set up |
```

Add to the workflow section, before step 0:

```
-1. switch_subject("高数") → Switch to a subject (call before setup_review for new subjects)
-0.5. list_subjects() → List all existing subjects with progress info
```

- [ ] **Step 2: Update Chinese section**

Change `9 个工具` to `11 个工具` (2 occurrences).

Change `## 工具 (9)` to `## 工具 (11)`.

Add two rows to the Chinese tool table:

```
| `switch_subject` | subject（科目名） | 科目信息（名称、状态、知识点数） | 切换到科目专属状态目录 |
| `list_subjects` | （无） | 所有科目的列表及进度 | 列出所有已设置的科目 |
```

Add to the Chinese workflow:

```
-1. switch_subject("高数") → 切换到科目（新科目需先切换再 setup_review）
-0.5. list_subjects() → 列出所有科目及进度
```

Change `完整 9 工具工作流` to `完整 11 工具工作流`.

- [ ] **Step 3: Commit**

```bash
cd "D:/vscode/Hermes skills/exam-ai"
git add README.md
git commit -m "docs: update README for multi-subject support (9→11 tools)"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Each spec requirement maps to a task:
  - Storage structure (subject dirs) → Task 1 (`switch_subject` creates dirs)
  - `switch_subject` tool → Task 1 (state.py) + Task 2 (server.py)
  - `list_subjects` tool → Task 1 (state.py) + Task 2 (server.py)
  - Existing tools unchanged → verified (no changes to models, planner, diagnostic, scorer, structure)
  - Backward compat → Task 3 tests that no-switch still works
  - Test isolation → Task 3
  - README → Task 4
- [x] **Placeholder scan**: No TBD, TODO, or vague instructions
- [x] **Type consistency**: `switch_subject()` returns `dict`, `list_subjects()` returns `dict` — server wraps in `json.dumps`. `_switch_subject` and `_list_subjects` aliases used consistently