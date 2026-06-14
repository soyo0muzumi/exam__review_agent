# Final Exam Review — MCP Server

AI-powered exam review planner, delivered as an MCP Server with 6 tools.

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
| `parse_material` | file_path | chapters: [{name, text}] | Parse PDF/DOCX/MD into chapter chunks |
| `sync_topics` | topics: [{name, level, chapter, depends_on?}] | Scored topics + learning order | Submit all knowledge points, get scored list |
| `record_answer` | topic_id, result (mastered/learning/weak) | Progress + fatigue flag | Record diagnostic result |
| `get_next_topic` | filter? (untested/all) | Next A-level topic to test | Get next question target |
| `generate_plan` | (uses current state) | Priority list + daily schedule + weak summary | Generate final review plan |

## Workflow

```
0. setup_review        → Set exam date & hours
1. parse_material      → Get chapter text
2. sync_topics          → AI submits knowledge points → tool scores & sorts
3. get_next_topic       → Get next topic to test
   → AI asks question
   → record_answer      → Record result
   → Repeat until done
4. generate_plan        → Get priority list + schedule
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
- `pdfplumber` — PDF text extraction
- `python-docx` — DOCX parsing