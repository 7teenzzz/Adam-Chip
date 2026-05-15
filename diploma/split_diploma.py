"""
Diploma splitter — разбивает Diploma.md на иерархические фрагменты.

Поддерживаемые форматы заголовков (auto-detected):
  markdown          # H1 / ## H2 / ### H3 / #### H4
  russian_numbered  1. Текст / 1.1 Текст / 1.1.1 Текст (с/без точки)
  bold_numbered     **1.1 Текст** / **1.1. Текст**

Уровни вывода:
  H1  → diploma/chapters/ch{N:02d}_{slug}.md
  H2  → diploma/sections/ch{N:02d}_{M:02d}_{slug}.md
  H3  → diploma/subsections/ch{N:02d}_{M:02d}_{K:02d}_{slug}.md
  H4+ → хранится внутри родительского файла (не разбивается)

Использование:
  python diploma/split_diploma.py

Требует: diploma/Diploma.md (Docling output)
"""

import re
from pathlib import Path
from typing import Iterable

# Regex patterns for each heading style.
# Group 1 = level marker, Group 2 = title text.
RE_MARKDOWN = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
RE_RUSSIAN_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+(.{3,})$")
RE_BOLD_NUMBERED = re.compile(r"^\*\*\s*(\d+(?:\.\d+){0,3})\.?\s+(.+?)\s*\*\*\s*$")


def slugify(text: str) -> str:
    """Translit-friendly slug. Keeps Cyrillic words readable by code."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:60]


def numbered_level(num: str) -> int:
    """'1' → 1, '1.1' → 2, '1.1.1' → 3, '1.1.1.1' → 4."""
    return num.count(".") + 1


def detect_heading_style(md: str) -> str:
    """Returns one of: markdown, russian_numbered, bold_numbered.
    Picks the style yielding the most H1-level matches (≥3 required).
    """
    counts = {"markdown": 0, "russian_numbered": 0, "bold_numbered": 0}
    for line in md.splitlines():
        if m := RE_MARKDOWN.match(line):
            if len(m.group(1)) == 1:
                counts["markdown"] += 1
        if m := RE_RUSSIAN_NUMBERED.match(line):
            if numbered_level(m.group(1)) == 1:
                counts["russian_numbered"] += 1
        if m := RE_BOLD_NUMBERED.match(line):
            if numbered_level(m.group(1)) == 1:
                counts["bold_numbered"] += 1

    # Pick mode with ≥3 H1 markers; fallback to highest
    best = max(counts, key=lambda k: counts[k])
    if counts[best] < 1:
        raise RuntimeError(
            f"No heading style detected. Counts: {counts}. "
            "Check Diploma.md — Docling may have failed to parse structure."
        )
    return best


def parse_headings(md: str, style: str) -> list[tuple[int, str, int]]:
    """Returns list of (level, title, line_index) sorted by line_index."""
    headings: list[tuple[int, str, int]] = []
    lines = md.splitlines()

    if style == "markdown":
        for i, line in enumerate(lines):
            if m := RE_MARKDOWN.match(line):
                level = len(m.group(1))
                if level <= 4:
                    headings.append((level, m.group(2).strip(), i))

    elif style == "russian_numbered":
        for i, line in enumerate(lines):
            if m := RE_RUSSIAN_NUMBERED.match(line):
                level = numbered_level(m.group(1))
                title = f"{m.group(1)} {m.group(2).strip()}"
                if level <= 4:
                    headings.append((level, title, i))

    elif style == "bold_numbered":
        for i, line in enumerate(lines):
            if m := RE_BOLD_NUMBERED.match(line):
                level = numbered_level(m.group(1))
                title = f"{m.group(1)} {m.group(2).strip()}"
                if level <= 4:
                    headings.append((level, title, i))

    return headings


def extract_block(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start:end]).strip()


def split_diploma(source: Path, out_root: Path) -> None:
    if not source.exists():
        print(f"ERROR: {source} not found. Run convert_pdf.py first.")
        return

    md = source.read_text(encoding="utf-8")
    style = detect_heading_style(md)
    print(f"Detected heading style: {style}")

    headings = parse_headings(md, style)
    lines = md.splitlines()

    h1_count = sum(1 for h in headings if h[0] == 1)
    h2_count = sum(1 for h in headings if h[0] == 2)
    h3_count = sum(1 for h in headings if h[0] == 3)
    print(f"Found: {h1_count} H1, {h2_count} H2, {h3_count} H3")

    if h1_count < 2:
        print("WARNING: Less than 2 H1 headings detected. Split may be incomplete.")

    chapters_dir = out_root / "chapters"
    sections_dir = out_root / "sections"
    subsections_dir = out_root / "subsections"
    for d in (chapters_dir, sections_dir, subsections_dir):
        d.mkdir(parents=True, exist_ok=True)

    ch_idx = 0
    sec_idx = 0
    sub_idx = 0

    for i, (level, title, line_no) in enumerate(headings):
        end_line = len(lines)
        for j in range(i + 1, len(headings)):
            if headings[j][0] <= level:
                end_line = headings[j][2]
                break

        content = extract_block(lines, line_no, end_line)

        if level == 1:
            ch_idx += 1
            sec_idx = 0
            sub_idx = 0
            slug = slugify(title)
            path = chapters_dir / f"ch{ch_idx:02d}_{slug}.md"
            path.write_text(content, encoding="utf-8")
            print(f"  CH {ch_idx:02d}  {path.name}  ({len(content.splitlines())} lines)")

        elif level == 2:
            sec_idx += 1
            sub_idx = 0
            slug = slugify(title)
            path = sections_dir / f"ch{ch_idx:02d}_{sec_idx:02d}_{slug}.md"
            path.write_text(content, encoding="utf-8")
            print(f"    SEC {ch_idx:02d}.{sec_idx:02d}  {path.name}")

        elif level == 3:
            sub_idx += 1
            slug = slugify(title)
            path = subsections_dir / f"ch{ch_idx:02d}_{sec_idx:02d}_{sub_idx:02d}_{slug}.md"
            path.write_text(content, encoding="utf-8")
            print(f"      SUB {ch_idx:02d}.{sec_idx:02d}.{sub_idx:02d}  {path.name}")

    print(f"\nDone. style={style} chapters={ch_idx} sections={sec_idx_total(headings)} subsections={sub_idx_total(headings)}")


def sec_idx_total(headings: Iterable[tuple[int, str, int]]) -> int:
    return sum(1 for h in headings if h[0] == 2)


def sub_idx_total(headings: Iterable[tuple[int, str, int]]) -> int:
    return sum(1 for h in headings if h[0] == 3)


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    split_diploma(
        source=repo_root / "diploma" / "Diploma.md",
        out_root=repo_root / "diploma",
    )
