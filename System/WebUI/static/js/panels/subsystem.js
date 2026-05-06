import { api } from "../api.js";

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

function addrRow(label, value) {
  if (!value) return null;
  return el("div", {
    style: "display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid var(--bg-3); font-size:12px",
  }, [
    el("span", { class: "caps", style: "color:var(--muted)" }, label),
    el("a", {
      href: value.startsWith("http") ? value : "#",
      target: "_blank",
      rel: "noopener",
      class: "mono",
      style: "color:var(--accent); text-decoration:none; word-break:break-all",
    }, value),
  ]);
}

function configKv(key, value) {
  const display = value === null || value === undefined ? "—"
    : typeof value === "boolean" ? (value ? "да" : "нет")
    : Array.isArray(value) ? value.join(", ") || "—"
    : String(value);

  return el("div", {
    style: "display:flex; flex-direction:column; gap:3px; padding:4px 0",
  }, [
    el("span", { class: "caps", style: "color:var(--muted); font-size:10px" }, key),
    el("span", { class: "mono", style: "font-size:12px; color:var(--text); word-break:break-all" }, display),
  ]);
}

function configSection(title, obj) {
  if (!obj || typeof obj !== "object") return null;
  const entries = Object.entries(obj);
  if (!entries.length) return null;
  const grid = el("div", { class: "field-grid" });
  entries.forEach(([k, v]) => {
    if (typeof v === "object" && !Array.isArray(v)) return; // skip nested objects
    grid.appendChild(configKv(k, v));
  });
  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, title)),
    el("div", { class: "card-body" }, [grid]),
  ]);
}

export function mount(target) {
  const statusBadge = el("span", { class: "mono dim", style: "font-size:12px" }, "загрузка…");
  const refreshBtn = el("button", { class: "btn", onclick: () => refresh() }, "↺ Обновить");

  const modulesBody = el("div");
  const addrsBody = el("div");
  const configRoot = el("div", { class: "col", style: "gap:12px" });
  const errBlock = el("div", { style: "display:none; color:var(--bad); font-size:12px; font-family:var(--font-mono); margin-top:8px" });

  target.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "row" }, [
      el("span", { class: "caps" }, "Подсистема ESP32 · состояние модулей и конфигурация"),
      el("span", { class: "spacer" }),
      statusBadge,
      refreshBtn,
    ]),
    errBlock,
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, "ESP32 · Модули")),
      el("div", { class: "card-body" }, [modulesBody]),
    ]),
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, "ESP32 · Адреса")),
      el("div", { class: "card-body" }, [addrsBody]),
    ]),
    configRoot,
  ]));

  async function refresh() {
    statusBadge.textContent = "обновление…";
    errBlock.style.display = "none";

    try {
      const [uiStatus, config] = await Promise.all([
        api.get("/api/ui/status"),
        api.get("/api/config"),
      ]);

      // Modules
      modulesBody.innerHTML = "";
      modulesBody.appendChild(moduleGrid(uiStatus.modules));

      // Addresses
      addrsBody.innerHTML = "";
      const esp = uiStatus.esp || {};
      const addrRows = [
        addrRow("base_url", esp.base_url),
        addrRow("camera_stream_url", esp.camera_stream_url),
        addrRow("mic_stream_url", esp.mic_stream_url),
        addrRow("speaker_url", esp.speaker_url),
      ].filter(Boolean);
      if (addrRows.length) addrRows.forEach((r) => addrsBody.appendChild(r));
      else addrsBody.textContent = "нет данных";

      // Config sections
      configRoot.innerHTML = "";
      const sections = [
        ["Конфигурация MCU", config?.mcu],
        ["Питание", config?.power],
        ["Безопасность", config?.safety],
      ];
      sections.forEach(([title, obj]) => {
        const sec = configSection(title, obj);
        if (sec) configRoot.appendChild(sec);
      });
      if (!configRoot.children.length) {
        configRoot.appendChild(el("div", { class: "card" }, el("div", { class: "card-body muted" }, "Конфиг MCU/power/safety не найден.")));
      }

      // Errors
      const errors = uiStatus.errors;
      if (errors && Object.keys(errors).length) {
        const lines = Object.entries(errors).map(([k, v]) => `${k}: ${v}`).join("\n");
        errBlock.style.display = "";
        errBlock.textContent = "Ошибки ESP32:\n" + lines;
      }

      const espOk = uiStatus.ok;
      statusBadge.style.color = espOk ? "var(--ok, #4caf50)" : "var(--bad, #f44336)";
      statusBadge.textContent = espOk ? "ESP32 онлайн" : "ESP32 офлайн";
    } catch (e) {
      statusBadge.textContent = "ошибка";
      statusBadge.style.color = "var(--bad, #f44336)";
      errBlock.style.display = "";
      errBlock.textContent = e.message;
    }
  }

  refresh();
}
