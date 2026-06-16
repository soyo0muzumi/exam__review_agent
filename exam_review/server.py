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
  8. get_question_bank — Return topics with examples or homework references
"""

from __future__ import annotations

import json
from datetime import date
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .models import (
    Topic,
    ReviewState,
    PracticeRecord,
)
from .parser import parse_text
from .scorer import score_topics
from .state import (
    get_or_create_state,
    load_all_chapter_text,
    load_state,
    reset_state,
    save_chapter_text,
    save_state,
)
from .structure import topological_sort
from .diagnostic import (
    calculate_progress,
    detect_fatigue,
    get_a_level_topics,
    get_next_untested,
    get_next_for_retest,
)
from .planner import generate_plan as _generate_plan
from .planner import render_review_doc as _render_review_doc

mcp = FastMCP(
    "exam-review",
    instructions="""Final Exam Review MCP Server — 9 tools for AI study coaching.

═══ AUTHORITY BOUNDARY ═══
TOOL = single source of truth. AI = interface only.
AI MUST NOT: compute priority, modify scores, reorder topics, skip steps.
AI CAN ONLY: extract knowledge points from text, ask questions, judge answers, present results.
All scoring, sorting, and scheduling come exclusively from these tools. Do not override or second-guess tool output.
════════════════

Workflow:
  0. setup_review(exam_date, daily_hours, chapter_weights?) → state
  1. Use pdf-mcp's pdf_read_all to extract text from PDF (or other tools for DOCX/MD)
  2. parse_material(text) → chapters (AI reads them, identifies knowledge points)
  3. sync_topics(topics) → scored topics + learning order (AI does NOT recompute)
     Each topic can include "attributes" (dict: type→list[str]) and "source" (textbook excerpt)
  4. get_next_topic() → next A-level topic with attributes & source; AI asks question; record_answer(result)
     Repeat until get_next_topic returns done:true
  5. generate_plan() → priority list + daily schedule + weak summary
  6. (Optional) get_next_topic(filter="all") → re-test weak topics; repeat from 4

AI responsibilities: identifying knowledge points from parsed text, generating questions, judging answers.
Tool responsibilities: state, parsing, scoring math, topological sort, schedule generation, priority ranking.

