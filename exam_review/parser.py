"""Parse text into chapter-based chunks.

Receives plain text (LLM extracts from PDF/DOCX via pdf-mcp or other tools)
and splits it by chapter headers.
"""

from __future__ import annotations

import re

CHAPTER_PATTERN = re.compile(
    r"(第[一二三四五六七八九十百\d]+章|Chapter\s+\d+|第[一二三四五六七八九十百\d]+节)",
    re.IGNORECASE,
)


def parse_text(text: str) -> list[dict]:
    """Parse plain text and return list of {name, text} chapters.

    Args:
        text: Full text extracted from PDF/DOCX/MD by the caller (LLM).
    """
    if not text.strip():
        raise ValueError("文本内容为空，请确认文件已正确提取。")

    return _chunk_by_chapters(text)


def _chunk_by_chapters(text: str) -> list[dict]:
    """Split text by chapter headers. Returns list of {name, text}."""
    splits = CHAPTER_PATTERN.split(text)

    if len(splits) <= 1:
        return [{"name": "全文", "text": text.strip()}]

    chapters = []
    i = 1
    while i < len(splits) - 1:
        header = splits[i].strip()
        content = splits[i + 1].strip() if i + 1 < len(splits) else ""
        if content:
            # Truncate very long chapters
            if len(content) > 10000:
                content = content[:8000] + "\n\n[... 内容过长，已截断 ...]"
            chapters.append({"name": header, "text": content})
        i += 2

    # Pre-text before first chapter
    if splits[0].strip():
        chapters.insert(0, {"name": "前言", "text": splits[0].strip()})

    return chapters if chapters else [{"name": "全文", "text": text.strip()}]


def count_occurrences(text: str, target: str) -> int:
    """Count how many times target appears in text (for frequency scoring)."""
    return text.count(target)