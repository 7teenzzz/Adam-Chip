"""
Diploma structure inspector — read-only валидация Docling output.

Проверяет качество извлечения и рекомендует heading style для split_diploma.py.

Использование:
  python diploma/inspect_structure.py
"""

import re
from collections import Counter
from pathlib import Path


RE_MARKDOWN = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
RE_RUSSIAN_NUMBERED = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+(.{3,})$")
RE_BOLD_NUMBERED = re.compile(r"^\*\*\s*(\d+(?:\.\d+){0,3})\.?\s+(.+?)\s*\*\*\s*$")


def numbered_level(num: str) -> int:
    return num.count(".") + 1


def analyze(md: str) -> dict:
    stats = {
        "total_chars": len(md),
        "total_lines": md.count("\n") + 1,
        "non_ascii_chars": sum(1 for c in md if ord(c) > 127),
        "cyrillic_chars": sum(1 for c in md if "Ѐ" <= c <= "ӿ"),
        "markdown": {"H1": [], "H2": [], "H3": [], "H4": []},
        "russian_numbered": {"H1": [], "H2": [], "H3": [], "H4": []},
        "bold_numbered": {"H1": [], "H2": [], "H3": [], "H4": []},
    }
    for line in md.splitlines():
        if m := RE_MARKDOWN.match(line):
            lvl = len(m.group(1))
            if lvl <= 4:
                stats["markdown"][f"H{lvl}"].append(m.group(2).strip())
        if m := RE_RUSSIAN_NUMBERED.match(line):
            lvl = numbered_level(m.group(1))
            if lvl <= 4:
                title = f"{m.group(1)} {m.group(2).strip()}"
                stats["russian_numbered"][f"H{lvl}"].append(title)
        if m := RE_BOLD_NUMBERED.match(line):
            lvl = numbered_level(m.group(1))
            if lvl <= 4:
                title = f"{m.group(1)} {m.group(2).strip()}"
                stats["bold_numbered"][f"H{lvl}"].append(title)
    return stats


def recommend(stats: dict) -> str:
    h1_counts = {
        style: len(stats[style]["H1"])
        for style in ("markdown", "russian_numbered", "bold_numbered")
    }
    if max(h1_counts.values()) == 0:
        return "NONE — no heading style detected. Check Diploma.md manually."
    return max(h1_counts, key=lambda k: h1_counts[k])


def main() -> int:
    repo_root = Path(__file__).parent.parent
    md_path = repo_root / "diploma" / "Diploma.md"
    if not md_path.exists():
        print(f"ERROR: {md_path} not found. Run convert_pdf.py first.")
        return 1

    md = md_path.read_text(encoding="utf-8")
    stats = analyze(md)

    print("=" * 70)
    print(f"Diploma.md analysis")
    print("=" * 70)
    print(f"Total chars:        {stats['total_chars']:,}")
    print(f"Total lines:        {stats['total_lines']:,}")
    print(f"Non-ASCII chars:    {stats['non_ascii_chars']:,}")
    print(f"Cyrillic chars:     {stats['cyrillic_chars']:,}")
    cyr_ratio = stats["cyrillic_chars"] / max(stats["total_chars"], 1)
    print(f"Cyrillic ratio:     {cyr_ratio:.1%}")
    if cyr_ratio < 0.3:
        print("WARNING: Low Cyrillic ratio. Russian text may be poorly extracted.")

    print()
    print("Heading detection per style:")
    for style in ("markdown", "russian_numbered", "bold_numbered"):
        h1 = len(stats[style]["H1"])
        h2 = len(stats[style]["H2"])
        h3 = len(stats[style]["H3"])
        h4 = len(stats[style]["H4"])
        print(f"  {style:20s}  H1={h1:3d}  H2={h2:3d}  H3={h3:3d}  H4={h4:3d}")

    rec = recommend(stats)
    print()
    print(f"RECOMMENDED STYLE: {rec}")

    if rec != "NONE":
        print()
        print(f"First 10 H1 ({rec}):")
        for h in stats[rec]["H1"][:10]:
            print(f"  - {h[:80]}")
        print()
        print(f"First 10 H2 ({rec}):")
        for h in stats[rec]["H2"][:10]:
            print(f"  - {h[:80]}")

    print()
    print("First 30 lines of Diploma.md:")
    print("-" * 70)
    for i, line in enumerate(md.splitlines()[:30], 1):
        print(f"{i:3d} | {line[:100]}")
    print("-" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
