"""Integration test for exam_review MCP server — validates all core modules."""
import json
import sys
import tempfile
from pathlib import Path

# ─── 1. Test models ──────────────────────────────────────────────
from exam_review.models import Topic, ReviewState, DailyPlanItem, PlanResult

print("=== Test 1: Models ===")
topic = Topic(id="lr", name="线性回归", level="A", importance=0.85, chapter="第3章")
assert topic.id == "lr"
assert topic.importance == 0.85
assert topic.attributes == {}  # default
assert topic.source == ""  # default
topic_with_attrs = Topic(
    id="nn", name="神经网络", level="A", importance=0.85,
    attributes={"formulas": ["σ(wx+b)"], "pitfalls": ["过拟合"]},
    source="神经网络是一种模拟生物神经系统的计算模型...",
)
assert topic_with_attrs.attributes["formulas"] == ["σ(wx+b)"]
assert topic_with_attrs.source.startswith("神经网络")
from exam_review.models import PracticeRecord
pr = PracticeRecord(topic_id="lr", date="2026-06-16", result="weak")
assert pr.topic_id == "lr"
assert pr.date == "2026-06-16"
assert pr.result == "weak"
state_with_history = ReviewState(exam_date="2026-07-15", daily_hours=3, mode="normal")
assert state_with_history.practice_history == []  # default empty
print("  PracticeRecord OK")
state = ReviewState(exam_date="2026-07-15", daily_hours=3, mode="normal")
assert state.exam_date == "2026-07-15"
assert state.topics == []
print("  Models OK")

# ─── 2. Test state persistence ───────────────────────────────────
from exam_review.state import (
    set_state_path, save_state, load_state, reset_state,
    save_chapter_text, load_all_chapter_text, get_or_create_state,
)

print("=== Test 2: State persistence ===")
tmp_dir = Path(tempfile.mkdtemp())
set_state_path(tmp_dir / "state.json")

state = ReviewState(
    exam_date="2026-07-15",
    daily_hours=3.0,
    mode="normal",
    chapter_weights={"第3章": 1.2},
)
save_state(state)

loaded = load_state()
assert loaded is not None
assert loaded.exam_date == "2026-07-15"
assert loaded.daily_hours == 3.0
assert loaded.chapter_weights == {"第3章": 1.2}
print("  Save/Load OK")

# Test chapter text
save_chapter_text("第1章", "这是第一章的文本 " * 50)
save_chapter_text("第2章", "这是第二章的文本 " * 50)
all_text = load_all_chapter_text()
assert "第一章" in all_text
assert "第二章" in all_text
print("  Chapter text OK")

# Test get_or_create
result = get_or_create_state()
assert result.exam_date == "2026-07-15"
print("  get_or_create OK")

# ─── 3. Test scorer ─────────────────────────────────────────────
from exam_review.scorer import count_occurrences, calculate_importance, score_topics

print("=== Test 3: Scorer ===")
freq = count_occurrences("线性回归是重点，线性回归很重要，线性回归必考", "线性回归")
assert freq == 3, f"Expected 3, got {freq}"
freq2 = count_occurrences("abc abc abc def", "abc")
assert freq2 == 3
print("  count_occurrences OK")

imp = calculate_importance("A", 3, None, "")
assert imp == 0.95  # 0.85 + 0.10

imp2 = calculate_importance("B", 1, {"第3章": 1.15}, "第3章")
assert abs(imp2 - 0.6325) < 0.001  # 0.55 * 1.15

imp3 = calculate_importance("C", 0, None, "")
assert imp3 == 0.25
print("  calculate_importance OK")

topics = [
    Topic(id="lr", name="线性回归", level="A", importance=0.25, chapter="第3章"),
    Topic(id="nn", name="神经网络", level="B", importance=0.25, chapter="第4章"),
    Topic(id="conv", name="卷积", level="C", importance=0.25, chapter="第5章"),
]
text = "线性回归 线性回归 线性回归 神经网络 神经网络"
scored = score_topics(topics, text, {"第3章": 1.2})
assert scored[0].importance > 0.85  # A-level with freq boost
assert scored[1].name == "神经网络"
print("  score_topics OK")

# ─── 4. Test structure (topological sort) ────────────────────────
from exam_review.structure import topological_sort

print("=== Test 4: Topological sort ===")
topics = [
    Topic(id="lr", name="线性回归", level="A", importance=0.85, depends_on=["stat"]),
    Topic(id="stat", name="统计基础", level="B", importance=0.55, depends_on=[]),
    Topic(id="gd", name="梯度下降", level="A", importance=0.85, depends_on=["lr"]),
    Topic(id="reg", name="正则化", level="B", importance=0.55, depends_on=["lr"]),
]
order = topological_sort(topics)
assert order.index("stat") < order.index("lr"), f"stat should come before lr, got {order}"
assert order.index("lr") < order.index("gd"), f"lr should come before gd, got {order}"
assert order.index("lr") < order.index("reg"), f"lr should come before reg, got {order}"
print(f"  Topological sort OK: {order}")

