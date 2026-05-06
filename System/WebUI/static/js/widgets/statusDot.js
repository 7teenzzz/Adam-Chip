// Returns DOM element for a coloured status dot. Pass {ok, label, title}.
// kind: "ok" | "warn" | "bad" | "amber" | "" (neutral).

export function statusDot(kind, label, title) {
  const wrap = document.createElement("span");
  wrap.className = "row";
  wrap.style.gap = "6px";
  if (title) wrap.title = title;
  const dot = document.createElement("span");
  dot.className = `dot ${kind || ""}`.trim();
  wrap.appendChild(dot);
  if (label) {
    const text = document.createElement("span");
    text.className = "caps";
    text.textContent = label;
    text.style.color = "var(--muted)";
    wrap.appendChild(text);
  }
  return wrap;
}

export function kindFromHealth(h) {
  if (!h) return "";
  if (h.ok === true) return "ok";
  if (h.ok === false) return "bad";
  return "warn";
}
