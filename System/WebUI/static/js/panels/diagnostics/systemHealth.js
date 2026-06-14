// Panel: #/diagnostics/system
// Power gate (nvpmodel/jetson_clocks) + systemd-style service health from
// /api/agent/status, moved out of panels/subsystem.js. Remaining diagnostic
// content is deferred to a future phase (placeholder card).

import { api } from "../../api.js";

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

function dot(kind) {
  const colors = { ok: "var(--ok, #4caf50)", bad: "var(--bad, #f44336)", warn: "var(--warn, #ff9800)" };
  return el("span", {
    style: `display:inline-block; width:8px; height:8px; border-radius:50%; background:${colors[kind] || "var(--muted)"}; flex-shrink:0`,
  });
}

function serviceRow(label, health) {
  const ok = health?.ok === true;
  const kind = ok ? "ok" : "bad";
  return el("div", {
    style: "display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--bg-3)",
  }, [
    dot(kind),
    el("span", { style: "font-size:13px" }, label),
    el("span", { class: "dim", style: "font-size:11px; margin-left:auto" }, health?.detail || (ok ? "ok" : "ошибка")),
  ]);
}

function renderPower(power) {
  const errors = power?.errors || [];
  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Питание (nvpmodel / jetson_clocks)"),
      dot(power?.ok ? "ok" : "bad"),
    ]),
    el("div", { class: "card-body" }, [
      el("div", { style: "display:grid; grid-template-columns:1fr 1fr; gap:0 24px" }, [
        el("div", { style: "padding:5px 0; border-bottom:1px solid var(--bg-3)" }, [
          el("span", { class: "caps", style: "color:var(--muted)" }, "Режим"),
          el("div", { class: "mono", style: "font-size:12px" }, power?.mode_text || "—"),
        ]),
        el("div", { style: "padding:5px 0; border-bottom:1px solid var(--bg-3)" }, [
          el("span", { class: "caps", style: "color:var(--muted)" }, "jetson_clocks"),
          el("div", { class: "mono", style: "font-size:12px" }, power?.clocks_text || "—"),
        ]),
      ]),
      errors.length
        ? el("div", { style: "margin-top:8px; color:var(--bad); font-size:12px" }, errors.join("; "))
        : null,
    ]),
  ]);
}

function renderServices(services) {
  const grid = el("div", { style: "display:grid; grid-template-columns:1fr 1fr; gap:0 24px" });
  Object.entries(services || {}).forEach(([key, health]) => {
    grid.appendChild(serviceRow(key.toUpperCase(), health));
  });
  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Сервисы")),
    el("div", { class: "card-body" }, [grid]),
  ]);
}

function renderPlaceholder() {
  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Диагностика системы")),
    el("div", { class: "card-body" }, [
      el("p", { style: "color:var(--text); font-size:13px; margin:0 0 4px" }, "Раздел в разработке"),
      el("p", { style: "color:var(--muted); font-size:12px; margin:0" }, "Содержимое появится в следующей фазе."),
    ]),
  ]);
}

export function mount(target) {
  const container = el("div", { class: "col" });
  target.appendChild(container);

  async function refresh() {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:12px 0", text: "Загрузка…" }));

    let status;
    try {
      status = await api.get("/api/agent/status");
    } catch (e) {
      container.innerHTML = "";
      container.appendChild(el("div", {
        class: "muted", style: "font-size:12px; padding:12px 0",
        text: "Ошибка загрузки: " + e.message,
      }));
      return;
    }

    container.innerHTML = "";
    container.appendChild(renderPower(status?.power));
    container.appendChild(renderServices(status?.services));
    container.appendChild(renderPlaceholder());
  }

  refresh();

  return function teardown() {};
}
