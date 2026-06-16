"""Pydantic models for exam review state — minimal necessary schema.

Chapter text is NOT stored in state (too large). It lives in separate
chapter files under ~/.exam-review/chapters/ and is loaded on demand
for frequency counting during sync_topics.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChapterRef(BaseModel):
    """Reference to a chapter — name and length only. Full text stored on disk."""
    name: str
    text_length: int = 0


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


class PracticeRecord(BaseModel):
    topic_id: str
    date: str       # ISO format: "2026-06-16"
    result: Literal["mastered", "learning", "weak"]


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
    practice_history: list[PracticeRecord] = Field(default_factory=list)


class DailyPlanItem(BaseModel):
    day: int
    topics: list[str]
    duration_min: int


class PlanResult(BaseModel):
    priority_list: list[dict]
    daily_schedule: list[DailyPlanItem]
    weak_summary: str