"""JSON state persistence — save/load/reset exam review state.

State file: ~/.exam-review/state.json (compact, no chapter text)
Chapter files: ~/.exam-review/chapters/<hash>.json (full text, separate)
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from .models import ReviewState

# Default: user home directory to avoid git commits
DEFAULT_STATE_DIR = Path.home() / ".exam-review"
DEFAULT_STATE_PATH = DEFAULT_STATE_DIR / "state.json"
CHAPTERS_DIR = DEFAULT_STATE_DIR / "chapters"

_state_path = DEFAULT_STATE_PATH
_current_subject: str | None = None


def set_state_path(path: Path) -> None:
    global _state_path
    _state_path = path


def load_state() -> ReviewState | None:
    """Load state from JSON file. Returns None if no state exists."""
    if not _state_path.exists():
        return None
    try:
        data = json.loads(_state_path.read_text(encoding="utf-8"))
        return ReviewState.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def save_state(state: ReviewState) -> None:
    """Save state to JSON file with atomic write."""
    content = state.model_dump_json(indent=2)
    _state_path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to temp then rename
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(_state_path.parent), suffix=".json"
    )
    try:
        with open(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(_state_path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def reset_state() -> None:
    """Delete state file and chapter files."""
    if _state_path.exists():
        _state_path.unlink()
    if CHAPTERS_DIR.exists():
        for f in CHAPTERS_DIR.glob("*.json"):
            f.unlink()


# ─── Chapter text storage ─────────────────────────────────────


def _chapter_key(name: str) -> str:
    """Generate a filesystem-safe key for a chapter name."""
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def save_chapter_text(name: str, text: str) -> None:
    """Save a chapter's full text to a separate file."""
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    key = _chapter_key(name)
    path = CHAPTERS_DIR / f"{key}.json"
    path.write_text(json.dumps({"name": name, "text": text}, ensure_ascii=False), encoding="utf-8")


def load_all_chapter_text() -> str:
    """Load all chapter texts concatenated for frequency counting."""
    if not CHAPTERS_DIR.exists():
        return ""
    parts = []
    for path in sorted(CHAPTERS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            parts.append(data.get("text", ""))
        except (json.JSONDecodeError, ValueError):
            continue
    return "\n".join(parts)


def load_chapter_text(name: str) -> str | None:
    """Load a single chapter's text by name."""
    key = _chapter_key(name)
    path = CHAPTERS_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("text")
    except (json.JSONDecodeError, ValueError):
        return None


def get_or_create_state() -> ReviewState:
    """Load state or create fresh if none exists."""
    state = load_state()
    if state is None:
        state = ReviewState()
        save_state(state)
    return state


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