"""
Diploma splitter — разбивает Diploma.md на иерархические фрагменты.

Уровни:
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


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:60]


def parse_headings(md: str):
    """Возвращает список (level, title, start_line_index)."""
    headings = []
    lines = md.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            headings.append((level, title, i))
    return headings, lines


def extract_block(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start:end]).strip()


def split_diploma(source: Path, out_root: Path) -> None:
    if not source.exists():
        print(f"ERROR: {source} not found. Run Docling first.")
        return

    md = source.read_text(encoding="utf-8")
    headings, lines = parse_headings(md)

    chapters_dir = out_root / "chapters"
    sections_dir = out_root / "sections"
    subsections_dir = out_root / "subsections"
    for d in (chapters_dir, sections_dir, subsections_dir):
        d.mkdir(parents=True, exist_ok=True)

    ch_idx = 0
    sec_idx = 0
    sub_idx = 0

    for i, (level, title, line_no) in enumerate(headings):
        # find end of this block = start of next heading at same or higher level
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

    print(f"\nDone. chapters={chapters_dir}, sections={sections_dir}, subsections={subsections_dir}")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    split_diploma(
        source=repo_root / "diploma" / "Diploma.md",
        out_root=repo_root / "diploma",
    )
