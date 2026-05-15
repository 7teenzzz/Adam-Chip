"""
Consolidate fragmented chapter files into canonical 4-chapter layout.

PyMuPDF-based split fragments chapters when ordered-list items like
"1. Восприятие" trigger H1 detection. This script consolidates the
fragments into Introduction + Chapter 1 + Chapter 2 + Chapter 3
based on numeric position in the split output.

Strategy: respect the chapter_map.md ground truth — there are exactly
4 macro-chapters and we know roughly where each starts.

Usage:
  python diploma/consolidate_chapters.py
"""

import re
import shutil
from pathlib import Path


CHAPTERS_DIR = Path("diploma/chapters")
RAW_DIR = Path("diploma/chapters/_raw")


# Map raw ch## files to canonical chapter index (0=intro, 1, 2, 3=Ch3, 4=refs)
# After visual inspection of split output (line counts + filenames):
CONSOLIDATION_RULES = {
    "ch04_": 0,  # Введение
    "ch05_": 1,  # Глава 1 main
    "ch06_": 1, "ch07_": 1, "ch08_": 1, "ch09_": 1, "ch10_": 1, "ch11_": 1, "ch12_": 1, "ch13_": 1,
    "ch14_": 2,  # Глава 2
    "ch15_": 3,  # Глава 3 intro (3.1.1 orphan + 3.1)
    "ch16_": 3, "ch17_": 3, "ch18_": 3, "ch19_": 3,  # Глава 3 sub
    "ch20_": 4,  # Список источников
}

CANONICAL_NAMES = {
    0: "ch00_introduction.md",
    1: "ch01_chapter1.md",
    2: "ch02_chapter2.md",
    3: "ch03_chapter3.md",
    4: "ch99_bibliography.md",
}


def main() -> int:
    if not CHAPTERS_DIR.exists():
        print(f"Missing {CHAPTERS_DIR} — run split_diploma.py first", flush=True)
        return 1

    raw_files = sorted([p for p in CHAPTERS_DIR.iterdir()
                        if p.is_file() and p.name.startswith("ch") and p.suffix == ".md"
                        and not p.name.startswith(("ch00_", "ch01_chapter", "ch02_chapter", "ch03_chapter", "ch99_"))])

    if not raw_files:
        print("No raw chapter files to consolidate (already done?).")
        return 0

    RAW_DIR.mkdir(exist_ok=True)
    buckets: dict[int, list[Path]] = {}

    for p in raw_files:
        prefix = p.name[:5]
        bucket = CONSOLIDATION_RULES.get(prefix)
        if bucket is None:
            shutil.move(str(p), RAW_DIR / p.name)
            continue
        buckets.setdefault(bucket, []).append(p)

    for bucket, files in sorted(buckets.items()):
        target_name = CANONICAL_NAMES[bucket]
        target = CHAPTERS_DIR / target_name
        merged = []
        for f in sorted(files):
            merged.append(f"\n<!-- merged from {f.name} -->\n")
            merged.append(f.read_text(encoding="utf-8"))
        target.write_text("\n".join(merged), encoding="utf-8")
        for f in files:
            shutil.move(str(f), RAW_DIR / f.name)
        print(f"Bucket {bucket} -> {target_name} ({sum(1 for _ in files)} files merged)")

    print("\nFinal canonical chapters:")
    for f in sorted(CHAPTERS_DIR.iterdir()):
        if f.is_file():
            print(f"  {f.name} ({f.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