# ─── 5. Test diagnostic ──────────────────────────────────────────
from exam_review.diagnostic import (
    get_a_level_topics, get_next_untested, get_next_for_retest,
    calculate_progress, detect_fatigue,
)

print("=== Test 5: Diagnostic ===")
topics = [
    Topic(id="a1", name="A1", level="A", importance=0.85, status="unknown"),
    Topic(id="a2", name="A2", level="A", importance=0.80, status="unknown"),
    Topic(id="b1", name="B1", level="B", importance=0.55, status="unknown"),
]
a_level = get_a_level_topics(topics)
assert len(a_level) == 2
print("  get_a_level_topics OK")

next_t = get_next_untested(topics, set(), "normal")
assert next_t.id == "a1"
next_t2 = get_next_untested(topics, {"a1"}, "normal")
assert next_t2.id == "a2"
next_t3 = get_next_untested(topics, {"a1", "a2"}, "normal")
assert next_t3 is None
print("  get_next_untested OK")

# Quick mode caps at 3
many = [Topic(id=f"a{i}", name=f"A{i}", level="A", importance=0.85) for i in range(10)]
next_q = get_next_untested(many, set(), "quick")
assert next_q.id == "a0"  # first untested
print("  get_next_untested (quick mode) OK")

# Retest weak/learning
retest_topics = [
    Topic(id="a1", name="A1", level="A", importance=0.85, status="weak"),
    Topic(id="a2", name="A2", level="A", importance=0.80, status="learning"),
    Topic(id="a3", name="A3", level="A", importance=0.75, status="mastered"),
]
retest = get_next_for_retest(retest_topics, set())
assert retest.id == "a1"  # weak comes first
print("  get_next_for_retest OK")

progress = calculate_progress(retest_topics)
assert progress["total"] == 3
assert progress["weak"] == 1
assert progress["mastered"] == 1
print("  calculate_progress OK")

# Fatigue detection: 3 consecutive weak
fatigue_topics = [
    Topic(id="a1", name="A1", level="A", importance=0.85, status="weak"),
    Topic(id="a2", name="A2", level="A", importance=0.80, status="weak"),
    Topic(id="a3", name="A3", level="A", importance=0.75, status="weak"),
]
assert detect_fatigue(fatigue_topics) == True
no_fatigue = [
    Topic(id="a1", name="A1", level="A", importance=0.85, status="mastered"),
    Topic(id="a2", name="A2", level="A", importance=0.80, status="weak"),
]
assert detect_fatigue(no_fatigue) == False
print("  detect_fatigue OK")

# ─── 6. Test planner ─────────────────────────────────────────────
from exam_review.planner import priority_score, generate_plan

print("=== Test 6: Planner ===")
t_weak = Topic(id="lr", name="线性回归", level="A", importance=0.85, status="weak")
t_learn = Topic(id="gd", name="梯度下降", level="A", importance=0.80, status="learning")
t_master = Topic(id="stat", name="统计基础", level="B", importance=0.55, status="mastered")

p1 = priority_score(t_weak)
assert abs(p1 - 1.65) < 0.001  # 0.85 + 0.8*1.0
p2 = priority_score(t_learn)
assert abs(p2 - 1.20) < 0.001  # 0.80 + 0.8*0.5
p3 = priority_score(t_master)
assert abs(p3 - 0.55) < 0.001  # 0.55 + 0.8*0.0
print("  priority_score OK")

plan = generate_plan(
    topics=[t_weak, t_learn, t_master],
    exam_date="2026-07-30",
    daily_hours=2,
    mode="normal",
    learning_order=["lr", "gd", "stat"],
)
assert len(plan.priority_list) == 3
assert plan.priority_list[0]["name"] == "线性回归"  # highest priority
assert len(plan.daily_schedule) > 0
print(f"  generate_plan OK: {len(plan.daily_schedule)} days scheduled")
weak_summary_ascii = plan.weak_summary.encode("ascii", errors="replace").decode()
print(f"  Weak summary: {weak_summary_ascii[:40]}...")

# Quick mode — no daily schedule
plan_quick = generate_plan(
    topics=[t_weak, t_learn, t_master],
    exam_date="2026-07-30",
    daily_hours=2,
    mode="quick",
)
assert plan_quick.daily_schedule == []
print("  generate_plan (quick mode) OK")

# ─── 7. Test parser ──────────────────────────────────────────────
from exam_review.parser import parse_text, _chunk_by_chapters

print("=== Test 7: Parser ===")
# Test chapter chunking
text = """前言内容在这里。

第一章 绪论
这是绪论的内容，介绍了基本概念。

第二章 方法
这是方法的内容，详细讲解了方法论。"""

chapters = _chunk_by_chapters(text)
assert len(chapters) >= 2
print(f"  _chunk_by_chapters OK: {len(chapters)} chapters")

# Test parse_text with markdown content
parsed = parse_text("第一章 测试\n\n测试内容在这里。")
# Parser splits by chapter markers; single-chapter text becomes "全文"
print(f"  parse_text OK: {[c['name'] for c in parsed]}")

