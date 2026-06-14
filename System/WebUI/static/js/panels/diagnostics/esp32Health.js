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

const MODULE_LABELS = {
  mic:     "Микрофон (INMP441)",
  cam:     "Камера (OV)",
  pcm5102: "Динамик (PCM5102)",
  pca9685: "Моторика (PCA9685)",
  temt600: "Датч. света (TEMT600)",
  pir:     "Датч. движения (PIR)",
};

const MODULE_ORDER = ["mic", "cam", "pcm5102", "pca9685", "temt600", "pir"];

function dot(kind) {
  const colors = { ok: "var(--ok, #4caf50)", bad: "var(--bad, #f44336)", warn: "var(--warn, #ff9800)" };
  return el("span", {
    style: `display:inline-block; width:8px; height:8px; border-radius:50%; background:${colors[kind] || "var(--muted)"}; flex-shrink:0`,
  });
}

function moduleGrid(modules) {
  const items = MODULE_ORDER.map((key) => {
    const m = modules?.[key];
    const ok = m?.ok === true;
    const unknown = m == null;
    const kind = unknown ? "warn" : ok ? "ok" : "bad";
    const detail = m?.error ? ` — ${m.error}` : "";
    return el("div", {
      style: "display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--bg-3)",
    }, [
      dot(kind),
      el("span", { style: "font-size:13px" }, MODULE_LABELS[key] || key),
      unknown ? el("span", { class: "dim", style: "font-size:11px; margin-left:auto" }, "н/д") : null,
      detail ? el("span", { style: "font-size:11px; color:var(--bad); margin-left:auto" }, detail) : null,
    ]);
  });

  const grid = el("div", {
    style: "display:grid; grid-template-columns:1fr 1fr; gap:0 24px",
  });
  items.forEach((it) => grid.appendChild(it));
  return grid;
}

export function mount(target) {
  const body = el("div", { class: "card-body" });

  api.get("/api/ui/status").then((resp) => {
    const data = resp?.data || resp;
    const grid = moduleGrid(data?.modules);
    if (grid) body.appendChild(grid);
  }).catch(() => {
    body.appendChild(el("div", { class: "muted" }, "Ошибка загрузки статуса"));
  });

  const card = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Состояние модулей ESP32")),
    body,
  ]);
  target.appendChild(card);

  return () => {
    // no intervals to clear
  };
}
