#!/usr/bin/env python3
# Prints a brief graph summary at session start. Called by .claude/settings.json SessionStart hook.
import re
import sys
from pathlib import Path

# Only run if we're in the Adam-Chip project
report_path = Path("graphify-out/GRAPH_REPORT.md")
if not report_path.exists():
    sys.exit(0)

text = report_path.read_text(encoding="utf-8")

# Extract stats line: nodes, edges, communities
stats_match = re.search(r"\*\*(\d+) nodes\*\*.*?\*\*(\d+) edges\*\*.*?\*\*(\d+) communities\*\*", text)
stats = ""
if stats_match:
    stats = f"{stats_match.group(1)} nodes · {stats_match.group(2)} edges · {stats_match.group(3)} communities"

# Extract god nodes section (first 5 entries)
god_match = re.search(r"## God Nodes(.*?)(?=\n## |\Z)", text, re.DOTALL)
god_lines = ""
if god_match:
    lines = [l.strip() for l in god_match.group(1).strip().splitlines() if l.strip() and l.strip().startswith("|") and "---" not in l and "Node" not in l]
    god_lines = "\n".join(lines[:5])

print(f"[graphify] Knowledge graph loaded — {stats}")
if god_lines:
    print(f"God nodes (most connected):\n{god_lines}")
print("[graphify] Use /graphify query, /graphify path, or MCP tools to explore.")
