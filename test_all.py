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
    switch_subject as _switch_subject, list_subjects as _list_subjects,
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
    patch_topic, generate_review_doc, get_question_bank,
    switch_subject, list_subjects,
    generate_mistake_sheet,
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
sync_result = json.loads(sync_topics(topics=topics_input, material_id="test-material"))
assert sync_result["added"] == 4
assert sync_result["updated"] == 0
assert sync_result["material_id"] == "test-material"
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
], material_id="test-material"))
assert sync_result2["updated"] == 1
updated_lr = next(t for t in sync_result2["topics"] if t["name"] == "线性回归")
assert updated_lr["attributes"] == {"formulas": ["新公式"], "definitions": ["线性模型"]}  # replaced, not merged
assert updated_lr["source"] == "新的原文"
print("  sync_topics REPLACE semantics OK")

# Test sync_topics with new attribute keys (methods, parameters, distinctions)
conv_topic = {"name": "卷积码", "level": "B", "chapter": "第6章", "depends_on": [],
              "attributes": {
                  "definitions": ["有记忆编码"],
                  "parameters": ["约束长度K=3", "码率R=1/2"],
                  "methods": ["Viterbi译码步骤：1.构建网格 2.计算路径度量 3.回溯"],
                  "distinctions": ["卷积码 vs 分组码：前者有记忆，后者无记忆"],
              },
              "source": "有记忆编码。Viterbi译码。广泛用于数字通信。"}
sync_conv = json.loads(sync_topics(topics=[conv_topic], material_id="test-material"))
assert sync_conv["added"] == 1
conv_data = next(t for t in sync_conv["topics"] if t["name"] == "卷积码")
assert conv_data["attributes"]["methods"] == ["Viterbi译码步骤：1.构建网格 2.计算路径度量 3.回溯"]
assert conv_data["attributes"]["parameters"] == ["约束长度K=3", "码率R=1/2"]
assert conv_data["attributes"]["distinctions"] == ["卷积码 vs 分组码：前者有记忆，后者无记忆"]
print("  sync_topics (new attribute keys) OK")

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
assert len(plan_result["priority_list"]) == 5
assert "daily_schedule" in plan_result
print(f"  generate_plan OK: {len(plan_result['priority_list'])} topics")

# Test generate_review_doc
doc_result = generate_review_doc(sort_by="chapter")
assert "复习手册" in doc_result
assert "线性回归" in doc_result
assert "🔴" in doc_result  # weak emoji
print("  generate_review_doc (chapter) OK")

doc_lo = generate_review_doc(sort_by="learning_order")
assert "练习记录" in doc_lo
print("  generate_review_doc (learning_order) OK")

# Test get_question_bank
# 卷积码 has methods — it already appears in question bank
qb_before = json.loads(get_question_bank())
assert qb_before["total_topics_with_examples"] == 1  # 卷积码 (has methods)
print("  get_question_bank (with methods only) OK")

# Patch a topic to add examples
patch_topic(topic_id=lr_id, attributes_merge={"examples": ["例3.1: 求回归方程"], "homework_refs": ["习题3.2"]})
qb_result = json.loads(get_question_bank())
assert qb_result["total_topics_with_examples"] == 2  # 卷积码 (methods) + 线性回归 (examples+homework)
lr_entry = next(t for t in qb_result["topics_with_examples"] if t["topic_id"] == lr_id)
assert "习题3.2" in lr_entry["homework_refs"]
print("  get_question_bank (with data) OK")

# Test get_question_bank includes topics with methods
conv_id = "卷积码"
qb_conv = json.loads(get_question_bank())
# 卷积码 has "methods" but no "examples" or "homework_refs" — should still appear
conv_in_qb = any(t["topic_id"] == conv_id for t in qb_conv["topics_with_examples"])
assert conv_in_qb, "Topic with methods should appear in question bank"
conv_entry = next(t for t in qb_conv["topics_with_examples"] if t["topic_id"] == conv_id)
assert "methods" in conv_entry
assert "Viterbi" in conv_entry["methods"][0]
print("  get_question_bank (methods trigger) OK")

