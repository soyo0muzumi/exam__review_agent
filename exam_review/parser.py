"""Parse PDF, DOCX, and MD files into chapter-based text chunks.

Uses pdfplumber for PDF (no OCR dependency). If extraction fails or yields
very little text, returns an error message and suggests the user provide a
text-selectable version.
"""

from __future__ import annotations

import re
from pathlib import Path

CHAPTER_PATTERN = re.compile(
    r"(第[一二三四五六七八九十百\d]+章|Chapter\s+\d+|第[一二三四五六七八九十百\d]+节)",
    re.IGNORECASE,
)


def parse_file(path: Path) -> list[dict]:
    """Parse a file and return list of {name, text} chapters."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        text = _parse_pdf(path)
    elif suffix == ".docx":
        text = _parse_docx(path)
    elif suffix in (".md", ".txt"):
        text = path.read_text(encoding="utf-8")
    else:
        text = path.read_text(encoding="utf-8")

    if not text.strip():
        raise ValueError(f"文件 {path} 内容为空或无法读取。")

    # PDF with very little text likely scanned
    if suffix == ".pdf" and len(text.strip()) < 100:
        raise ValueError(
            "PDF 内容过少，可能是扫描件。请提供可选中文字的 PDF 版本，或改用 DOCX/Markdown。"
        )

    return _chunk_by_chapters(text)


def _parse_pdf(path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
    import pdfplumber

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n".join(pages)


def _parse_docx(path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


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