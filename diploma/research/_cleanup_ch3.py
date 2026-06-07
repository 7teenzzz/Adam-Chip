"""One-off cleanup of diploma/chapters/ch03_chapter3.md.

Removes Docling artifacts:
  - <!-- page N --> and <!-- merged from ... --> HTML comments
  - Standalone numeric lines (page footers like "79")
  - Two redundant H1-merged blocks (# 1. Конфигурационный... and # 2. Динамический...)
    whose content is now integrated into the 3.2.3 narrative
  - Reflow paragraph lines into single long lines (joins lines like "при"/"эмоционально"/"окрашенном" back into prose)

Also normalizes file paths to module names only:
  System/adam/prompt.py -> prompt.py, etc.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "chapters" / "ch03_chapter3.md"

raw = SRC.read_text(encoding="utf-8")

# --- Step 1: drop HTML comments (page markers, merged-from) ---
raw = re.sub(r"<!--.*?-->\s*\n", "", raw)

# --- Step 2: drop standalone page numbers (lines with just digits) ---
raw = re.sub(r"^\d+\s*$\n", "", raw, flags=re.MULTILINE)

# --- Step 3: drop the two redundant H1 blocks ---
# Block A: "# 1. Конфигурационный уровень ... промпт"
# Block B: "# 2. Динамический уровень ... консистентности."
# Both blocks end before the next "## 3.1" or "## 3.2" or "### 3.x.x" heading.
raw = re.sub(
    r"# 1\. Конфигурационный уровень[\s\S]*?(?=##|###)",
    "",
    raw,
    count=1,
)
# After dropping block A, block B should now follow. Same pattern:
# Actually block B starts after some intermediate text. Let's match what's left.

# --- Step 4: file path -> module name replacements ---
path_replacements = [
    ("System/adam/prompt.py", "prompt.py"),
    ("System/adam/action.py", "action.py"),
    ("System/adam/device.py", "device.py"),
    ("System/Speech/ASR_WhisperX.py", "ASR_WhisperX.py"),
    ("System/Speech/TTS.py", "TTS.py"),
    ("System/Config.json", "Config.json"),
    ("Engineering/consolidator.py", "consolidator.py"),
    ("System/adam/memory_metrics.py", "memory_metrics.py"),
    ("System/adam/aiim.py", "aiim.py"),
]
for full, short in path_replacements:
    raw = raw.replace(full, short)

# --- Step 5: reflow paragraphs ---
# Lines should be joined within paragraph blocks.
# Block boundaries: blank line, heading line, code fence, table row, list-item start, image link line.
lines = raw.split("\n")
out: list[str] = []
in_code = False
para_buf: list[str] = []

def flush():
    if para_buf:
        out.append(" ".join(para_buf))
        para_buf.clear()

list_re = re.compile(r"^([-*]|\d+\.)\s")
table_re = re.compile(r"^\s*\|")
heading_re = re.compile(r"^#")
fence_re = re.compile(r"^\s*```")

for line in lines:
    stripped = line.strip()

    if fence_re.match(line):
        flush()
        out.append(line)
        in_code = not in_code
        continue

    if in_code:
        out.append(line)
        continue

    if not stripped:
        flush()
        out.append("")
        continue

    if heading_re.match(stripped) or table_re.match(line):
        flush()
        out.append(line)
        continue

    if list_re.match(stripped):
        # List item — start its own paragraph (allow continuation lines after)
        flush()
        para_buf.append(stripped)
        continue

    # Mermaid block sometimes preserved without fence; handle as code fallback?
    # We trust the ```mermaid fence to catch it.

    # Regular text line — accumulate into paragraph
    para_buf.append(stripped)

flush()

cleaned = "\n".join(out)

# --- Step 6: collapse 3+ consecutive blank lines to single blank line ---
cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

SRC.write_text(cleaned, encoding="utf-8")
print(f"Cleaned. Original size: {len(raw)} chars, new size: {len(cleaned)} chars")