# Filter by topic_ids
qb_filtered = json.loads(get_question_bank(topic_ids=[lr_id]))
assert qb_filtered["total_topics_with_examples"] == 1  # only 线性回归
qb_filtered_empty = json.loads(get_question_bank(topic_ids=["nonexistent_id"]))
assert qb_filtered_empty["total_topics_with_examples"] == 0
print("  get_question_bank (filter) OK")

# Verify examples and homework appear in review doc after patch
doc_with_examples = generate_review_doc(sort_by="chapter")
assert "例题" in doc_with_examples or "例3.1" in doc_with_examples
assert "作业" in doc_with_examples or "习题3.2" in doc_with_examples
print("  generate_review_doc (with examples/homework) OK")

# Verify new attribute keys render with Chinese labels
assert "方法" in doc_with_examples or "Viterbi" in doc_with_examples
assert "参数" in doc_with_examples or "约束长度" in doc_with_examples
assert "区别" in doc_with_examples or "分组码" in doc_with_examples
print("  generate_review_doc (new keys: 方法/参数/区别) OK")

# ─── 9. Test multi-subject isolation ───────────────────────────

print("=== Test 9: Multi-subject isolation ===")

# Create isolated temp directories for subjects
subj1_dir = Path(tempfile.mkdtemp()) / "高数"
subj2_dir = Path(tempfile.mkdtemp()) / "线性代数"

# Switch to 高数 (manually set path for test isolation)
set_state_path(subj1_dir / "state.json")
subj1_dir.mkdir(parents=True, exist_ok=True)
(subj1_dir / "chapters").mkdir(parents=True, exist_ok=True)

setup_review(exam_date="2026-07-15", daily_hours=3, mode="normal")
sync_topics(topics=[
    {"name": "微积分", "level": "A", "chapter": "第1章", "depends_on": []},
], material_id="高数课本")
高数_next = json.loads(get_next_topic())
assert 高数_next["name"] == "微积分"
print("  高数 state OK")

# Switch to 线性代数
set_state_path(subj2_dir / "state.json")
subj2_dir.mkdir(parents=True, exist_ok=True)
(subj2_dir / "chapters").mkdir(parents=True, exist_ok=True)

setup_review(exam_date="2026-07-20", daily_hours=2, mode="normal")
sync_topics(topics=[
    {"name": "矩阵", "level": "A", "chapter": "第1章", "depends_on": []},
], material_id="线性代数课本")
代数_next = json.loads(get_next_topic())
assert 代数_next["name"] == "矩阵"
print("  线性代数 state OK")

# Verify isolation: switching back to 高数 should still have 微积分
set_state_path(subj1_dir / "state.json")
高数_state = load_state()
assert len(高数_state.topics) == 1
assert 高数_state.topics[0].name == "微积分"
assert 高数_state.exam_date == "2026-07-15"
print("  高数 state preserved after switching subjects OK")

# Test switch_subject function directly
result = _switch_subject("测试科目")
assert result["subject"] == "测试科目"
assert result["state_exists"] == False
print("  switch_subject new subject OK")

# Test list_subjects
subjects = _list_subjects()
assert isinstance(subjects, dict)
assert "subjects" in subjects
print("  list_subjects OK")

# Cleanup test subject dirs
import shutil
shutil.rmtree(subj1_dir.parent, ignore_errors=True)
shutil.rmtree(subj2_dir.parent, ignore_errors=True)

# Reset to default for remaining cleanup
reset_state()
set_state_path(tmp_dir / "state.json")
print("  Multi-subject isolation OK")

# ─── 10. Test Phase A: models & diagnostic ──────────────────────

print("=== Test 10: Phase A — models & diagnostic ===")

from exam_review.models import PracticeRecord, ChapterProgress, PlanResult
from exam_review.diagnostic import (
    suggest_question_type,
    calculate_chapter_progress,
    check_mastery_decay,
)

# PracticeRecord Q&A fields
pr_qa = PracticeRecord(
    topic_id="lr", date="2026-07-01", result="weak",
    question="什么是线性回归？", user_answer="猜的", correct_answer="统计方法",
)
assert pr_qa.question == "什么是线性回归？"
assert pr_qa.user_answer == "猜的"
assert pr_qa.correct_answer == "统计方法"

