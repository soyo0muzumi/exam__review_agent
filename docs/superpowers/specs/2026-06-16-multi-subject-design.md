# Exam-AI: Multi-Subject Support Design

## Context

Exam-AI currently stores all state in a single global `~/.exam-review/state.json`. When a user needs to review multiple subjects (e.g., linear algebra AND probability theory), they must call `setup_review` to reset the entire state — losing all progress, topics, and practice history for the previous subject. This design adds subject isolation so each subject has its own independent state, chapters, and progress.

## Decisions

- **Isolation level**: Complete — each subject is an independent "notebook" with its own state, chapters, topics, practice history.
- **Subject identifier**: Subject name (e.g., "高数", "线性代数"). Used as directory name under `~/.exam-review/`.
- **Switching mechanism**: New `switch_subject` tool changes the global `_state_path` and `CHAPTERS_DIR` pointers. All existing tools work on the current subject without API changes.
- **Backward compatibility**: If no subject is switched, the system operates on `~/.exam-review/state.json` (old behavior). New users call `switch_subject` before `setup_review`.

---

## 1. Storage structure

```
~/.exam-review/
  state.json              ← legacy global state (backward compat)
  chapters/
    <hash>.json           ← legacy global chapters
  高数/
    state.json            ← subject-specific state
    chapters/
      <hash>.json
  线性代数/
    state.json
    chapters/
      <hash>.json
```

## 2. New tools

### `switch_subject(subject: str) -> str`

Switches all state operations to the named subject. Creates the subject directory if it doesn't exist. Does NOT create state — the user must call `setup_review` after switching to a new subject.

**Behavior:**
1. Set `_state_path` → `~/.exam-review/{subject}/state.json`
2. Set `CHAPTERS_DIR` → `~/.exam-review/{subject}/chapters/`
3. Create directories if they don't exist
4. Return current subject name and whether state exists

**Return example:**
```json
{
  "subject": "高数",
  "state_exists": true,
  "topics_count": 25,
  "exam_date": "2026-07-15"
}
```

If state doesn't exist yet: `"state_exists": false, "topics_count": 0, "exam_date": ""`.

### `list_subjects() -> str`

Lists all subjects that have a `state.json` in their directory. Scans `~/.exam-review/` subdirectories.

**Return example:**
```json
{
  "current_subject": "高数",
  "subjects": [
    {"name": "高数", "exam_date": "2026-07-15", "topics_count": 25, "tested_count": 10},
    {"name": "线性代数", "exam_date": "2026-07-20", "topics_count": 18, "tested_count": 0}
  ]
}
```

## 3. Changes to existing code

### `state.py`

- `_state_path` and `CHAPTERS_DIR` already are global variables — `switch_subject` just sets them to the subject-specific paths
- Add `_current_subject: str | None = None` global to track which subject is active
- `set_state_path()` already exists for tests — `switch_subject` uses the same mechanism
- `reset_state()` already deletes `state.json` and `chapters/` — it operates on the current subject's directory, which is correct

**New function:**
```python
def switch_subject(subject: str) -> dict:
    """Switch to a subject-specific state directory."""
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

**New function:**
```python
def list_subjects() -> dict:
    """List all subjects with state files."""
    subject_dirs = []
    for d in DEFAULT_STATE_DIR.iterdir():
        if d.is_dir() and (d / "state.json").exists():
            state = ReviewState.model_validate_json((d / "state.json").read_text(encoding="utf-8"))
            subject_dirs.append({
                "name": d.name,
                "exam_date": state.exam_date,
                "topics_count": len(state.topics),
                "tested_count": len(state.tested_topic_ids),
            })
    return {"current_subject": _current_subject, "subjects": subject_dirs}
```

### `server.py`

- Add `switch_subject` tool (Tool 9)
- Add `list_subjects` tool (Tool 10)
- Update module docstring: 9 tools → 10 tools
- Update `instructions` string: add switch_subject and list_subjects to the workflow
- All existing tools work unchanged — they call `load_state()`/`save_state()` which operate on `_state_path`, which is now subject-specific

### `test_all.py`

- Test `switch_subject` creating a new subject directory
- Test `list_subjects` returning subject info
- Test that operations after `switch_subject("高数")` are isolated from `switch_subject("线性代数")`

## 4. Backward compatibility

- If `switch_subject` is never called, the system uses `~/.exam-review/state.json` — the old global behavior
- Existing users who only have one subject continue working without any changes
- No data migration needed — the global state file stays where it is

## 5. What does NOT change

- `ReviewState` model stays the same
- All tool signatures stay the same (no new `subject` parameter on existing tools)
- `Topic`, `PracticeRecord`, etc. — no changes
- `planner.py`, `diagnostic.py`, `scorer.py`, `structure.py` — no changes

## Tool count summary

| Phase | Tool count | New tools |
|-------|-----------|------------|
| Before this PR | 9 | — |
| After this PR | 11 | switch_subject, list_subjects |

## Verification

1. `python test_all.py` — all existing tests pass (backward compat)
2. `switch_subject("高数")` → creates directory, returns `"state_exists": false`
3. `setup_review(...)` after switch → state stored in `~/.exam-review/高数/state.json`
4. `switch_subject("线性代数")` → independent state
5. `list_subjects()` → returns both subjects with info
6. Old global state still works if `switch_subject` is never called