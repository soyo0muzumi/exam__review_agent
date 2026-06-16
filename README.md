# Final Exam Review — MCP Server

AI-powered exam review planner, delivered as an MCP Server with 11 tools.

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

Then restart Hermes Agent. The 11 tools will auto-discover as `mcp_exam_review_*` and become available in every conversation.

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

## Tools (11)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `switch_subject` | subject (name string) | Subject info (name, state_exists, topics_count) | Switch to a subject-specific state directory |
| `list_subjects` | (none) | List of subjects with exam_date and progress | List all subjects that have been set up |
| `setup_review` | exam_date, daily_hours, chapter_weights?, mode? | State summary | Initialize/reset review state |
| `parse_material` | text | chapters: [{name, text}] | Split text into chapter chunks (use pdf-mcp to extract PDF text first) |
| `sync_topics` | topics: [{name, level, chapter, depends_on?, attributes?, source?}] | Scored topics + learning order | Submit all knowledge points, get scored list |
| `record_answer` | topic_id, result (mastered/learning/weak) | Progress + fatigue flag | Record diagnostic result |
| `get_next_topic` | filter? (untested/all) | Next A-level topic with attributes & source | Get next question target |
| `patch_topic` | topic_id, level?, attributes_merge?, source? | Updated topic | Incrementally update a single topic (merge semantics) |
| `generate_plan` | (uses current state) | Priority list + daily schedule + weak summary | Generate final review plan |
| `generate_review_doc` | sort_by? (chapter/learning_order) | Markdown review document | Generate review document organized by chapter or learning order |
| `get_question_bank` | topic_ids? | JSON with topics that have examples/homework_refs | Show available examples and homework references |

## Workflow

```
-1. switch_subject("高数") → Switch to a subject (call before setup_review for new subjects)
-0.5. list_subjects() → List all existing subjects with progress info
0. setup_review        → Set exam date & hours
1. pdf-mcp pdf_read_all → Extract PDF text (or other tools for DOCX/MD)
2. parse_material       → Split text into chapters
3. sync_topics          → AI submits knowledge points → tool scores & sorts
   (Each topic can include attributes and source)
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

## Modes

- **normal**: Full 11-tool workflow
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

然后重启 Hermes Agent，11 个工具会自动发现为 `mcp_exam_review_*` 前缀，在所有会话中均可使用。

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

## 工具 (11)

| 工具 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `switch_subject` | subject（科目名） | 科目信息（名称、状态、知识点数） | 切换到科目专属状态目录 |
| `list_subjects` | （无） | 所有科目的列表及进度 | 列出所有已设置的科目 |
| `setup_review` | exam_date, daily_hours, chapter_weights?, mode? | 状态摘要 | 初始化/重置复习状态 |
| `parse_material` | text（纯文本） | chapters: [{name, text}] | 将文本按章节切分（PDF 需先通过 pdf-mcp 提取文本） |
| `sync_topics` | topics: [{name, level, chapter, depends_on?, attributes?, source?}] | 评分后知识点 + 学习顺序 | 提交所有知识点，获取评分排序 |
| `record_answer` | topic_id, result (mastered/learning/weak) | 进度 + 疲劳标记 | 记录诊断结果 |
| `get_next_topic` | filter? (untested/all) | 下一个 A 级知识点（含 attributes & source） | 获取下一个测试目标 |
| `patch_topic` | topic_id, level?, attributes_merge?, source? | 更新后的知识点 | 增量更新单个知识点（合并语义） |
| `generate_plan` | （使用当前状态） | 优先级列表 + 每日计划 + 薄弱总结 | 生成最终复习计划 |
| `generate_review_doc` | sort_by? (chapter/learning_order) | Markdown 复习文档 | 按章节或学习顺序生成复习手册 |
| `get_question_bank` | topic_ids? | 包含例题/作业的知识点 JSON | 展示可用的例题和作业题目 |

## 工作流

```
-1. switch_subject("高数") → 切换到科目（新科目需先切换再 setup_review）
-0.5. list_subjects() → 列出所有科目及进度
0. setup_review        → 设置考试日期与每日学习时长
1. pdf-mcp pdf_read_all → 提取 PDF 文本（DOCX/MD 用其他工具）
2. parse_material       → 按章节切分文本
3. sync_topics          → AI 提交知识点 → 工具评分排序
   （每个知识点可包含 attributes 和 source）
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

## 模式

- **normal**：完整 11 工具工作流
- **cram**：距离考试 ≤3 天，紧凑安排，仅 A 级知识点
- **quick**：仅生成优先级列表，测试前 3 个 A 级知识点

## 依赖

- `mcp` — Python MCP SDK
- `pydantic` — 数据模型