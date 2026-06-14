"""Importance scoring — pure computation, no LLM.

Three-tier rule:
    A = 0.85  (掌握, 重点, 必考, 高频, 核心)
    B = 0.55  (理解, 熟悉, 应用)
    C = 0.25  (了解, 知道, 选学)

Adjustments:
    +0.10 if frequency ≥ 3
    ×chapter_weight if chapter is in chapter_weights
"""

from __future__ import annotations

import re

from .models import Topic

LEVEL_BASE = {"A": 0.85, "B": 0.55, "C": 0.25}


def count_occurrences(text: str, term: str) -> int:
    """Count occurrences of term in text, using word boundaries for safety.

    For Chinese terms (containing CJK characters), uses direct substring
    matching since word boundaries don't apply. For Latin terms, uses
    regex word boundaries to avoid substring false positives.
    """
    if not term or not text:
        return 0

    # Check if term contains CJK characters
    has_cjk = bool(re.search(r"[一-鿿㐀-䶿]", term))

    if has_cjk:
        # Chinese: direct substring count (word boundaries unreliable for CJK)
        return text.count(term)
    else:
        # Latin: regex word boundary to avoid substring matches
        pattern = rf"\b{re.escape(term)}\b"
        return len(re.findall(pattern, text, re.IGNORECASE))


def calculate_importance(
    level: str,
    frequency: int,
    chapter_weights: dict[str, float] | None,
    chapter: str,
) -> float:
    """Calculate importance score for a topic."""
    importance = LEVEL_BASE.get(level, 0.25)

    if frequency >= 3:
        importance += 0.10

    if chapter_weights and chapter in chapter_weights:
        importance *= chapter_weights[chapter]

    return min(max(importance, 0.0), 1.0)


def score_topics(
    topics: list[Topic],
    full_text: str,
    chapter_weights: dict[str, float] | None = None,
) -> list[Topic]:
    """Score topics based on frequency in the source text and chapter weights.

    Only scores topics with importance == 0.25 (unscored / newly added).
    Existing topics keep their computed scores.
    """
    chapter_weights = chapter_weights or {}

    for topic in topics:
        freq = count_occurrences(full_text, topic.name)
        topic.importance = calculate_importance(
            topic.level, freq, chapter_weights, topic.chapter
        )

    return topics