# ─── 8. Test server tools (direct function calls) ────────────────
from exam_review.server import (
    setup_review, parse_material, sync_topics,
    record_answer, get_next_topic, generate_plan,
    patch_topic,
)
from exam_review.state import load_state

print("=== Test 8: Server tool functions ===")

# Reset state for clean test
reset_state()

# Setup
result = json.loads(setup_review(
    exam_date="2026-07-30",
    daily_hours=3,
    chapter_weights={"第3章": 1.2},
    mode="normal",
))
assert result["exam_date"] == "2026-07-30"
assert result["daily_hours"] == 3
print("  setup_review OK")

# Sync topics
topics_input = [
    {"name": "统计基础", "level": "B", "chapter": "第1章", "depends_on": []},
    {"name": "线性回归", "level": "A", "chapter": "第3章", "depends_on": ["统计基础"],
     "attributes": {"formulas": ["β̂ = (X'X)⁻¹X'y"], "pitfalls": ["R²高≠模型好"]},
     "source": "线性回归是研究变量间线性关系的统计方法..."},
    {"name": "梯度下降", "level": "A", "chapter": "第4章", "depends_on": ["线性回归"]},
    {"name": "正则化", "level": "B", "chapter": "第5章", "depends_on": ["线性回归"]},
]
sync_result = json.loads(sync_topics(topics=topics_input))
assert sync_result["added"] == 4
assert sync_result["updated"] == 0
assert len(sync_result["learning_order"]) == 4
# Verify attributes and source are stored
topics_by_name = {t["name"]: t for t in sync_result["topics"]}
assert topics_by_name["线性回归"]["attributes"]["formulas"] == ["β̂ = (X'X)⁻¹X'y"]
assert topics_by_name["线性回归"]["source"].startswith("线性回归")
assert topics_by_name["统计基础"]["attributes"] == {}
print(f"  sync_topics OK: added={sync_result['added']}, order={sync_result['learning_order']}")

# Test sync_topics REPLACE semantics: re-submitting same topic with new attributes replaces them
sync_result2 = json.loads(sync_topics(topics=[
    {"name": "线性回归", "level": "A", "chapter": "第3章", "depends_on": ["统计基础"],
     "attributes": {"formulas": ["新公式"], "definitions": ["线性模型"]}, "source": "新的原文"},
]))
assert sync_result2["updated"] == 1
updated_lr = next(t for t in sync_result2["topics"] if t["name"] == "线性回归")
assert updated_lr["attributes"] == {"formulas": ["新公式"], "definitions": ["线性模型"]}  # replaced, not merged
assert updated_lr["source"] == "新的原文"
print("  sync_topics REPLACE semantics OK")

# Get next topic
next_topic = json.loads(get_next_topic())
assert next_topic["level"] == "A"
assert "attributes" in next_topic
assert "source" in next_topic
print(f"  get_next_topic OK: {next_topic['name']}")

# Incremental update via patch_topic (merge semantics)
lr_id = "线性回归".replace(" ", "_").lower()  # "线性回归"
patch_result = json.loads(patch_topic(
    topic_id=lr_id,
    attributes_merge={"pitfalls": ["R²高≠模型好"]},
    source="线性回归是研究变量间线性关系的统计方法，通过最小二乘法拟合...",
))
# patch_topic MERGES: new key "pitfalls" added, existing key "formulas" preserved
assert "pitfalls" in patch_result["attributes"]
assert "R²高≠模型好" in patch_result["attributes"]["pitfalls"]
assert "formulas" in patch_result["attributes"]  # still there from sync_topics replace
assert patch_result["source"].startswith("线性回归")
attrs_safe = json.dumps(patch_result["attributes"], ensure_ascii=True)
print(f"  patch_topic OK: {patch_result['name']} attrs={attrs_safe}")

# Record answer
record_result = json.loads(record_answer(
    topic_id=next_topic["topic_id"],
    result="weak",
))
assert record_result["result"] == "weak"
assert record_result["progress"]["weak"] == 1
print(f"  record_answer OK: {record_result['topic_id']} → weak")

# Verify practice_history was appended
state_check = load_state()
assert len(state_check.practice_history) >= 1
assert state_check.practice_history[0].topic_id == next_topic["topic_id"]
assert state_check.practice_history[0].result == "weak"
print("  practice_history append OK")

# Get next again
next2 = json.loads(get_next_topic())
assert next2["name"] != next_topic["name"]
print(f"  get_next_topic (2nd) OK: {next2['name']}")

# Record and finish
record_answer(topic_id=next2["topic_id"], result="mastered")

# Check done
done_check = json.loads(get_next_topic())
print(f"  Remaining topic: {done_check}")

# Generate plan
plan_result = json.loads(generate_plan())
assert "priority_list" in plan_result
assert len(plan_result["priority_list"]) == 4
assert "daily_schedule" in plan_result
print(f"  generate_plan OK: {len(plan_result['priority_list'])} topics")

# Cleanup
reset_state()

# ─── Cleanup temp files ──────────────────────────────────────────
import shutil
shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)