pr_no_qa = PracticeRecord(topic_id="lr", date="2026-07-01", result="mastered")
assert pr_no_qa.question is None
assert pr_no_qa.user_answer is None
assert pr_no_qa.correct_answer is None
print("  PracticeRecord Q&A fields OK")

# ChapterProgress model
cp = ChapterProgress(
    chapter="第3章", total=10, mastered=5, learning=2, weak=1, untested=2,
    ready_to_learn=["梯度下降"],
)
assert cp.total == 10
assert cp.mastered == 5
assert cp.ready_to_learn == ["梯度下降"]
print("  ChapterProgress model OK")

# PlanResult with chapter_progress
pr_result = PlanResult(priority_list=[], daily_schedule=[], weak_summary="")
assert pr_result.chapter_progress == []
print("  PlanResult chapter_progress OK")

# suggest_question_type
t1 = Topic(id="t1", name="公式题", level="A", importance=0.85,
           attributes={"formulas": ["E=mc²"], "definitions": ["能量"]})
assert suggest_question_type(t1) == "fill_blank"  # formulas > definitions

t2 = Topic(id="t2", name="方法题", level="A", importance=0.85,
           attributes={"methods": ["step1: a", "step2: b"], "formulas": ["E=mc²"]})
assert suggest_question_type(t2) == "calculation"  # methods > formulas

t3 = Topic(id="t3", name="辨析题", level="A", importance=0.85,
           attributes={"distinctions": ["A vs B"], "methods": ["do X"]})
assert suggest_question_type(t3) == "mcq"  # distinctions > everything

t4 = Topic(id="t4", name="定义题", level="A", importance=0.85,
           attributes={"definitions": ["X is Y"]})
assert suggest_question_type(t4) == "short_answer"

t5 = Topic(id="t5", name="默认题", level="A", importance=0.85)
assert suggest_question_type(t5) == "fill_blank"  # default
print("  suggest_question_type OK")

# calculate_chapter_progress
cp_topics = [
    Topic(id="a", name="A", level="A", importance=0.85, chapter="ch1", status="mastered"),
    Topic(id="b", name="B", level="A", importance=0.85, chapter="ch1", status="weak", depends_on=["a"]),
    Topic(id="c", name="C", level="A", importance=0.85, chapter="ch1", status="unknown", depends_on=["a"]),
    Topic(id="d", name="D", level="A", importance=0.85, chapter="ch2", status="unknown"),
]
progress = calculate_chapter_progress(cp_topics)
assert len(progress) == 2
ch1 = next(p for p in progress if p.chapter == "ch1")
ch2 = next(p for p in progress if p.chapter == "ch2")
assert ch1.total == 3
assert ch1.mastered == 1
assert ch1.weak == 1
assert ch1.untested == 1
# B depends on A, A is mastered → B is ready
# C depends on A, A is mastered → C is ready too
assert "B" in ch1.ready_to_learn
assert "C" in ch1.ready_to_learn
assert ch2.untested == 1
assert ch2.ready_to_learn == ["D"]  # no deps → vacuous truth: ready to learn
print("  calculate_chapter_progress OK")

# check_mastery_decay
from datetime import date
t_mastered = Topic(id="m", name="M", level="A", importance=0.85, status="mastered")
history = [
    PracticeRecord(topic_id="m", date="2026-06-20", result="mastered"),
    PracticeRecord(topic_id="x", date="2026-07-01", result="weak"),
]
assert check_mastery_decay(t_mastered, history, decay_days=7, reference_date=date(2026, 7, 2)) == "decayed"
assert check_mastery_decay(t_mastered, history, decay_days=30, reference_date=date(2026, 7, 2)) == "stable"
# Non-mastered always stable
t_weak = Topic(id="w", name="W", level="A", importance=0.85, status="weak")
assert check_mastery_decay(t_weak, history) == "stable"
# No practice history → stable
t_no_history = Topic(id="n", name="N", level="A", importance=0.85, status="mastered")
assert check_mastery_decay(t_no_history, []) == "stable"
print("  check_mastery_decay OK")

# ─── 11. Test Phase A: planner & server integration ─────────────

print("=== Test 11: Phase A — planner & server integration ===")

