# Final Exam Review — MCP Server

AI-powered exam review planner, delivered as an MCP Server with 13 tools.

[English](#quick-start) | [中文](#快速开始)

## Quick Start

### Install

```bash
cd exam-ai
pip install -e .
```

### Configure in Hermes Agent

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  exam-review:
    command: python
    args: ["-m", "exam_review.server"]
    enabled: true
```

Or use the CLI:

```bash
hermes mcp add exam-review --command python --args "-m,exam_review.server"
```

Then restart Hermes Agent. The 13 tools will auto-discover as `mcp_exam_review_*` and become available in every conversation.

### Configure Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "exam-review": {
      "command": "python",
      "args": ["-m", "exam_review.server"]
    }
  }
}
```

Or if installed via pip:

```json
{
  "mcpServers": {
    "exam-review": {
      "command": "exam-review"
    }
  }
}
```

### Run standalone (for testing)

```bash
python -m exam_review.server
```

This starts the MCP server on stdio. Claude Code will connect automatically when configured.

## Tools (13)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `switch_subject` | subject (name string) | Subject info (name, state_exists, topics_count) | Switch to a subject-specific state directory |
| `list_subjects` | (none) | List of subjects with exam_date and progress | List all subjects that have been set up |
| `setup_review` | exam_date, daily_hours, chapter_weights?, mode? | State summary | Initialize/reset review state |
| `parse_material` | text | chapters: [{name, text}] | Split text into chapter chunks (use pdf-mcp to extract PDF text first) |
| `sync_topics` | topics: [{name, level, chapter, depends_on?, attributes?, source?}], material_id | Scored topics + learning order + material_id | Submit all knowledge points with source tracking |
| `detect_knowledge_gaps` | expected_topics: [{name, level?, chapter?}] | JSON with missing, partial, present & total_expected | Detect gaps by comparing current topics vs expected syllabus |
| `record_answer` | topic_id, result (mastered/learning/weak), question?, user_answer?, correct_answer? | Progress + fatigue flag + Q&A stored | Record diagnostic result |
| `get_next_topic` | filter? (untested/all) | Next A-level topic with attributes, source & suggested_question_type | Get next question target |
| `patch_topic` | topic_id, level?, attributes_merge?, source? | Updated topic | Incrementally update a single topic (merge semantics) |
| `generate_plan` | (uses current state) | Priority list + daily schedule + weak summary + chapter_progress | Generate final review plan |
| `generate_review_doc` | sort_by? (chapter/learning_order), format? (detailed/quickref) | Markdown review document | Generate review document organized by chapter or learning order |
| `generate_mistake_sheet` | (none) | Markdown mistake review | Generate mistake review from Q&A records |
| `get_question_bank` | topic_ids? | JSON with topics that have examples, homework_refs, or methods | Show available examples, methods, and homework references |

## Workflow

```
-1. switch_subject("高数") → Switch to a subject (call before setup_review for new subjects)
-0.5. list_subjects() → List all existing subjects with progress info
0. setup_review        → Set exam date & hours
1. pdf-mcp pdf_read_all → Extract PDF text (or other tools for DOCX/MD)
2. parse_material       → Split text into chapters
3. sync_topics(topics, material_id) → AI submits knowledge points → tool scores, sorts & tags sources
   (Optional: detect_knowledge_gaps → Compare with expected syllabus to find missing topics)
   (Each topic can include attributes and source — see Attributes Schema below)
4. get_next_topic       → Get next topic with attributes & source
   → AI asks question
   → record_answer      → Record result
   → Repeat until done
   (Optional: patch_topic → Incrementally update a topic's attributes/source)
5. generate_plan        → Get priority list + schedule
   (Optional: generate_review_doc → Markdown review document for human review)
   (Optional: get_question_bank → List topics with example problems for study)
```

## Priority Function

```
priority = importance + 0.8 × weakness
```

- `importance`: A=0.85, B=0.55, C=0.25, +0.10 if frequency≥3, ×chapter_weight
- `weakness`: weak=1.0, learning=0.5, mastered=0.0, unknown=0.3

This is the **sole sorting standard**. No overrides.

## State

Persisted to `~/.exam-review/state.json`. Resumes automatically on next session.

## Attributes Schema

Each topic's `attributes` dict uses these recommended keys:

| Key | Label | Description |
|-----|-------|-------------|
| `formulas` | 公式 | Core formulas, theorems, laws |
| `definitions` | 定义 | Key definitions, concepts |
| `parameters` | 参数 | Parameters with physical/math meaning |
| `methods` | 方法 | Methods, procedures, algorithms (encoding/decoding, proof, derivation, solution steps) |
| `pitfalls` | 易错 | Common misconceptions |
| `examples` | 例题 | Typical example problems |
| `homework_refs` | 作业 | Homework/exercise references |
| `distinctions` | 区别 | Comparisons and disambiguations |

The type is `dict[str, list[str]]` — any key is accepted, but the 8 keys above have Chinese labels in generated output. Keys other than these 8 render with the raw key name.

## Modes

- **normal**: Full 13-tool workflow
- **cram**: ≤3 days to exam, tight packing, A-level only
- **quick**: Priority list only, test first 3 A-level topics

## Dependencies

- `mcp` — MCP SDK for Python
- `pydantic` — Data models

---

## 快速开始

### 安装

```bash
cd exam-ai
pip install -e .
```

### 在 Hermes Agent 中配置

添加到 `~/.hermes/config.yaml`：

```yaml
mcp_servers:
  exam-review:
    command: python
    args: ["-m", "exam_review.server"]
    enabled: true
```

或使用 CLI 命令：

```bash
hermes mcp add exam-review --command python --args "-m,exam_review.server"
```

然后重启 Hermes Agent，13 个工具会自动发现为 `mcp_exam_review_*` 前缀，在所有会话中均可使用。

### 配置 Claude Code

添加到 `~/.claude/settings.json`：

```json
{
  "mcpServers": {
    "exam-review": {
      "command": "python",
      "args": ["-m", "exam_review.server"]
    }
  }
}
```

通过 pip 安装时：

```json
{
  "mcpServers": {
    "exam-review": {
      "command": "exam-review"
    }
  }
}
```

### 独立运行（测试用）

```bash
python -m exam_review.server
```

服务通过 stdio 启动 MCP 协议，配置后 Claude Code 会自动连接。

## 工具 (13)

| 工具 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `switch_subject` | subject（科目名） | 科目信息（名称、状态、知识点数） | 切换到科目专属状态目录 |
| `list_subjects` | （无） | 所有科目的列表及进度 | 列出所有已设置的科目 |
| `setup_review` | exam_date, daily_hours, chapter_weights?, mode? | 状态摘要 | 初始化/重置复习状态 |
| `parse_material` | text（纯文本） | chapters: [{name, text}] | 将文本按章节切分（PDF 需先通过 pdf-mcp 提取文本） |
| `sync_topics` | topics: [{name, level, chapter, depends_on?, attributes?, source?}], material_id | 评分后知识点 + 学习顺序 + material_id | 提交所有知识点，带来源追踪 |
| `detect_knowledge_gaps` | expected_topics: [{name, level?, chapter?}] | JSON（missing, partial, present & total_expected） | 对比预期大纲，发现遗漏知识点 |
| `record_answer` | topic_id, result (mastered/learning/weak), question?, user_answer?, correct_answer? | 进度 + 疲劳标记 + 存储 Q&A | 记录诊断结果 |
| `get_next_topic` | filter? (untested/all) | 下一个 A 级知识点（含 attributes, source & suggested_question_type） | 获取下一个测试目标 |
| `patch_topic` | topic_id, level?, attributes_merge?, source? | 更新后的知识点 | 增量更新单个知识点（合并语义） |
| `generate_plan` | （使用当前状态） | 优先级列表 + 每日计划 + 薄弱总结 + chapter_progress | 生成最终复习计划 |
| `generate_review_doc` | sort_by? (chapter/learning_order), format? (detailed/quickref) | Markdown 复习文档 | 按章节或学习顺序生成复习手册 |
| `generate_mistake_sheet` | （无） | Markdown 错题复习 | 从 Q&A 记录生成错题复习 |
| `get_question_bank` | topic_ids? | 包含例题、方法或作业的知识点 JSON | 展示可用的例题、方法和作业题目 |

## 工作流

```
-1. switch_subject("高数") → 切换到科目（新科目需先切换再 setup_review）
-0.5. list_subjects() → 列出所有科目及进度
0. setup_review        → 设置考试日期与每日学习时长
1. pdf-mcp pdf_read_all → 提取 PDF 文本（DOCX/MD 用其他工具）
2. parse_material       → 按章节切分文本
3. sync_topics(topics, material_id) → AI 提交知识点 → 工具评分、排序并标记来源
   （可选：detect_knowledge_gaps → 对比预期大纲，发现遗漏知识点）
   （每个知识点可包含 attributes 和 source — 见下方属性 Schema）
4. get_next_topic       → 获取下一个待测知识点（含 attributes & source）
   → AI 出题
   → record_answer      → 记录结果
   → 重复直到完成
   （可选：patch_topic → 增量更新知识点的 attributes/source）
5. generate_plan        → 获取优先级列表 + 学习计划
   （可选：generate_review_doc → 生成 Markdown 复习文档供人阅读）
   （可选：get_question_bank → 列出有例题的知识点）
```

## 优先级公式

```
优先级 = importance + 0.8 × weakness
```

- `importance`：A=0.85, B=0.55, C=0.25，频率≥3 再 +0.10，×章节权重
- `weakness`：weak=1.0, learning=0.5, mastered=0.0, unknown=0.3

这是**唯一排序标准**，不可覆盖。

## 状态

持久化到 `~/.exam-review/state.json`，下次会话自动恢复。

## 属性 Schema

每个知识点的 `attributes` 字典推荐使用以下键：

| 键 | 中文标签 | 说明 |
|----|---------|------|
| `formulas` | 公式 | 核心公式、定理、定律 |
| `definitions` | 定义 | 关键定义、概念 |
| `parameters` | 参数 | 参数及其物理/数学含义 |
| `methods` | 方法 | 方法、步骤、算法（编码/译码、证明、推导、解题步骤） |
| `pitfalls` | 易错 | 常见误解 |
| `examples` | 例题 | 典型例题 |
| `homework_refs` | 作业 | 作业题号 |
| `distinctions` | 区别 | 对比辨析 |

类型为 `dict[str, list[str]]`，接受任意键，但以上 8 个键在生成输出时有中文标签。其他键直接显示原始键名。

## 模式

- **normal**：完整 13 工具工作流
- **cram**：距离考试 ≤3 天，紧凑安排，仅 A 级知识点
- **quick**：仅生成优先级列表，测试前 3 个 A 级知识点

## 依赖

- `mcp` — Python MCP SDK
- `pydantic` — 数据模型