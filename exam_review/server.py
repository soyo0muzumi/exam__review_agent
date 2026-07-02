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

from __future__ import annotations

from collections import defaultdict
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
    switch_subject as _switch_subject,
    list_subjects as _list_subjects,
)
from .structure import topological_sort
from .diagnostic import (
    calculate_progress,
    detect_fatigue,
    get_a_level_topics,
    get_next_untested,
    get_next_for_retest,
    suggest_question_type,  # NEW
)
from .planner import generate_plan as _generate_plan
from .planner import render_review_doc as _render_review_doc

mcp = FastMCP(
    "exam-review",
    instructions="""Final Exam Review MCP Server — tools for AI study coaching.

═══ AUTHORITY BOUNDARY ═══
TOOL = source of truth. AI = interface only.
AI MUST NOT: compute priority, modify scores, reorder topics, skip steps.
AI CAN ONLY: extract knowledge points from text, ask questions, judge answers, present results.
════════════════

Workflow:
  -1. switch_subject("科目名")
  -0.5. list_subjects()
  0. setup_review(exam_date, daily_hours, chapter_weights?)
  1. Use pdf-mcp's pdf_read_all to extract text from PDF
  2. parse_material(text) → chapters
  3. sync_topics(topics) → scored topics + learning order
  4. get_next_topic() → next A-level topic with suggested_question_type & attributes & source; AI asks question matching type; record_answer(result, question?, user_answer?, correct_answer?)
  5. generate_plan() → priority list + daily schedule + weak summary + chapter_progress

Question types (from suggested_question_type):
  fill_blank   → fill-in-the-blank (formulas, atomic facts)
  short_answer → short answer (definitions, concepts)
  calculation  → step-by-step computation (methods, algorithms)
  mcq          → multiple choice (distinctions only)

Present chapter_progress FIRST (ALEKS Pie), then priority_list.

Additional tools:
  switch_subject(subject), list_subjects(), patch_topic(...),
  generate_review_doc(sort_by?, format?), get_question_bank(topic_ids?),
  generate_mistake_sheet() → Markdown mistake review""",
)


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
        topics: List of topic dicts. Each must have "name" and "level" (A/B/C). Optional: "chapter", "depends_on" (list of other topic names), "attributes" (dict of semantic-type→list[str]), "source" (relevant textbook excerpt for this topic).
            Recommended attributes keys:
              "formulas"      — core formulas and theorems
              "definitions"   — key definitions and concepts
              "parameters"    — parameters and their physical/math meaning
              "methods"       — methods, procedures, algorithms (encoding/decoding, proof,
                                derivation, solution steps — any "how-to")
              "pitfalls"      — common misconceptions
              "examples"      — example problems. Prioritize textbook "例"/"例题" markers.
                                If textbook lacks examples, AI may call web_search for supplementary
                                problems, but MUST confirm with the user and mark each item with
                                "(来源: 网络搜索)". NEVER fabricate from model knowledge.
              "homework_refs" — homework/exercise references. Same sourcing rules as examples:
                                textbook first, web_search with confirmation + attribution second,
                                never fabricated.
              "distinctions"  — comparisons and disambiguations (易混淆概念对比)
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
    question: str | None = None,
    user_answer: str | None = None,
    correct_answer: str | None = None,
) -> str:
    """Record diagnostic result for a topic. AI judges the user's answer quality and calls this with the assessment.

    Args:
        topic_id: The topic ID that was tested.
        result: AI's assessment — "mastered", "learning", or "weak".
        question: Optional question text that was asked.
        user_answer: Optional answer given by the user.
        correct_answer: Optional correct answer for reference.
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
        PracticeRecord(
            topic_id=topic_id,
            date=date.today().isoformat(),
            result=result,
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer,
        )
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
        {
            "topic_id": next_topic.id,
            "name": next_topic.name,
            "level": next_topic.level,
            "attributes": next_topic.attributes,
            "source": next_topic.source,
            "suggested_question_type": suggest_question_type(next_topic),  # NEW
        },
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
        practice_history=state.practice_history,
    )

    # NOTE: state is NOT saved — generate_plan is read-only
    return plan.model_dump_json(indent=2)


# ─── Tool 7: generate_review_doc ─────────────────────────────────


@mcp.tool()
def generate_review_doc(
    sort_by: Literal["chapter", "learning_order"] = "chapter",
    format: Literal["detailed", "quickref"] = "detailed",
) -> str:
    """Generate a Markdown review document organized by chapter or learning order. Returns Markdown text for AI to present or save.

    Args:
        sort_by: "chapter" groups topics by chapter, "learning_order" follows topological sort order.
        format: "detailed" (default) for full attribute listing, "quickref" for compact table format.
    """
    state = load_state()
    if state is None or not state.topics:
        return json.dumps({"error": "没有知识点。请先完成 setup + sync_topics。"})

    md = _render_review_doc(
        topics=state.topics,
        practice_history=state.practice_history,
        learning_order=state.learning_order,
        sort_by=sort_by,
        format=format,
    )
    return md


# ─── Tool 7.5: generate_mistake_sheet ─────────────────────────────


@mcp.tool()
def generate_mistake_sheet() -> str:
    """Generate a Markdown mistake review sheet from Q&A practice records. Only includes topics with 'weak' results that have question/user_answer/correct_answer data. Pure Markdown output (no JSON wrapper)."""
    state = load_state()
    if state is None or not state.topics:
        return "还没有学习数据。请先完成 setup + sync_topics。"

    # Filter practice records with Q&A data and weak result
    mistakes = [
        r for r in state.practice_history
        if r.result == "weak" and r.question and r.user_answer and r.correct_answer
    ]

    if not mistakes:
        return "暂无错题记录。需要在 record_answer 时传入 question/user_answer/correct_answer。"

    # Build topic name lookup
    id_to_name = {t.id: t.name for t in state.topics}

    # Group by topic_id
    from collections import defaultdict
    grouped: dict[str, list] = defaultdict(list)
    for rec in mistakes:
        grouped[rec.topic_id].append(rec)

    lines = ["# 错题集", ""]
    for topic_id in sorted(grouped.keys()):
        name = id_to_name.get(topic_id, topic_id)
        lines.append(f"## {name}")
        lines.append("")
        for i, rec in enumerate(grouped[topic_id], 1):
            q = (rec.question or "").replace("|", "\\|")
            ua = (rec.user_answer or "").replace("|", "\\|")
            ca = (rec.correct_answer or "").replace("|", "\\|")
            lines.append(f"### 错题 {i}")
            lines.append("")
            lines.append(f"- **题目**: {q}")
            lines.append(f"- **你的答案**: {ua}")
            lines.append(f"- **正确答案**: {ca}")
            lines.append(f"- **日期**: {rec.date}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ─── Tool 8: get_question_bank ────────────────────────────────────


@mcp.tool()
def get_question_bank(
    topic_ids: list[str] | None = None,
) -> str:
    """Return topics that have actionable content for question generation. Returns examples, homework references, and methods (encoding/decoding procedures, solution strategies, algorithms). Structured JSON for AI to reference when generating review guides and practice questions.

    Args:
        topic_ids: Optional list of topic IDs to filter. If None, returns all topics with actionable content.
    """
    state = load_state()
    if state is None or not state.topics:
        return json.dumps({"error": "没有知识点。请先完成 setup + sync_topics。"})

    topics = state.topics
    if topic_ids is not None:
        id_set = set(topic_ids)
        topics = [t for t in topics if t.id in id_set]

    action_keys = ("examples", "homework_refs", "methods")
    result_topics = []
    for t in topics:
        result_data = {"topic_id": t.id, "name": t.name, "chapter": t.chapter}
        has_content = False
        for key in action_keys:
            vals = t.attributes.get(key, [])
            if vals:
                result_data[key] = vals
                has_content = True
        if has_content:
            result_topics.append(result_data)

    return json.dumps(
        {
            "topics_with_examples": result_topics,
            "total_topics_with_examples": len(result_topics),
        },
        ensure_ascii=False,
        indent=2,
    )


# ─── Entry Point ───────────────────────────────────────────────


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()