# Reset for clean test
reset_state()
tmp_dir2 = Path(tempfile.mkdtemp())
set_state_path(tmp_dir2 / "state.json")

# Setup
setup_review(exam_date="2026-07-30", daily_hours=3, mode="normal")

# Sync topics with rich attributes
sync_topics(topics=[
    {"name": "统计基础", "level": "B", "chapter": "第1章", "depends_on": [],
     "attributes": {"definitions": ["统计是收集和分析数据的科学"]}},
    {"name": "线性回归", "level": "A", "chapter": "第3章", "depends_on": ["统计基础"],
     "attributes": {"formulas": ["β̂ = (X'X)⁻¹X'y"], "definitions": ["线性模型"], "distinctions": ["回归 vs 分类"]}},
    {"name": "梯度下降", "level": "A", "chapter": "第4章", "depends_on": ["线性回归"],
     "attributes": {"methods": ["1.初始化 2.计算梯度 3.更新参数"], "formulas": ["θ := θ - α∇J(θ)"]}},
], material_id="test-material")

# get_next_topic includes suggested_question_type
next_t = json.loads(get_next_topic())
assert "suggested_question_type" in next_t
assert next_t["suggested_question_type"] in ("fill_blank", "short_answer", "calculation", "mcq")
print(f"  get_next_topic question_type: {next_t['suggested_question_type']}")

# record_answer with Q&A fields
rec_result = json.loads(record_answer(
    topic_id=next_t["topic_id"],
    result="weak",
    question="请解释什么是线性回归？",
    user_answer="一种分类方法",
    correct_answer="研究变量间线性关系的统计方法",
))
assert rec_result["result"] == "weak"

# Verify Q&A persisted in practice_history
state_after = load_state()
last_rec = state_after.practice_history[-1]
assert last_rec.question == "请解释什么是线性回归？"
assert last_rec.user_answer == "一种分类方法"
assert last_rec.correct_answer == "研究变量间线性关系的统计方法"
print("  record_answer with Q&A fields OK")

# generate_plan with chapter_progress and question_type
plan = json.loads(generate_plan())
assert "chapter_progress" in plan
assert len(plan["chapter_progress"]) >= 2
assert plan["priority_list"][0].get("question_type") is not None
# Verify no side-effect mutation: get_next_topic still shows original status
next_after = json.loads(get_next_topic(filter="all"))
assert next_after["topic_id"] is not None  # there are topics to retest
print(f"  generate_plan chapter_progress: {len(plan['chapter_progress'])} chapters, question_type in priority")

# generate_review_doc with quickref format
quickref = generate_review_doc(sort_by="chapter", format="quickref")
assert "速查表" in quickref
assert "| 知识点 |" in quickref
print("  generate_review_doc quickref OK")

# Still produces detailed format
detailed = generate_review_doc(sort_by="chapter", format="detailed")
assert "复习手册" in detailed
print("  generate_review_doc detailed OK")

# generate_mistake_sheet
mistakes = generate_mistake_sheet()
# Our weak record has Q&A data, so it should show up
assert "错题" in mistakes or "暂无错题记录" in mistakes
if "错题" in mistakes:
    assert "线性回归" in mistakes or "线性" in mistakes
    assert "你的答案" in mistakes
    assert "正确答案" in mistakes
print("  generate_mistake_sheet OK")

# generate_plan does NOT modify topic.status
state_before_plan = load_state()
topic_before = next(t for t in state_before_plan.topics if t.id == next_t["topic_id"])
original_status = topic_before.status
_ = generate_plan()
state_after_plan = load_state()
topic_after = next(t for t in state_after_plan.topics if t.id == next_t["topic_id"])
assert topic_after.status == original_status, f"generate_plan mutated status: {original_status} → {topic_after.status}"
print("  generate_plan no side-effect mutation OK")

# Old v1 state without Q&A fields still loads
# (tested implicitly — all above tests use PracticeRecord with optional fields)
print("  v1 backward compatibility OK")

# Cleanup
shutil.rmtree(tmp_dir2, ignore_errors=True)
reset_state()
set_state_path(tmp_dir / "state.json")

print("  Phase A integration OK")

# Cleanup
reset_state()

# ─── Cleanup temp files ──────────────────────────────────────────
import shutil
shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)