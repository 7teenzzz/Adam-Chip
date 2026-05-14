import { api } from "../api.js";

const LOG_PORT = 8083;

function el(tag, attrs, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v != null && v !== false) node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null || c === false) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}

export function mount(target) {
  const base = `http://${location.hostname}:${LOG_PORT}`;

  const dot        = el("span", { class: "dot" });
  const statusText = el("span", { class: "muted", style: "font-size:11px" }, "проверка…");
  const openBtn    = el("a", {
    href: base,
    target: "_blank",
    rel: "noopener",
    class: "btn btn-primary",
    style: "font-size:12px; padding:6px 14px; opacity:0.4; pointer-events:none",
  }, "Открыть Log Viewer ↗");

  const kvDataDir = el("span", { style: "font-family:var(--font-mono);font-size:12px" }, "…");
  const kvEvents  = el("span", { style: "font-family:var(--font-mono);font-size:12px" }, "…");
  const kvMetrics = el("span", { style: "font-family:var(--font-mono);font-size:12px" }, "…");
  const kvUptime  = el("span", { style: "font-family:var(--font-mono);font-size:12px" }, "…");

  const svcBody = el("tbody");

  async function refresh() {
    try {
      const [health, services] = await Promise.all([
        fetch(`${base}/health`, { signal: AbortSignal.timeout(2000) }).then(r => r.json()),
        fetch(`${base}/services`, { signal: AbortSignal.timeout(2000) }).then(r => r.json()),
      ]);

      dot.className    = "dot ok";
      statusText.textContent = "доступен";
      openBtn.style.opacity       = "1";
      openBtn.style.pointerEvents = "";

      kvDataDir.textContent = health.data_dir || "—";
      kvEvents.textContent  = health.events_file_exists  ? "✓" : "✗";
      kvMetrics.textContent = health.metrics_file_exists ? "✓" : "✗";
      kvUptime.textContent  = health.uptime_sec != null ? health.uptime_sec + "s" : "—";

      svcBody.innerHTML = "";
      for (const [unit, v] of Object.entries(services)) {
        const ok  = v.active_state === "active";
        const bad = v.active_state === "inactive" || v.active_state === "failed";
        const cls = ok ? "ok" : bad ? "bad" : "warn";
        const tr  = el("tr", null, [
          el("td", { style: "font-family:var(--font-mono);font-size:11px;padding:6px 10px;border-bottom:1px solid var(--line)" }, unit),
          el("td", { style: "padding:6px 10px;border-bottom:1px solid var(--line)" }, [
            el("span", { class: `badge ${cls}` }, [
              el("span", { class: "dot", style: "width:5px;height:5px;background:currentColor;border-radius:50%;display:inline-block" }),
              document.createTextNode(" " + v.active_state),
            ]),
          ]),
          el("td", { style: "font-family:var(--font-mono);font-size:11px;color:var(--muted);padding:6px 10px;border-bottom:1px solid var(--line)" }, v.sub_state),
          el("td", { style: "font-family:var(--font-mono);font-size:11px;color:var(--dim);padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap" },
            (v.since || "").replace(/MSK|EET|UTC/g, "").trim()),
        ]);
        svcBody.appendChild(tr);
      }
    } catch {
      dot.className          = "dot bad";
      statusText.textContent = `недоступен (:${LOG_PORT})`;
      openBtn.style.opacity       = "0.4";
      openBtn.style.pointerEvents = "none";
    }
  }

  refresh();
  const timer = setInterval(refresh, 10000);

  const thStyle = "text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.07em;background:var(--bg-2)";

  const card = el("section", { class: "card", style: "max-width:800px" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Log Viewer"),
      el("div", { style: "display:flex;align-items:center;gap:8px" }, [dot, statusText]),
      el("span", { class: "spacer" }),
      openBtn,
    ]),
    el("div", { class: "card-body", style: "display:flex;flex-direction:column;gap:16px" }, [
      // health kv
      el("div", { style: "display:grid;grid-template-columns:repeat(4,1fr);gap:4px 24px" }, [
        el("span", { class: "caps" }, "data_dir"), el("span", { class: "caps" }, "events.jsonl"),
        el("span", { class: "caps" }, "metrics.jsonl"), el("span", { class: "caps" }, "uptime"),
        kvDataDir, kvEvents, kvMetrics, kvUptime,
      ]),
      // services
      el("div", null, [
        el("p", { class: "caps", style: "margin:0 0 6px" }, "Сервисы"),
        el("table", { style: "width:100%;border-collapse:collapse" }, [
          el("thead", null, [el("tr", null, [
            el("th", { style: thStyle }, "Юнит"),
            el("th", { style: thStyle }, "Статус"),
            el("th", { style: thStyle }, "Sub"),
            el("th", { style: thStyle }, "С"),
          ])]),
          svcBody,
        ]),
      ]),
    ]),
  ]);

  target.appendChild(card);
  return () => clearInterval(timer);
}
