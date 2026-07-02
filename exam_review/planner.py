"""Plan generation — priority function and schedule builder.

The priority function is the SINGLE sorting standard:
    priority(topic) = importance + 0.8 × weakness
No exceptions. No ad-hoc overrides.
"""

from __future__ import annotations

from datetime import date, timedelta

from .diagnostic import (
    calculate_chapter_progress as _calc_chapter_progress,
    check_mastery_decay as _check_decay,
    suggest_question_type as _suggest_qtype,
)
from .models import ChapterProgress, DailyPlanItem, PlanResult, PracticeRecord, Topic


def priority_score(topic: Topic) -> float:
    """Core priority function. Sole sorting standard for all outputs."""
    weakness = {"weak": 1.0, "learning": 0.5, "mastered": 0.0, "unknown": 0.3}.get(
        topic.status, 0.3
    )
    return topic.importance + 0.8 * weakness


def generate_plan(
    topics: list[Topic],
    exam_date: str,
    daily_hours: float,
    mode: str = "normal",
    learning_order: list[str] | None = None,
    practice_history: list[PracticeRecord] | None = None,
) -> PlanResult:
    """Generate the final review plan."""
    practice_history = practice_history or []
    sorted_topics = sorted(topics, key=priority_score, reverse=True)
    learning_order = learning_order or [t.id for t in sorted_topics]

    # mastery_decay: read-only, applied to priority_list output only
    # (topic.status is NEVER modified)
    priority_list = []
    for t in sorted_topics:
        decayed = _check_decay(t, practice_history)
        effective_status = "learning" if decayed == "decayed" else t.status
        priority_list.append(
            {
                "id": t.id,
                "name": t.name,
                "level": t.level,
                "importance": round(t.importance, 2),
                "status": effective_status,
                "priority": round(priority_score(t), 2),
                "question_type": _suggest_qtype(t),
            }
        )

    # chapter_progress — NEW
    chapter_progress = _calc_chapter_progress(topics, learning_order)

    if mode == "quick":
        daily_schedule = []
    elif mode == "cram":
        daily_schedule = _build_cram_schedule(sorted_topics, exam_date, daily_hours)
    else:
        daily_schedule = _build_normal_schedule(
            sorted_topics, exam_date, daily_hours, learning_order
        )

    weak_summary = _build_weak_summary(sorted_topics)

    return PlanResult(
        chapter_progress=chapter_progress,
        priority_list=priority_list,
        daily_schedule=daily_schedule,
        weak_summary=weak_summary,
    )


def _topic_duration(topic: Topic) -> int:
    """Duration in minutes based on level."""
    return {"A": 45, "B": 30, "C": 15}.get(topic.level, 30)


def _build_normal_schedule(
    sorted_topics: list[Topic],
    exam_date: str,
    daily_hours: float,
    learning_order: list[str],
) -> list[DailyPlanItem]:
    """Build schedule: pack by priority. Review day frequency is adaptive:
    - Every 3rd day if ≤50% of A-level topics are weak
    - Every 2nd day if >50% of A-level topics are weak
    """
    daily_minutes = int(daily_hours * 60)
    exam = date.fromisoformat(exam_date)
    remaining = list(sorted_topics)
    schedule: list[DailyPlanItem] = []
    day_num = 1
    current_date = date.today()

    # Adaptive review frequency
    a_level = [t for t in sorted_topics if t.level == "A"]
    weak_ratio = sum(1 for t in a_level if t.status == "weak") / max(len(a_level), 1)
    review_interval = 2 if weak_ratio > 0.5 else 3

    while remaining and current_date <= exam:
        is_review_day = day_num % review_interval == 0

        if is_review_day:
            review_topics = [t for t in sorted_topics if t.status in ("weak", "learning")]
            topic_names = [t.name for t in review_topics[: daily_minutes // 20]]
            schedule.append(
                DailyPlanItem(
                    day=day_num,
                    topics=topic_names or ["综合复习"],
                    duration_min=daily_minutes,
                )
            )
        else:
            sessions: list[str] = []
            minutes_left = daily_minutes

            for t in list(remaining):
                dur = _topic_duration(t)
                if minutes_left >= dur:
                    sessions.append(t.name)
                    minutes_left -= dur
                    remaining.remove(t)
                if minutes_left < 15:
                    break

            schedule.append(
                DailyPlanItem(day=day_num, topics=sessions, duration_min=daily_minutes - minutes_left)
            )

        day_num += 1
        current_date += timedelta(days=1)

    return schedule


def _build_cram_schedule(
    sorted_topics: list[Topic],
    exam_date: str,
    daily_hours: float,
) -> list[DailyPlanItem]:
    """Cram mode: pack tightly, A-level only, no review days."""
    daily_minutes = int(daily_hours * 60)
    exam = date.fromisoformat(exam_date)
    remaining = sorted_topics.copy()
    schedule: list[DailyPlanItem] = []
    day_num = 1
    current_date = date.today()

    while remaining and current_date <= exam:
        sessions: list[str] = []
        minutes_left = daily_minutes

        for t in list(remaining):
            dur = _topic_duration(t)
            if minutes_left >= dur:
                sessions.append(t.name)
                minutes_left -= dur
                remaining.remove(t)
            if minutes_left < 15:
                break

        schedule.append(
            DailyPlanItem(day=day_num, topics=sessions, duration_min=daily_minutes - minutes_left)
        )
        day_num += 1
        current_date += timedelta(days=1)

    return schedule


def _build_weak_summary(sorted_topics: list[Topic]) -> str:
    """Build a summary of weak/learning high-importance topics."""
    weak = [t for t in sorted_topics if t.status == "weak" and t.importance > 0.7]

    if not weak:
        return "没有明显的薄弱点，继续保持！"

    lines = ["⚠ 重点薄弱:"]
    for t in weak[:5]:
        lines.append(f"  - {t.name} ({t.level}级, {t.importance:.2f})")
    return "\n".join(lines)


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
        chapters: dict[str, list[Topic]] = {}
        no_chapter: list[Topic] = []
        for t in topics:
            if t.chapter:
                chapters.setdefault(t.chapter, []).append(t)
            else:
                no_chapter.append(t)
        sorted_groups: list[tuple[str, list[Topic]]] = []
        for ch_name in sorted(chapters.keys()):
            sorted_groups.append((ch_name, sorted(chapters[ch_name], key=lambda t: t.importance, reverse=True)))
        if no_chapter:
            sorted_groups.append(("未分类", sorted(no_chapter, key=lambda t: t.importance, reverse=True)))
    else:
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
                key_labels = {
                    "formulas": "公式",
                    "definitions": "定义",
                    "parameters": "参数",
                    "methods": "方法",
                    "pitfalls": "易错",
                    "examples": "例题",
                    "homework_refs": "作业",
                    "distinctions": "区别",
                }
                for key, vals in t.attributes.items():
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