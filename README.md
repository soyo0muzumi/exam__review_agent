# Final Exam Review — MCP Server

AI-powered exam review planner, delivered as an MCP Server with 6 tools.

[English](#quick-start) | [中文](#快速开始)

## Quick Start

### Install

```bash
cd exam-ai
pip install -e .
```

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

## Tools (6)

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `setup_review` | exam_date, daily_hours, chapter_weights?, mode? | State summary | Initialize/reset review state |
| `parse_material` | text | chapters: [{name, text}] | Split text into chapter chunks (use pdf-mcp to extract PDF text first) |
| `sync_topics` | topics: [{name, level, chapter, depends_on?}] | Scored topics + learning order | Submit all knowledge points, get scored list |
| `record_answer` | topic_id, result (mastered/learning/weak) | Progress + fatigue flag | Record diagnostic result |
| `get_next_topic` | filter? (untested/all) | Next A-level topic to test | Get next question target |
| `generate_plan` | (uses current state) | Priority list + daily schedule + weak summary | Generate final review plan |

## Workflow

```
0. setup_review        → Set exam date & hours
1. pdf-mcp pdf_read_all → Extract PDF text (or other tools for DOCX/MD)
2. parse_material       → Split text into chapters
3. sync_topics          → AI submits knowledge points → tool scores & sorts
4. get_next_topic       → Get next topic to test
   → AI asks question
   → record_answer      → Record result
   → Repeat until done
5. generate_plan        → Get priority list + schedule
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

- **normal**: Full 6-step workflow
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

## 工具 (6)

| 工具 | 输入 | 输出 | 用途 |
|------|------|------|------|
| `setup_review` | exam_date, daily_hours, chapter_weights?, mode? | 状态摘要 | 初始化/重置复习状态 |
| `parse_material` | text（纯文本） | chapters: [{name, text}] | 将文本按章节切分（PDF 需先通过 pdf-mcp 提取文本） |
| `sync_topics` | topics: [{name, level, chapter, depends_on?}] | 评分后知识点 + 学习顺序 | 提交所有知识点，获取评分排序 |
| `record_answer` | topic_id, result (mastered/learning/weak) | 进度 + 疲劳标记 | 记录诊断结果 |
| `get_next_topic` | filter? (untested/all) | 下一个 A 级知识点 | 获取下一个测试目标 |
| `generate_plan` | （使用当前状态） | 优先级列表 + 每日计划 + 薄弱总结 | 生成最终复习计划 |

## 工作流

```
0. setup_review        → 设置考试日期与每日学习时长
1. pdf-mcp pdf_read_all → 提取 PDF 文本（DOCX/MD 用其他工具）
2. parse_material       → 按章节切分文本
3. sync_topics          → AI 提交知识点 → 工具评分排序
4. get_next_topic       → 获取下一个待测知识点
   → AI 出题
   → record_answer      → 记录结果
   → 重复直到完成
5. generate_plan        → 获取优先级列表 + 学习计划
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

- **normal**：完整 6 步工作流
- **cram**：距离考试 ≤3 天，紧凑安排，仅 A 级知识点
- **quick**：仅生成优先级列表，测试前 3 个 A 级知识点

## 依赖

- `mcp` — Python MCP SDK
- `pydantic` — 数据模型