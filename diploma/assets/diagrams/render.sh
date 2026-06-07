#!/usr/bin/env bash
# Render all *.mmd → *.svg via mmdc (Mermaid CLI).
# Usage: ./render.sh [filename.mmd]  (without arg — рендерит все)
set -e
cd "$(dirname "$0")"

render_one() {
    local src="$1"
    local out="${src%.mmd}.svg"
    echo "  $src → $out"
    mmdc -i "$src" -o "$out" -b transparent -c mermaid-config.json --quiet
}

if [ -n "$1" ]; then
    render_one "$1"
else
    for f in *.mmd; do
        [ -f "$f" ] || continue
        render_one "$f"
    done
fi

echo "Done."
