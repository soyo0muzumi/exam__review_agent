"""Diagnostic helpers — next question selection, progress stats, fatigue."""

from __future__ import annotations

from .models import Topic


def get_a_level_topics(topics: list[Topic]) -> list[Topic]:
    """Return A-level topics."""
    return [t for t in topics if t.level == "A"]


def get_next_untested(
    topics: list[Topic],
    tested_ids: set[str],
    mode: str = "normal",
) -> Topic | None:
    """Get next A-level topic not in tested_ids.

    mode: "normal" (all A-level), "cram" (same), "quick" (first 3 A-level)
    """
    a_level = get_a_level_topics(topics)
    untested = [t for t in a_level if t.id not in tested_ids]

    if mode == "quick":
        untested = untested[:3]

    return untested[0] if untested else None


def get_next_for_retest(
    topics: list[Topic],
    tested_ids: set[str],
) -> Topic | None:
    """Get next weak/learning A-level topic for re-testing."""
    candidates = [
        t
        for t in topics
        if t.level == "A" and t.status in ("weak", "learning") and t.id not in tested_ids
    ]
    # Prioritize weak over learning
    weak = [t for t in candidates if t.status == "weak"]
    return weak[0] if weak else (candidates[0] if candidates else None)


def calculate_progress(topics: list[Topic]) -> dict:
    """Calculate progress stats for A-level topics."""
    a_level = get_a_level_topics(topics)
    tested = [t for t in a_level if t.status != "unknown"]

    return {
        "total": len(a_level),
        "tested": len(tested),
        "mastered": sum(1 for t in a_level if t.status == "mastered"),
        "learning": sum(1 for t in a_level if t.status == "learning"),
        "weak": sum(1 for t in a_level if t.status == "weak"),
    }


def detect_fatigue(topics: list[Topic]) -> bool:
    """True if last 3 consecutive A-level tested topics are 'weak'."""
    a_tested = [t for t in get_a_level_topics(topics) if t.status != "unknown"]

    if len(a_tested) < 3:
        return False

    last_3 = a_tested[-3:]
    return all(t.status == "weak" for t in last_3)