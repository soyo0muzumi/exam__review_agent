"""Plan generation — priority function and schedule builder.

The priority function is the SINGLE sorting standard:
    priority(topic) = importance + 0.8 × weakness
No exceptions. No ad-hoc overrides.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import DailyPlanItem, PlanResult, Topic


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
) -> PlanResult:
    """Generate the final review plan."""
    sorted_topics = sorted(topics, key=priority_score, reverse=True)
    learning_order = learning_order or [t.id for t in sorted_topics]

    priority_list = [
        {
            "id": t.id,
            "name": t.name,
            "level": t.level,
            "importance": round(t.importance, 2),
            "status": t.status,
            "priority": round(priority_score(t), 2),
        }
        for t in sorted_topics
    ]

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