Additional tools:
  - patch_topic(topic_id, level?, attributes_merge?, source?) → incrementally update a single topic
    Use when the user wants to add/correct a key point without re-syncing all topics.
  - generate_review_doc(sort_by?) -> Markdown review document (chapter or learning_order)
  - get_question_bank(topic_ids?) -> Topics with examples/homework_refs""",
)


# ─── Tool 1: setup_review ──────────────────────────────────────


@mcp.tool()
def setup_review(
    exam_date: str,
    daily_hours: float,
    chapter_weights: dict[str, float] | None = None,
    mode: Literal["normal", "cram", "quick"] = "normal",
) -> str:
    """Initialize or reset exam review state.

    Args:
        exam_date: Exam date in YYYY-MM-DD format.
        daily_hours: Available study hours per day (0.5-16).
        chapter_weights: Optional dict mapping chapter names to weight multipliers (e.g. {"第3章": 1.15}).
        mode: "normal", "cram" (≤3 days to exam), or "quick" (priority list only).
    """
    state = ReviewState(
        exam_date=exam_date,
        daily_hours=daily_hours,
        chapter_weights=chapter_weights or {},
        mode=mode,
    )
    save_state(state)

    return json.dumps(
        {
            "exam_date": exam_date,
            "daily_hours": daily_hours,
            "mode": mode,
            "chapter_weights": chapter_weights or {},
            "topics_count": 0,
        },
        ensure_ascii=False,
        indent=2,
    )


# ─── Tool 2: parse_material ────────────────────────────────────


@mcp.tool()
def parse_material(text: str) -> str:
    """Split plain text into chapter-based chunks. For PDF files, first use pdf-mcp's pdf_read_all to extract text, then pass the extracted text here.

    Args:
        text: Full text content extracted from PDF/DOCX/MD by the caller.
    """

    try:
        chapters = parse_text(text)
    except Exception as e:
        return json.dumps({"error": f"解析失败: {e}"})

    state = get_or_create_state()
    # Store chapter refs in state (name + length only, NOT full text)
    # Full text goes to separate chapter files on disk
    state.chapters = [
        {"name": ch["name"], "text_length": len(ch["text"])} for ch in chapters
    ]
    for ch in chapters:
        save_chapter_text(ch["name"], ch["text"])
    save_state(state)

    # Return chapters with text for AI to read
    return json.dumps(
        {"chapters": chapters, "total_chapters": len(chapters)},
        ensure_ascii=False,
        indent=2,
    )


# ─── Tool 3: sync_topics ──────────────────────────────────────


@mcp.tool()
def sync_topics(topics: list[dict]) -> str:
    """Submit all knowledge points at once. This is the ONLY way to set topics. AI identifies topics from parsed text, assigns levels, and lists dependencies. The tool auto-calculates importance and learning order. Calling again ADDS new topics and UPDATES metadata of existing ones (name, level, chapter, depends_on, attributes, source), but does NOT recompute importance of already-scored topics. Note: attributes and source are REPLACED on update, not merged — use patch_topic for incremental changes.

    Args:
        topics: List of topic dicts. Each must have "name" and "level" (A/B/C). Optional: "chapter", "depends_on" (list of other topic names), "attributes" (dict of semantic-type→list[str], e.g. {"formulas": ["y=wx+b"], "pitfalls": ["过拟合"]}), "source" (relevant textbook excerpt for this topic).
    """
    state = load_state()
    if state is None:
        return json.dumps({"error": "请先调用 setup_review 初始化。"})

    # Load full text from chapter files (not from state) for frequency counting
    full_text = load_all_chapter_text()

    # Build id→topic lookup for existing topics
    existing_map = {t.id: t for t in state.topics}

    added = 0
    updated = 0
    new_topics = []

    for t in topics:
        topic_id = t["name"].replace(" ", "_").lower()

        # Resolve depends_on from names to IDs
        depends_on = []
        for dep_name in t.get("depends_on", []):
            dep_id = dep_name.replace(" ", "_").lower()
            depends_on.append(dep_id)

        if topic_id in existing_map:
            # Update metadata only — do NOT recompute importance
            existing = existing_map[topic_id]
            existing.level = t.get("level", existing.level)
            existing.chapter = t.get("chapter", existing.chapter)
            existing.depends_on = depends_on or existing.depends_on
            # Replace attributes and source — sync_topics provides a full snapshot
            if "attributes" in t:
                existing.attributes = t["attributes"]
            # Update source only if provided and non-empty
            if t.get("source"):
                existing.source = t["source"]
            updated += 1
        else:
            new_topics.append(
                Topic(
                    id=topic_id,
                    name=t["name"],
                    level=t.get("level", "C"),
                    importance=0.25,
                    chapter=t.get("chapter", ""),
                    status="unknown",
                    depends_on=depends_on,
                    attributes=t.get("attributes", {}),
                    source=t.get("source", ""),
                )
            )
            added += 1

    # Score ONLY new topics (existing ones keep their scores)
    # Always score new topics, even with empty text (they get base importance)
    if new_topics:
        scored_new = score_topics(new_topics, full_text, state.chapter_weights)
        # Merge: keep existing + add new scored
        state.topics = [t for t in state.topics if t.id not in {nt.id for nt in scored_new}] + scored_new
    else:
        state.topics.extend(new_topics)

    # Recompute learning order via topological sort
    state.learning_order = topological_sort(state.topics)
    state.topic_version += 1

    save_state(state)

    return json.dumps(
        {
            "added": added,
            "updated": updated,
            "topic_version": state.topic_version,
            "topics": [t.model_dump() for t in state.topics],
            "learning_order": state.learning_order,
        },
        ensure_ascii=False,
        indent=2,
    )


# ─── Tool 4: record_answer ────────────────────────────────────


@mcp.tool()
def record_answer(
    topic_id: str,
    result: Literal["mastered", "learning", "weak"],
) -> str:
    """Record diagnostic result for a topic. AI judges the user's answer quality and calls this with the assessment.

    Args:
        topic_id: The topic ID that was tested.
        result: AI's assessment — "mastered", "learning", or "weak".
    """
    state = load_state()
    if state is None:
        return json.dumps({"error": "请先调用 setup_review 初始化。"})

    topic = next((t for t in state.topics if t.id == topic_id), None)
    if topic is None:
        return json.dumps({"error": f"知识点 '{topic_id}' 不存在。"})

    topic.status = result
    if topic_id not in state.tested_topic_ids:
        state.tested_topic_ids.append(topic_id)
    state.practice_history.append(
        PracticeRecord(topic_id=topic_id, date=date.today().isoformat(), result=result)
    )
    save_state(state)

    progress = calculate_progress(state.topics)
    fatigue = detect_fatigue(state.topics)

    return json.dumps(
        {
            "topic_id": topic_id,
            "name": topic.name,
            "result": result,
            "attributes": topic.attributes,
            "source": topic.source,
            "progress": progress,
            "fatigue": fatigue,
        },
        ensure_ascii=False,
        indent=2,
    )


# ─── Tool 5: get_next_topic ───────────────────────────────────


@mcp.tool()
def get_next_topic(
    filter: Literal["untested", "all"] = "untested",
) -> str:
    """Get the next A-level topic to test. Returns null if all are tested.

    Args:
        filter: "untested" returns only topics not yet tested. "all" returns any A-level topic (for re-testing weak ones).
    """
    state = load_state()
    if state is None or not state.topics:
        return json.dumps({"error": "没有知识点。请先调用 sync_topics。"})

    mode = state.mode if hasattr(state, "mode") else "normal"
    tested_ids = set(state.tested_topic_ids)

    if filter == "untested":
        next_topic = get_next_untested(state.topics, tested_ids, mode)
    else:
        # Return next weak/learning topic for re-testing (exclude already tested in this round)
        next_topic = get_next_for_retest(state.topics, tested_ids)

    if next_topic is None:
        return json.dumps({"done": True, "message": "所有 A 级知识点已测试完毕。"})

    return json.dumps(
        {"topic_id": next_topic.id, "name": next_topic.name, "level": next_topic.level, "attributes": next_topic.attributes, "source": next_topic.source},
        ensure_ascii=False,
        indent=2,
    )


# ─── Tool 5.5: patch_topic ────────────────────────────────────


@mcp.tool()
def patch_topic(
    topic_id: str,
    level: str | None = None,
    attributes_merge: dict[str, list[str]] | None = None,
    source: str | None = None,
) -> str:
    """Incrementally update a single topic. Use this to add key points, fix attributes, or update source text without re-syncing all topics.

    Args:
        topic_id: The topic ID to update.
        level: Optional new level (A/B/C).
        attributes_merge: Optional dict to merge into existing attributes. Lists are extended, not replaced. E.g. {"pitfalls": ["R²高≠模型好"]} adds to existing pitfalls without removing others.
        source: Optional new source text. Only updates if non-empty.
    """
    state = load_state()
    if state is None:
        return json.dumps({"error": "请先调用 setup_review 初始化。"})

    topic = next((t for t in state.topics if t.id == topic_id), None)
    if topic is None:
        return json.dumps({"error": f"知识点 '{topic_id}' 不存在。"})

    if level is not None:
        topic.level = level

    if attributes_merge:
        for k, v in attributes_merge.items():
            topic.attributes.setdefault(k, []).extend(v)

    if source:
        topic.source = source

    save_state(state)

    return json.dumps(
        {
            "topic_id": topic.id,
            "name": topic.name,
            "level": topic.level,
            "attributes": topic.attributes,
            "source": topic.source,
        },
        ensure_ascii=False,
        indent=2,
    )


# ─── Tool 6: generate_plan ────────────────────────────────────


@mcp.tool()
def generate_plan() -> str:
    """Generate the final review plan: priority list, daily schedule, and weak summary. Uses the priority function: importance + 0.8 × weakness. Call after diagnostic testing is complete."""
    state = load_state()
    if state is None or not state.topics:
        return json.dumps({"error": "没有知识点。请先完成 setup + sync_topics。"})

    if not state.exam_date:
        return json.dumps({"error": "请先调用 setup_review 设置考试日期。"})

    plan = _generate_plan(
        topics=state.topics,
        exam_date=state.exam_date,
        daily_hours=state.daily_hours,
        mode=getattr(state, "mode", "normal"),
        learning_order=state.learning_order,
    )

    save_state(state)
    return plan.model_dump_json(indent=2)


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


# ─── Entry Point ───────────────────────────────────────────────


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()