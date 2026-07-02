"""Diagnostic helpers — next question selection, progress stats, fatigue."""

from __future__ import annotations

from datetime import date, datetime

from .models import ChapterProgress, PracticeRecord, Topic


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


def suggest_question_type(topic: Topic) -> str:
    """Suggest question type based on topic attributes (ALEKS + SuperMemo 20 Rules).

    Priority: distinctions→mcq, methods→calculation, formulas→fill_blank, definitions→short_answer.
    """
    attrs = topic.attributes or {}
    if attrs.get("distinctions"):
        return "mcq"
    if attrs.get("methods"):
        return "calculation"
    if attrs.get("formulas"):
        return "fill_blank"
    if attrs.get("definitions"):
        return "short_answer"
    return "fill_blank"


def calculate_chapter_progress(
    topics: list[Topic],
) -> list[ChapterProgress]:
    """Calculate per-chapter progress with ready_to_learn (ALEKS outer fringe).

    ready_to_learn: topics whose dependencies are all mastered.
    """
    chapters: dict[str, dict] = {}
    id_to_topic = {t.id: t for t in topics}

    for t in topics:
        ch = t.chapter or "未分类"
        if ch not in chapters:
            chapters[ch] = {
                "total": 0, "mastered": 0, "learning": 0, "weak": 0, "untested": 0,
                "ready_candidates": [],
            }
        chapters[ch]["total"] += 1
        if t.status == "mastered":
            chapters[ch]["mastered"] += 1
        elif t.status == "learning":
            chapters[ch]["learning"] += 1
        elif t.status == "weak":
            chapters[ch]["weak"] += 1
        else:
            chapters[ch]["untested"] += 1

        # Candidate for ready_to_learn: not mastered, all deps mastered
        if t.status != "mastered":
            deps_mastered = all(
                id_to_topic[dep].status == "mastered"
                for dep in t.depends_on if dep in id_to_topic
            )
            if deps_mastered:
                chapters[ch]["ready_candidates"].append(t.name)

    result = []
    for ch_name in sorted(chapters.keys()):
        ch_data = chapters[ch_name]
        result.append(ChapterProgress(
            chapter=ch_name,
            total=ch_data["total"],
            mastered=ch_data["mastered"],
            learning=ch_data["learning"],
            weak=ch_data["weak"],
            untested=ch_data["untested"],
            ready_to_learn=sorted(ch_data["ready_candidates"]),
        ))
    return result


def check_mastery_decay(
    topic: Topic,
    practice_history: list[PracticeRecord],
    decay_days: int = 7,
    reference_date: date | None = None,
) -> str:
    """Check if a mastered topic has decayed (no recent practice).

    Returns "decayed" if last practice > decay_days ago, "stable" otherwise.
    For non-mastered topics, always returns "stable".
    """
    if topic.status != "mastered":
        return "stable"

    ref = reference_date or date.today()

    # Find most recent practice record for this topic
    topic_records = [r for r in practice_history if r.topic_id == topic.id]
    if not topic_records:
        return "stable"

    last = max(topic_records, key=lambda r: r.date)
    try:
        last_date = date.fromisoformat(last.date)
    except (ValueError, TypeError):
        return "stable"

    if (ref - last_date).days > decay_days:
        return "decayed"
    return "stable"


def detect_knowledge_gaps(
    topics: list[Topic],
    expected_topics: list[dict],
) -> dict:
    current_names = {t.name.lower(): t for t in topics}
    coverage_keys = {"formulas", "definitions", "methods", "distinctions", "pitfalls"}
    missing = []
    partial = []
    present = 0

    for expected in expected_topics:
        name = expected.get("name", "")
        name_lower = name.lower()
        if not name:
            continue

        if name_lower in current_names:
            topic = current_names[name_lower]
            attrs = topic.attributes or {}
            existing_attrs = [k for k in coverage_keys if attrs.get(k)]
            missing_attrs = [k for k in coverage_keys if not attrs.get(k)]
            if missing_attrs:
                partial.append({
                    "name": topic.name,
                    "existing_attrs": existing_attrs,
                    "missing_attrs": missing_attrs,
                    "suggestion": f"{topic.name}缺少" + "、".join(missing_attrs),
                })
            else:
                present += 1
        else:
            matched = None
            for cn in current_names:
                if name_lower in cn or cn in name_lower:
                    matched = current_names[cn]
                    break
            if matched:
                attrs = matched.attributes or {}
                existing_attrs = [k for k in coverage_keys if attrs.get(k)]
                missing_attrs = [k for k in coverage_keys if not attrs.get(k)]
                partial.append({
                    "name": matched.name,
                    "existing_attrs": existing_attrs,
                    "missing_attrs": missing_attrs,
                    "suggestion": f"名称相似: 期望'{name}'，实际'{matched.name}'",
                })
            else:
                missing.append({
                    "name": name,
                    "level": expected.get("level", "C"),
                    "chapter": expected.get("chapter", ""),
                })

    return {
        "missing": missing,
        "partial": partial,
        "present": present,
        "total_expected": len(expected_topics),
    }